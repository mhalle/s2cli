"""Reference tree commands - build and manage citation trees in SQLite."""

import json
import sys
from pathlib import Path
from typing import Annotated, Optional

import sqlite_utils
import typer

from ..client import (
    PAPER_FIELDS_FULL,
    get_client,
    safe_iterate,
)
from ..options import (
    EXIT_API_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_RATE_LIMITED,
    ID_FORMATS_HELP,
    ApiKeyOption,
    QuietOption,
    format_api_error,
    is_empty_results_error,
    is_rate_limit_error,
    resolve_api_key,
)

app = typer.Typer(no_args_is_help=True)

# Fields to fetch for papers in the tree
REFTREE_PAPER_FIELDS = [
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
]

# Fields to request for citations/references (to get isInfluential and intents)
CITATION_FIELDS = ["paperId", "isInfluential", "intents"]


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
    db: sqlite_utils.Database,
    paper_ids: list[str],
    max_depth: int,
    direction: str = "citations",
    limit: int = 1000,
    influential_only: bool = False,
    quiet: bool = False,
) -> tuple[set[str], int]:
    """Crawl citation/reference tree using hybrid approach.

    Stores all edges at each level (or only influential if influential_only),
    but only traverses into influential ones.

    Args:
        client: SemanticScholar client
        db: Database connection
        paper_ids: Starting paper IDs
        max_depth: Maximum traversal depth
        direction: "citations" (up - papers citing this) or "references" (down - papers this cites)
        limit: Maximum citations/references to fetch per paper
        influential_only: Only store influential edges
        quiet: Suppress progress output

    Returns:
        Tuple of (all_paper_ids, edges_added)
    """
    all_paper_ids: set[str] = set()
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

    # Queue: (paper_id, current_depth)
    queue: list[tuple[str, int]] = [(pid, 0) for pid in paper_ids]
    visited: set[str] = set()

    while queue:
        paper_id, depth = queue.pop(0)

        if paper_id in visited:
            continue
        visited.add(paper_id)
        all_paper_ids.add(paper_id)

        if depth >= max_depth:
            continue

        # Check if we already have edges for this paper
        existing_edges = list(db["paper_references"].rows_where(
            f"{cache_column} = ?", [paper_id], limit=1
        ))

        if existing_edges:
            # Already crawled this paper, get influential edges from DB
            if not quiet:
                print(f"  [depth {depth}] {paper_id}: using cached edges", file=sys.stderr)
            for edge in db["paper_references"].rows_where(f"{cache_column} = ?", [paper_id]):
                all_paper_ids.add(edge[next_column])
                if edge["is_influential"]:
                    queue.append((edge[next_column], depth + 1))
            continue

        # Fetch from API
        if not quiet:
            print(f"  [depth {depth}] {paper_id}: fetching {label}...", file=sys.stderr)

        try:
            if direction == "citations":
                results = client.get_paper_citations(
                    paper_id,
                    fields=CITATION_FIELDS,
                    limit=limit,
                )
            else:
                results = client.get_paper_references(
                    paper_id,
                    fields=CITATION_FIELDS,
                    limit=limit,
                )
            results_list = safe_iterate(results, limit)
        except Exception as e:
            if is_empty_results_error(e):
                results_list = []
            else:
                raise

        # Store edges (all or influential only), queue only influential ones
        edges = []
        influential_count = 0
        total_count = 0
        for item in results_list:
            if direction == "citations":
                edge = citation_to_edge(paper_id, item)
                next_id = edge["citing_id"]
            else:
                edge = reference_to_edge(paper_id, item)
                next_id = edge["cited_id"]

            if next_id:  # Some may not have paperId
                total_count += 1
                is_influential = edge["is_influential"]
                if is_influential:
                    influential_count += 1

                # Store edge if not filtering or if influential
                if not influential_only or is_influential:
                    edges.append(edge)
                    all_paper_ids.add(next_id)

                # Only traverse influential
                if is_influential:
                    queue.append((next_id, depth + 1))

        if edges:
            db["paper_references"].upsert_all(edges, pk=("citing_id", "cited_id"))
            edges_added += len(edges)

        if not quiet:
            if influential_only:
                print(
                    f"  [depth {depth}] {paper_id}: {influential_count} influential "
                    f"(of {total_count} {label})",
                    file=sys.stderr,
                )
            else:
                print(
                    f"  [depth {depth}] {paper_id}: {total_count} {label} "
                    f"({influential_count} influential)",
                    file=sys.stderr,
                )

    return all_paper_ids, edges_added


