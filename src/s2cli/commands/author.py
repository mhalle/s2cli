"""Author commands - query individual authors."""

import sys
from typing import Annotated, Optional

import typer

from ..client import (
    AUTHOR_FIELDS_DEFAULT,
    AUTHOR_FIELDS_FULL,
    PAPER_FIELDS_DEFAULT,
    PAPER_FIELDS_FULL,
    get_client,
    parse_fields,
    safe_iterate,
)
from ..options import (
    AUTHOR_FIELDS_HELP,
    EXIT_API_ERROR,
    EXIT_NOT_FOUND,
    EXIT_RATE_LIMITED,
    PAPER_FIELDS_HELP,
    ApiKeyOption,
    FormatOption,
    OutputFormat,
    QuietOption,
    format_api_error,
    is_rate_limit_error,
    resolve_api_key,
    resolve_format,
)
from ..output import print_output

app = typer.Typer(no_args_is_help=True)


@app.command()
def get(
    author_id: Annotated[
        str,
        typer.Argument(help="Semantic Scholar author ID"),
    ],
    fields: Annotated[
        Optional[str],
        typer.Option(
            "--fields",
            "-F",
            help=AUTHOR_FIELDS_HELP,
        ),
    ] = None,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get an author by ID.

    Examples:
        s2cli author get 1741101
        s2cli author get 1741101 --fields name,hIndex,citationCount,affiliations
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, AUTHOR_FIELDS_DEFAULT, AUTHOR_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        author = client.get_author(author_id, fields=field_list)
        if author:
            print_output(author, fmt=output_format, fields=field_list if fields else None)
        else:
            if not quiet:
                print(f"Author not found: {author_id}", file=sys.stderr)
            raise typer.Exit(EXIT_NOT_FOUND)
    except typer.Exit:
        raise
    except Exception as e:
        if not quiet:
            print(f"Error: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)


@app.command()
def papers(
    author_id: Annotated[
        str,
        typer.Argument(help="Semantic Scholar author ID"),
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
            help="Maximum number of papers to return",
        ),
    ] = 100,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get papers by an author.

    Examples:
        s2cli author papers 1741101 --limit 20
        s2cli author papers 1741101 --fields title,year,venue,citationCount
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.get_author_papers(author_id, fields=field_list, limit=1000)
        # Only take the number we actually want
        papers_list = safe_iterate(results, limit)
        print_output(papers_list, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            print(f"Error: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)
