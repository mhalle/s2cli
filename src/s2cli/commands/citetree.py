"""Reference tree commands - build and manage citation trees in SQLite."""

import json
import sys
import time
from pathlib import Path
from typing import Annotated, Optional

import httpx
import sqlite_utils
import typer

from ..client import (
    PAPER_FIELDS_FULL,
    get_client,
)
from ..options import (
    EXIT_API_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_RATE_LIMITED,
    ID_FORMATS_HELP,
    ApiKeyOption,
    QuietOption,
    format_api_error,
    is_rate_limit_error,
    resolve_api_key,
)
from ..yaml_config import CitetreeConfig, load_config

# Semantic Scholar API base URL
S2_API_BASE = "https://api.semanticscholar.org/graph/v1"

app = typer.Typer(no_args_is_help=True)

# Fields to fetch for papers in the tree
CITETREE_PAPER_FIELDS = [
    "paperId",
    "externalIds",
    "title",
    "abstract",
    "tldr",
    "year",
    "authors",
    "citationCount",
    "referenceCount",
    "influentialCitationCount",
    "fieldsOfStudy",
    "openAccessPdf",
]

# Fields to request for citations/references (to get isInfluential and intents)
CITATION_FIELDS = ["paperId", "isInfluential", "intents"]

# Batch API limits
BATCH_SIZE = 500

# SQLite has a limit of 999 variables per query, use 500 for safety margin
SQL_BATCH_SIZE = 500


def chunked(iterable, size):
    """Yield successive chunks of the given size from an iterable."""
    items = list(iterable)
    for i in range(0, len(items), size):
        yield items[i : i + size]


def rows_where_batched(table, column: str, values: list, batch_size: int = SQL_BATCH_SIZE):
    """Query rows with IN clause, batching to avoid SQLite variable limits.

    Args:
        table: sqlite_utils table object
        column: Column name to match against
        values: List of values to match
        batch_size: Maximum values per query (default 500)

    Yields:
        Row dicts from all matching batches
    """
    if not values:
        return
    for batch in chunked(values, batch_size):
        query = f"{column} IN ({','.join('?' * len(batch))})"
        yield from table.rows_where(query, batch)


def select_mmr(
    candidates: list[str],
    relevance: dict[str, float],
    candidate_sources: dict[str, set[str]],  # paper_id -> set of source papers it cites/is cited by
    n: int,
    lambda_: float = 0.5,
) -> list[str]:
    """Select papers using Maximal Marginal Relevance.

    Balances relevance (influential count) with diversity (not too similar to already selected).

    Args:
        candidates: List of candidate paper IDs
        relevance: Dict mapping paper_id -> relevance score (e.g., influential count)
        candidate_sources: Dict mapping paper_id -> set of source papers it connects to
                          Used for similarity calculation (Jaccard of sources)
        n: Number of papers to select
        lambda_: Trade-off parameter. 1.0 = pure relevance, 0.0 = pure diversity

    Returns:
        List of selected paper IDs
    """
    if not candidates:
        return []

    selected: list[str] = []
    selected_sources: set[str] = set()  # Union of sources for selected papers
    remaining = set(candidates)

    # Normalize relevance scores to 0-1 range
    max_rel = max(relevance.get(p, 0) for p in candidates) or 1

    while len(selected) < n and remaining:
        best_score = -float('inf')
        best_paper = None

        for p in remaining:
            # Relevance component (normalized)
            rel = relevance.get(p, 0) / max_rel

            # Diversity component: how different is this paper from already selected?
            # Use Jaccard distance of source sets
            p_sources = candidate_sources.get(p, set())
            if selected_sources and p_sources:
                # Jaccard similarity
                intersection = len(p_sources & selected_sources)
                union = len(p_sources | selected_sources)
                similarity = intersection / union if union > 0 else 0
            else:
                similarity = 0

            # MMR score: balance relevance and diversity
            score = lambda_ * rel - (1 - lambda_) * similarity

            if score > best_score:
                best_score = score
                best_paper = p

        if best_paper:
            selected.append(best_paper)
            remaining.remove(best_paper)
            # Update selected sources for diversity calculation
            selected_sources.update(candidate_sources.get(best_paper, set()))

    return selected


