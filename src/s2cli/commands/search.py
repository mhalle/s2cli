"""Search commands - search papers and authors."""

import sys
from itertools import islice
from typing import Annotated, Optional

import typer

from ..client import (
    AUTHOR_FIELDS_DEFAULT,
    AUTHOR_FIELDS_FULL,
    PAPER_FIELDS_DEFAULT,
    PAPER_FIELDS_FULL,
    get_client,
    parse_fields,
)
from ..options import (
    AUTHOR_FIELDS_HELP,
    EXIT_API_ERROR,
    EXIT_RATE_LIMITED,
    PAPER_FIELDS_HELP,
    ApiKeyOption,
    FormatOption,
    OutputFormat,
    QuietOption,
    is_rate_limit_error,
    resolve_api_key,
    resolve_format,
)
from ..output import print_output

app = typer.Typer(no_args_is_help=True)


@app.command()
def papers(
    query: Annotated[
        str,
        typer.Argument(help="Search query"),
    ],
    fields: Annotated[
        Optional[str],
        typer.Option(
            "--fields",
            "-F",
            help=PAPER_FIELDS_HELP,
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of results",
        ),
    ] = 10,
    year: Annotated[
        Optional[str],
        typer.Option(
            "--year",
            "-y",
            help="Year filter (e.g., 2020, 2018-2022, 2020-)",
        ),
    ] = None,
    venue: Annotated[
        Optional[str],
        typer.Option(
            "--venue",
            help="Filter by venue/journal",
        ),
    ] = None,
    open_access: Annotated[
        bool,
        typer.Option(
            "--open-access",
            help="Only open access papers",
        ),
    ] = False,
    fields_of_study: Annotated[
        Optional[str],
        typer.Option(
            "--fields-of-study",
            help="Filter by field (Computer Science, Medicine, etc.)",
        ),
    ] = None,
    min_citations: Annotated[
        Optional[int],
        typer.Option(
            "--min-citations",
            help="Minimum citation count",
        ),
    ] = None,
    publication_types: Annotated[
        Optional[str],
        typer.Option(
            "--publication-types",
            help="Filter by type (Review, JournalArticle, Conference)",
        ),
    ] = None,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Search for papers by keyword/phrase.

    Examples:
        s2cli search papers "transformer attention mechanism" --limit 20
        s2cli search papers "CRISPR" --year 2020-2024 --min-citations 100
        s2cli search papers "climate change" --fields-of-study "Environmental Science"
        s2cli search papers "neural networks" --open-access --fields title,abstract,tldr
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.search_paper(
            query,
            fields=field_list,
            limit=100,  # Page size (max allowed)
            year=year,
            venue=venue,
            open_access_pdf=open_access if open_access else None,
            fields_of_study=[fields_of_study] if fields_of_study else None,
            min_citation_count=min_citations,
            publication_types=[publication_types] if publication_types else None,
        )
        # Only take the number of results we actually want
        papers_list = list(islice(results, limit))
        print_output(papers_list, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            if is_rate_limit_error(e):
                print("Error: Rate limited. Wait a moment and retry, or set S2_API_KEY.", file=sys.stderr)
            else:
                print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)


@app.command()
def authors(
    query: Annotated[
        str,
        typer.Argument(help="Author name to search for"),
    ],
    fields: Annotated[
        Optional[str],
        typer.Option(
            "--fields",
            "-F",
            help=AUTHOR_FIELDS_HELP,
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum number of results",
        ),
    ] = 10,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Search for authors by name.

    Examples:
        s2cli search authors "Yann LeCun" --limit 5
        s2cli search authors "Geoffrey Hinton" --fields name,hIndex,paperCount
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, AUTHOR_FIELDS_DEFAULT, AUTHOR_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.search_author(query, fields=field_list, limit=100)
        # Only take the number of results we actually want
        authors_list = list(islice(results, limit))
        print_output(authors_list, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            if is_rate_limit_error(e):
                print("Error: Rate limited. Wait a moment and retry, or set S2_API_KEY.", file=sys.stderr)
            else:
                print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)
