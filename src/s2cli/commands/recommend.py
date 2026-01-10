"""Recommend commands - get paper recommendations."""

import sys
from itertools import islice
from typing import Annotated, Optional

import typer

from ..client import PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL, get_client, parse_fields
from ..options import (
    EXIT_API_ERROR,
    EXIT_RATE_LIMITED,
    ID_FORMATS_HELP,
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


@app.command("for-paper")
def for_paper(
    paper_id: Annotated[
        str,
        typer.Argument(help=f"Paper ID to base recommendations on. {ID_FORMATS_HELP}"),
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
            help="Maximum number of recommendations",
        ),
    ] = 10,
    pool: Annotated[
        Optional[str],
        typer.Option(
            "--pool",
            help="Recommendation pool: recent, all-cs",
        ),
    ] = None,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get recommendations based on a single paper.

    Examples:
        s2cli recommend for-paper 649def34f8be52c8b66281af98ae884c09aef38b
        s2cli recommend for-paper arXiv:1706.03762 --fields title,tldr,year --limit 5
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.get_recommended_papers(
            paper_id,
            fields=field_list,
            limit=limit,
            pool_from=pool,
        )
        papers_list = list(islice(results, limit))
        print_output(papers_list, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            print(f"Error: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)


@app.command("for-papers")
def for_papers(
    paper_ids: Annotated[
        list[str],
        typer.Argument(help=f"Paper IDs to base recommendations on. {ID_FORMATS_HELP}"),
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
            help="Maximum number of recommendations",
        ),
    ] = 10,
    pool: Annotated[
        Optional[str],
        typer.Option(
            "--pool",
            help="Recommendation pool: recent, all-cs",
        ),
    ] = None,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get recommendations based on multiple papers.

    Examples:
        s2cli recommend for-papers arXiv:1706.03762 arXiv:2103.14030 --limit 5
        s2cli recommend for-papers arXiv:1706.03762 arXiv:2103.14030 --fields title,tldr
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.get_recommended_papers_from_lists(
            positive_paper_ids=paper_ids,
            fields=field_list,
            limit=limit,
            pool_from=pool,
        )
        papers_list = list(islice(results, limit))
        print_output(papers_list, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            print(f"Error: {format_api_error(e)}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)