def fetch_citations_batch(
    api_key: str | None,
    paper_ids: list[str],
    direction: str = "citations",
) -> dict[str, list[str]]:
    """Fetch citations/references for multiple papers via batch API.

    Uses POST /graph/v1/paper/batch to fetch citations for up to 500 papers
    in a single request.

    Args:
        api_key: API key for authentication
        paper_ids: List of paper IDs to fetch citations for
        direction: "citations" or "references"

    Returns:
        Dict mapping paper_id -> list of citing/cited paper IDs
    """
    if not paper_ids:
        return {}

    # Build the fields parameter
    if direction == "citations":
        fields = "paperId,citations.paperId"
    else:
        fields = "paperId,references.paperId"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    url = f"{S2_API_BASE}/paper/batch"
    params = {"fields": fields}

    result: dict[str, list[str]] = {}

    # Process in batches of BATCH_SIZE
    for i in range(0, len(paper_ids), BATCH_SIZE):
        batch = paper_ids[i : i + BATCH_SIZE]

        # Small delay between batches
        if i > 0:
            time.sleep(1)

        # Retry with exponential backoff
        for attempt in range(3):
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(
                        url,
                        params=params,
                        headers=headers,
                        json={"ids": batch},
                    )
                    response.raise_for_status()
                    data = response.json()

                # Parse response - data is a list matching input order
                for paper_data in data:
                    if paper_data is None:
                        continue
                    paper_id = paper_data.get("paperId")
                    if not paper_id:
                        continue

                    # Extract citation/reference paper IDs
                    related = paper_data.get(direction, []) or []
                    related_ids = []
                    for item in related:
                        if item and item.get("paperId"):
                            related_ids.append(item["paperId"])
                    result[paper_id] = related_ids

                break  # Success, exit retry loop

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - wait and retry
                    wait_time = (attempt + 1) * 5
                    time.sleep(wait_time)
                    if attempt == 2:
                        raise
                else:
                    raise
            except httpx.RequestError:
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)
                if attempt == 2:
                    raise

    return result


def init_db(db_path: Path) -> sqlite_utils.Database:
    """Initialize database with schema if needed."""
    db = sqlite_utils.Database(db_path)

    # Papers table
    if "papers" not in db.table_names():
        db["papers"].create(
            {
                "paper_id": str,
                "title": str,
                "abstract": str,
                "tldr": str,
                "year": int,
                "authors": str,  # JSON
                "citation_count": int,
                "reference_count": int,
                "influential_citation_count": int,
                "fields_of_study": str,  # JSON
                "external_ids": str,  # JSON
            },
            pk="paper_id",
            if_not_exists=True,
        )

    # Paper references (edges)
    if "paper_references" not in db.table_names():
        db["paper_references"].create(
            {
                "citing_id": str,
                "cited_id": str,
                "is_influential": int,  # 0/1
                "intents": str,  # JSON array
            },
            pk=("citing_id", "cited_id"),
            if_not_exists=True,
        )
        db["paper_references"].create_index(["cited_id"], if_not_exists=True)

    # Exploration roots
    if "exploration_roots" not in db.table_names():
        db["exploration_roots"].create(
            {
                "paper_id": str,
                "original_id": str,  # The ID used to add (e.g., PMID:123)
                "depth": int,
                "direction": str,  # "citations" or "references"
                "added_at": str,
            },
            pk="paper_id",
            if_not_exists=True,
        )

    # Enable FTS on papers table for text search
    if "papers_fts" not in db.table_names():
        db["papers"].enable_fts(
            ["title", "abstract", "tldr", "authors"],
            create_triggers=True,
        )

    return db