def fetch_missing_papers(
    client,
    db: sqlite_utils.Database,
    paper_ids: set[str],
    quiet: bool = False,
) -> int:
    """Fetch papers not yet in the database."""
    import time

    # Find which papers we don't have
    existing = set(
        row["paper_id"]
        for row in db["papers"].rows_where(
            "paper_id IN ({})".format(",".join("?" * len(paper_ids))),
            list(paper_ids),
        )
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
                papers = client.get_papers(batch, fields=REFTREE_PAPER_FIELDS)
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
        list[str],
        typer.Argument(help=f"Paper IDs to use as roots. {ID_FORMATS_HELP}"),
    ],
    db: Annotated[
        Path,
        typer.Option(
            "--db",
            "-d",
            help="SQLite database path",
        ),
    ],
    depth: Annotated[
        int,
        typer.Option(
            "--depth",
            help="Maximum traversal depth",
        ),
    ] = 2,
    direction: Annotated[
        str,
        typer.Option(
            "--direction",
            help="Traversal direction: citations (up, default) or references (down)",
        ),
    ] = "citations",
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum citations/references per paper (API max: 1000)",
        ),
    ] = 1000,
    influential_only: Annotated[
        bool,
        typer.Option(
            "--influential-only",
            "-I",
            help="Only store influential edges (always traverses influential only)",
        ),
    ] = False,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Add paper(s) as roots and crawl their citation trees.

    By default, crawls citations (papers that cite the root - going up/forward in time).
    Use --direction references to crawl references (papers the root cites - going down/backward).

    Uses hybrid crawl: stores all edges at each level, but only
    traverses into influential ones.

    Examples:
        s2cli citetree add PMID:12345678 --db papers.db --depth 2
        s2cli citetree add arXiv:1706.03762 --db papers.db --direction references
    """
    if direction not in ("citations", "references"):
        print(f"Error: direction must be 'citations' or 'references'", file=sys.stderr)
        raise typer.Exit(EXIT_INPUT_ERROR)

    client = get_client(resolve_api_key(api_key))
    database = init_db(db)

    if not quiet:
        print(f"Database: {db}", file=sys.stderr)
        print(f"Adding {len(paper_ids)} root(s) with depth {depth} ({direction})", file=sys.stderr)

    # First, resolve paper IDs to S2 paper IDs
    resolved_roots = []
    for pid in paper_ids:
        try:
            paper = client.get_paper(pid, fields=["paperId"])
            if paper and paper.paperId:
                resolved_roots.append((pid, paper.paperId))
                if not quiet:
                    print(f"Resolved {pid} -> {paper.paperId}", file=sys.stderr)
            else:
                print(f"Warning: Could not resolve {pid}", file=sys.stderr)
        except Exception as e:
            print(f"Error resolving {pid}: {format_api_error(e)}", file=sys.stderr)
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
                "depth": depth,
                "direction": direction,
                "added_at": datetime.now().isoformat(),
            },
            pk="paper_id",
        )

    # Crawl tree
    if not quiet:
        print(f"\nCrawling {direction} tree...", file=sys.stderr)

    try:
        root_s2_ids = [s2_id for _, s2_id in resolved_roots]
        all_papers, edges_added = crawl_tree(
            client, database, root_s2_ids, depth, direction, limit, influential_only, quiet
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
        for row in database["papers"].rows_where(
            "paper_id IN ({})".format(",".join("?" * len(root_ids))),
            root_ids,
        ):
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

    # Count influential edges
    influential_count = 0
    if "paper_references" in database.table_names():
        result = database.execute("SELECT COUNT(*) FROM paper_references WHERE is_influential = 1").fetchone()
        influential_count = result[0] if result else 0

    print(f"Database: {db}")
    print(f"  Roots: {roots_count}")
    print(f"  Papers: {papers_count}")
    print(f"  Edges: {edges_count} ({influential_count} influential)")