def paper_to_row(paper) -> dict:
    """Convert a paper object to a database row."""
    raw = paper.raw_data if hasattr(paper, "raw_data") else paper

    tldr = raw.get("tldr")
    if isinstance(tldr, dict):
        tldr = tldr.get("text")

    authors = raw.get("authors")
    if authors:
        authors = json.dumps(authors)

    fields_of_study = raw.get("fieldsOfStudy")
    if fields_of_study:
        fields_of_study = json.dumps(fields_of_study)

    external_ids = raw.get("externalIds")
    if external_ids:
        external_ids = json.dumps(external_ids)

    open_access_pdf = raw.get("openAccessPdf")
    open_access_url = None
    if open_access_pdf and isinstance(open_access_pdf, dict):
        open_access_url = open_access_pdf.get("url")

    return {
        "paper_id": raw.get("paperId"),
        "title": raw.get("title"),
        "abstract": raw.get("abstract"),
        "tldr": tldr,
        "year": raw.get("year"),
        "authors": authors,
        "citation_count": raw.get("citationCount"),
        "reference_count": raw.get("referenceCount"),
        "influential_citation_count": raw.get("influentialCitationCount"),
        "fields_of_study": fields_of_study,
        "external_ids": external_ids,
        "open_access_url": open_access_url,
    }


def citation_to_edge(cited_id: str, citation) -> dict:
    """Convert a citation object to an edge row (paper that cites the given paper)."""
    raw = citation.raw_data if hasattr(citation, "raw_data") else citation
    citing_paper = raw.get("citingPaper", {})

    intents = raw.get("intents")
    if intents:
        intents = json.dumps(intents)

    return {
        "citing_id": citing_paper.get("paperId"),
        "cited_id": cited_id,
        "is_influential": 1 if raw.get("isInfluential") else 0,
        "intents": intents,
    }


def reference_to_edge(citing_id: str, ref) -> dict:
    """Convert a reference object to an edge row (paper that the given paper cites)."""
    raw = ref.raw_data if hasattr(ref, "raw_data") else ref
    cited_paper = raw.get("citedPaper", {})

    intents = raw.get("intents")
    if intents:
        intents = json.dumps(intents)

    return {
        "citing_id": citing_id,
        "cited_id": cited_paper.get("paperId"),
        "is_influential": 1 if raw.get("isInfluential") else 0,
        "intents": intents,
    }


def crawl_tree(
    client,
    api_key: str | None,
    db: sqlite_utils.Database,
    paper_ids: list[str],
    max_depth: int,
    direction: str = "citations",
    influential_only: bool = False,
    limit: int | None = None,
    quiet: bool = False,
) -> tuple[set[str], int]:
    """Crawl citation/reference tree using batch API.

    Uses level-based batching for efficient fetching. Stores all edges
    with is_influential=NULL (batch API doesn't provide this).

    For --influential-only mode, filters traversal to papers with
    influentialCitationCount > 0 (as a proxy since batch API doesn't
    provide per-edge isInfluential).

    Args:
        client: SemanticScholar client
        api_key: API key for batch requests
        db: Database connection
        paper_ids: Starting paper IDs
        max_depth: Maximum traversal depth
        direction: "citations" (up - papers citing this) or "references" (down - papers this cites)
        influential_only: Filter traversal to influential papers only
        limit: Max papers per level (only top N by influential count)
        quiet: Suppress progress output

    Returns:
        Tuple of (all_paper_ids, edges_added)
    """
    all_paper_ids: set[str] = set(paper_ids)
    edges_added = 0

    # For citations: we look up papers by cited_id (papers that cite this one)
    # For references: we look up papers by citing_id (papers this one cites)
    if direction == "citations":
        cache_column = "cited_id"
        next_column = "citing_id"
        label = "citations"
    else:
        cache_column = "citing_id"
        next_column = "cited_id"
        label = "references"

    # Level-based traversal
    current_level = set(paper_ids)
    visited: set[str] = set()

    for depth in range(max_depth):
        # Find papers at this level that we haven't fetched yet
        to_fetch = []
        cached_papers = []

        for paper_id in current_level:
            if paper_id in visited:
                continue

            # Check if we already have edges for this paper
            existing_edges = list(
                db["paper_references"].rows_where(f"{cache_column} = ?", [paper_id], limit=1)
            )
            if existing_edges:
                cached_papers.append(paper_id)
            else:
                to_fetch.append(paper_id)

        if not to_fetch and not cached_papers:
            break

        # Build citations_per_source: maps source paper -> list of citing/cited papers
        citations_per_source: dict[str, list[str]] = {}

        # Process cached papers
        for paper_id in cached_papers:
            visited.add(paper_id)
            citations_per_source[paper_id] = []
            for edge in db["paper_references"].rows_where(f"{cache_column} = ?", [paper_id]):
                next_id = edge[next_column]
                if next_id:
                    all_paper_ids.add(next_id)
                    citations_per_source[paper_id].append(next_id)

        if cached_papers and not quiet:
            print(f"  [depth {depth}] Using {len(cached_papers)} cached papers", file=sys.stderr)

        # Fetch from API in batch
        if to_fetch:
            if not quiet:
                print(f"  [depth {depth}] Fetching {label} for {len(to_fetch)} papers...", file=sys.stderr)

            try:
                citations_map = fetch_citations_batch(api_key, to_fetch, direction)
            except Exception as e:
                if not quiet:
                    print(f"  Warning: Batch fetch failed: {e}", file=sys.stderr)
                citations_map = {}

            # Store edges and collect per-source citations
            total_edges = 0

            for paper_id in to_fetch:
                visited.add(paper_id)
                related_ids = citations_map.get(paper_id, [])
                citations_per_source[paper_id] = related_ids

                # Create edges with is_influential=NULL
                edges = []
                for related_id in related_ids:
                    if direction == "citations":
                        edge = {
                            "citing_id": related_id,
                            "cited_id": paper_id,
                            "is_influential": None,
                            "intents": None,
                        }
                    else:
                        edge = {
                            "citing_id": paper_id,
                            "cited_id": related_id,
                            "is_influential": None,
                            "intents": None,
                        }
                    edges.append(edge)
                    all_paper_ids.add(related_id)

                if edges:
                    db["paper_references"].upsert_all(edges, pk=("citing_id", "cited_id"))
                    edges_added += len(edges)
                    total_edges += len(edges)

            if not quiet:
                print(f"  [depth {depth}] Found {total_edges} {label}", file=sys.stderr)

        # Apply MMR selection: balance relevance (influential count) with diversity
        if limit and citations_per_source:
            # Collect all unique candidates (excluding visited)
            all_candidates = set()
            # Build candidate_sources: which source papers does each candidate connect to
            candidate_sources: dict[str, set[str]] = {}
            for source_id, citations in citations_per_source.items():
                for c in citations:
                    if c not in visited:
                        all_candidates.add(c)
                        if c not in candidate_sources:
                            candidate_sources[c] = set()
                        candidate_sources[c].add(source_id)

            if not quiet:
                print(f"  [depth {depth}→{depth+1}] MMR selecting from {len(all_candidates)} candidates...", file=sys.stderr)

            # Fetch influential counts for all candidates (used as relevance score)
            influential_counts = fetch_influential_counts(api_key, list(all_candidates), quiet=True)

            # Calculate budget for this level
            max_per_level = limit // max_depth if max_depth > 0 else limit

            # Use MMR to select diverse, relevant papers
            # lambda=0.7 favors relevance slightly over diversity
            selected_papers = select_mmr(
                candidates=list(all_candidates),
                relevance=influential_counts,
                candidate_sources=candidate_sources,
                n=max_per_level,
                lambda_=0.7,
            )
            next_level = set(selected_papers)

            # Prune edges for non-selected papers
            edges_kept = 0
            edges_dropped = 0

            for source_id, citations in citations_per_source.items():
                for cand in citations:
                    if cand in visited:
                        continue
                    if cand in next_level:
                        edges_kept += 1
                    else:
                        edges_dropped += 1
                        # Remove edge from database
                        if direction == "citations":
                            db.execute(
                                "DELETE FROM paper_references WHERE citing_id = ? AND cited_id = ?",
                                [cand, source_id]
                            )
                        else:
                            db.execute(
                                "DELETE FROM paper_references WHERE citing_id = ? AND cited_id = ?",
                                [source_id, cand]
                            )
                        # Remove from all_paper_ids so we don't fetch details
                        all_paper_ids.discard(cand)

            if not quiet:
                print(
                    f"  [depth {depth}→{depth+1}] Selected {len(next_level)} papers (MMR λ=0.7, budget {max_per_level})",
                    file=sys.stderr,
                )
                print(
                    f"  [depth {depth}→{depth+1}] Kept {edges_kept} edges, dropped {edges_dropped} low-relevance/redundant edges",
                    file=sys.stderr,
                )
        else:
            # No limit - just combine all
            next_level = set()
            for citations in citations_per_source.values():
                next_level.update(c for c in citations if c not in visited)

        current_level = next_level

    return all_paper_ids, edges_added


def fetch_influential_counts(
    api_key: str | None,
    paper_ids: list[str],
    quiet: bool = False,
) -> dict[str, int]:
    """Fetch influentialCitationCount for papers.

    Args:
        api_key: API key for authentication
        paper_ids: List of paper IDs to check
        quiet: Suppress progress output

    Returns:
        Dict mapping paper_id -> influentialCitationCount (including 0).
    """
    if not paper_ids:
        return {}

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    url = f"{S2_API_BASE}/paper/batch"
    params = {"fields": "paperId,influentialCitationCount"}

    paper_counts: dict[str, int] = {}

    for i in range(0, len(paper_ids), BATCH_SIZE):
        batch = paper_ids[i : i + BATCH_SIZE]

        if i > 0:
            time.sleep(0.5)  # Shorter delay since smaller payloads

        for attempt in range(3):
            try:
                with httpx.Client(timeout=60.0) as client:
                    response = client.post(
                        url,
                        params=params,
                        headers=headers,
                        json={"ids": batch},
                    )
                    response.raise_for_status()
                    data = response.json()

                for paper_data in data:
                    if paper_data is None:
                        continue
                    paper_id = paper_data.get("paperId")
                    count = paper_data.get("influentialCitationCount") or 0
                    if paper_id:
                        paper_counts[paper_id] = count

                break

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    wait_time = (attempt + 1) * 5
                    time.sleep(wait_time)
                    if attempt == 2:
                        raise
                else:
                    raise
            except httpx.RequestError:
                wait_time = (attempt + 1) * 5
                time.sleep(wait_time)
                if attempt == 2:
                    raise

    return paper_counts


def fetch_missing_papers(
    client,
    db: sqlite_utils.Database,
    paper_ids: set[str],
    quiet: bool = False,
) -> int:
    """Fetch papers not yet in the database."""
    # Find which papers we don't have
    existing = set(
        row["paper_id"]
        for row in rows_where_batched(db["papers"], "paper_id", list(paper_ids))
    ) if paper_ids else set()

    missing = paper_ids - existing

    if not missing:
        if not quiet:
            print(f"All {len(paper_ids)} papers already in database", file=sys.stderr)
        return 0

    if not quiet:
        print(f"Fetching {len(missing)} missing papers...", file=sys.stderr)

    # Fetch in batches - API allows up to 500 papers per request
    missing_list = list(missing)
    batch_size = 500
    fetched = 0
    failed = []

    for i in range(0, len(missing_list), batch_size):
        batch = missing_list[i : i + batch_size]

        # Small delay between batches to avoid rate limits
        if i > 0:
            time.sleep(1)

        # Retry with exponential backoff for rate limits
        for attempt in range(3):
            try:
                papers = client.get_papers(batch, fields=CITETREE_PAPER_FIELDS)
                rows = []
                for paper in papers:
                    if paper:
                        rows.append(paper_to_row(paper))

                if rows:
                    db["papers"].upsert_all(rows, pk="paper_id")
                    fetched += len(rows)

                if not quiet:
                    print(f"  Fetched {fetched}/{len(missing)} papers", file=sys.stderr)
                break  # Success, exit retry loop

            except Exception as e:
                # Retry with backoff for any error (rate limits, connection errors, etc.)
                wait_time = (attempt + 1) * 5
                if not quiet:
                    print(f"  Batch failed ({type(e).__name__}), retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
                if attempt == 2:  # Last attempt failed
                    failed.extend(batch)

    if failed and not quiet:
        print(f"  Warning: {len(failed)} papers could not be fetched", file=sys.stderr)

    return fetched


@app.command()
def add(
    paper_ids: Annotated[
        Optional[list[str]],
        typer.Argument(help=f"Paper IDs to use as roots. {ID_FORMATS_HELP}"),
    ] = None,
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            "-d",
            help="SQLite database path",
        ),
    ] = None,
    config: Annotated[
        Optional[Path],
        typer.Option(
            "--config",
            "-c",
            help="YAML config file with papers and settings",
        ),
    ] = None,
    depth: Annotated[
        Optional[int],
        typer.Option(
            "--depth",
            help="Maximum traversal depth",
        ),
    ] = None,
    direction: Annotated[
        Optional[str],
        typer.Option(
            "--direction",
            help="Traversal direction: citations (up, default) or references (down)",
        ),
    ] = None,
    limit: Annotated[
        Optional[int],
        typer.Option(
            "--limit",
            "-l",
            help="Maximum citations/references per paper (API max: 1000)",
        ),
    ] = None,
    influential_only: Annotated[
        Optional[bool],
        typer.Option(
            "--influential-only",
            "-I",
            help="Only traverse papers with influentialCitationCount > 0",
        ),
    ] = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Add paper(s) as roots and crawl their citation trees.

    By default, crawls citations (papers that cite the root - going up/forward in time).
    Use --direction references to crawl references (papers the root cites - going down/backward).

    Uses batch API for efficient fetching. Stores all edges at each level.
    With --influential-only, filters traversal to papers with influentialCitationCount > 0.

    Examples:
        s2cli citetree add PMID:12345678 --db papers.db --depth 2
        s2cli citetree add arXiv:1706.03762 --db papers.db --direction references
        s2cli citetree add --config citetree.yaml --db papers.db
    """
    # Load config file if provided
    cfg = CitetreeConfig()
    if config:
        if not config.exists():
            print(f"Config file not found: {config}", file=sys.stderr)
            raise typer.Exit(EXIT_INPUT_ERROR)
        try:
            cfg = load_config(config)
            if not quiet:
                print(f"Loaded config from {config}", file=sys.stderr)
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            raise typer.Exit(EXIT_INPUT_ERROR)

    # Merge CLI args with config (CLI takes precedence)
    final_depth = depth if depth is not None else cfg.depth
    final_direction = direction if direction is not None else cfg.direction
    final_limit = limit if limit is not None else cfg.limit
    final_influential_only = influential_only if influential_only is not None else cfg.influential_only

    # Combine papers from config and CLI args
    final_paper_ids = list(cfg.papers)
    if paper_ids:
        final_paper_ids.extend(paper_ids)

    # Validate we have required inputs
    if not final_paper_ids:
        print("Error: No paper IDs provided. Use positional args or --config with papers list.", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    if db is None:
        print("Error: --db is required", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    if final_direction not in ("citations", "references"):
        print(f"Error: direction must be 'citations' or 'references'", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    client = get_client(resolve_api_key(api_key))
    database = init_db(db)

    if not quiet:
        print(f"Database: {db}", file=sys.stderr)
        print(f"Adding {len(final_paper_ids)} root(s) with depth {final_depth} ({final_direction})", file=sys.stderr)

    # Resolve paper IDs to S2 paper IDs using batch API
    resolved_roots = []
    try:
        papers = client.get_papers(final_paper_ids, fields=["paperId", "externalIds"])
        for pid, paper in zip(final_paper_ids, papers):
            if paper and paper.paperId:
                resolved_roots.append((pid, paper.paperId))
                if not quiet:
                    print(f"Resolved {pid} -> {paper.paperId}", file=sys.stderr)
            else:
                print(f"Warning: Could not resolve {pid}", file=sys.stderr)
    except Exception as e:
        print(f"Error resolving paper IDs: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_API_ERROR)

    if not resolved_roots:
        print("No valid paper IDs provided", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    # Record roots
    from datetime import datetime
    for original_id, s2_id in resolved_roots:
        database["exploration_roots"].upsert(
            {
                "paper_id": s2_id,
                "original_id": original_id,
                "depth": final_depth,
                "direction": final_direction,
                "added_at": datetime.now().isoformat(),
            },
            pk="paper_id",
        )

    # Crawl tree
    if not quiet:
        print(f"\nCrawling {final_direction} tree...", file=sys.stderr)

    resolved_api_key = resolve_api_key(api_key)
    try:
        root_s2_ids = [s2_id for _, s2_id in resolved_roots]
        all_papers, edges_added = crawl_tree(
            client, resolved_api_key, database, root_s2_ids, final_depth, final_direction, final_influential_only, final_limit, quiet
        )
    except Exception as e:
        if is_rate_limit_error(e):
            print(f"Rate limited: {format_api_error(e)}", file=sys.stderr)
            raise typer.Exit(EXIT_RATE_LIMITED)
        print(f"Error during crawl: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_API_ERROR)

    # Fetch missing papers
    if not quiet:
        print(f"\nFetching paper details...", file=sys.stderr)

    try:
        papers_fetched = fetch_missing_papers(client, database, all_papers, quiet)
    except Exception as e:
        if is_rate_limit_error(e):
            print(f"Rate limited: {format_api_error(e)}", file=sys.stderr)
            raise typer.Exit(EXIT_RATE_LIMITED)
        print(f"Error fetching papers: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_API_ERROR)

    # Summary
    if not quiet:
        total_papers = database["papers"].count
        total_edges = database["paper_references"].count
        total_roots = database["exploration_roots"].count
        print(f"\nDone!", file=sys.stderr)
        print(f"  Roots: {total_roots}", file=sys.stderr)
        print(f"  Papers: {total_papers}", file=sys.stderr)
        print(f"  Edges: {total_edges}", file=sys.stderr)


@app.command()
def roots(
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            "-d",
            help="SQLite database path",
        ),
    ],
):
    """List exploration roots in the database.

    Examples:
        s2cli citetree roots --db papers.db
    """
    if not db.exists():
        print(f"Database not found: {db}", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    database = sqlite_utils.Database(db)

    if "exploration_roots" not in database.table_names():
        print("No roots table found", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    roots_list = list(database["exploration_roots"].rows)

    if not roots_list:
        print("No roots in database", file=sys.stderr)
        return

    # Get paper titles for roots
    root_ids = [r["paper_id"] for r in roots_list]
    titles = {}
    if "papers" in database.table_names():
        for row in rows_where_batched(database["papers"], "paper_id", root_ids):
            titles[row["paper_id"]] = row["title"]

    print(f"Roots ({len(roots_list)}):\n")
    for root in roots_list:
        title = titles.get(root["paper_id"], "(title not fetched)")
        direction = root.get("direction", "references")  # default for old DBs
        print(f"  {root['original_id']}")
        print(f"    S2 ID: {root['paper_id']}")
        print(f"    Title: {title[:60]}..." if len(title) > 60 else f"    Title: {title}")
        print(f"    Depth: {root['depth']} ({direction})")
        print(f"    Added: {root['added_at']}")
        print()


@app.command()
def status(
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            "-d",
            help="SQLite database path",
        ),
    ],
):
    """Show database statistics.

    Examples:
        s2cli citetree status --db papers.db
    """
    if not db.exists():
        print(f"Database not found: {db}", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    database = sqlite_utils.Database(db)

    roots_count = database["exploration_roots"].count if "exploration_roots" in database.table_names() else 0
    papers_count = database["papers"].count if "papers" in database.table_names() else 0
    edges_count = database["paper_references"].count if "paper_references" in database.table_names() else 0

    # Count edges by type
    influential_count = 0
    batch_count = 0
    if "paper_references" in database.table_names():
        result = database.execute("SELECT COUNT(*) FROM paper_references WHERE is_influential = 1").fetchone()
        influential_count = result[0] if result else 0
        result = database.execute("SELECT COUNT(*) FROM paper_references WHERE is_influential IS NULL").fetchone()
        batch_count = result[0] if result else 0

    print(f"Database: {db}")
    print(f"  Roots: {roots_count}")
    print(f"  Papers: {papers_count}")
    if batch_count > 0 and influential_count > 0:
        print(f"  Edges: {edges_count} ({influential_count} influential, {batch_count} from batch)")
    elif batch_count > 0:
        print(f"  Edges: {edges_count} (from batch API)")
    else:
        print(f"  Edges: {edges_count} ({influential_count} influential)")


@app.command()
def refresh(
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            "-d",
            help="SQLite database path",
        ),
    ],
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Re-fetch paper details for all papers in the database.

    Use this to update papers with new fields (e.g., openAccessPdf) without
    re-crawling the citation tree. Handles schema changes by adding new columns.

    Examples:
        s2cli citetree refresh --db papers.db
    """
    if not db.exists():
        print(f"Database not found: {db}", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    database = sqlite_utils.Database(db)

    if "papers" not in database.table_names():
        print("No papers table found", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    # Get all paper IDs
    paper_ids = [row["paper_id"] for row in database["papers"].rows_where(select="paper_id")]

    if not paper_ids:
        print("No papers in database", file=sys.stderr)
        return

    if not quiet:
        print(f"Refreshing {len(paper_ids)} papers...", file=sys.stderr)

    client = get_client(api_key)

    batch_size = 500
    fetched = 0
    failed = []

    for i in range(0, len(paper_ids), batch_size):
        batch = paper_ids[i : i + batch_size]

        # Small delay between batches to avoid rate limits
        if i > 0:
            time.sleep(1)

        # Retry with exponential backoff for rate limits
        for attempt in range(3):
            try:
                papers = client.get_papers(batch, fields=CITETREE_PAPER_FIELDS)
                rows = []
                for paper in papers:
                    if paper:
                        rows.append(paper_to_row(paper))

                if rows:
                    # Use alter=True to add any new columns automatically
                    database["papers"].upsert_all(rows, pk="paper_id", alter=True)
                    fetched += len(rows)

                if not quiet:
                    print(f"  Refreshed {fetched}/{len(paper_ids)} papers", file=sys.stderr)
                break  # Success, exit retry loop

            except Exception as e:
                # Retry with backoff for any error (rate limits, connection errors, etc.)
                wait_time = (attempt + 1) * 5
                if not quiet:
                    print(f"  Batch failed ({type(e).__name__}), retrying in {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)
                if attempt == 2:  # Last attempt failed
                    failed.extend(batch)

    if failed and not quiet:
        print(f"  Warning: {len(failed)} papers could not be refreshed", file=sys.stderr)

    if not quiet:
        print(f"\nDone! Refreshed {fetched} papers.", file=sys.stderr)
