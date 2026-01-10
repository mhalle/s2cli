"""Paper commands - query individual papers."""

import sys
from itertools import islice
from typing import Annotated, Optional

import typer

from ..client import PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL, get_client, parse_fields
from ..options import (
    EXIT_API_ERROR,
    EXIT_NOT_FOUND,
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
def get(
    paper_id: Annotated[
        str,
        typer.Argument(
            help="Paper ID (S2ID, DOI, ArXiv:xxx, PMID:xxx, ACL:xxx, CorpusId:xxx)"
        ),
    ],
    fields: Annotated[
        Optional[str],
        typer.Option(
            "--fields",
            "-F",
            help=PAPER_FIELDS_HELP,
        ),
    ] = None,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get a paper by ID.

    Accepts multiple ID formats:
    - S2 Paper ID: 649def34f8be52c8b66281af98ae884c09aef38b
    - DOI: 10.1038/nature12373
    - ArXiv: arXiv:2103.14030
    - PMID: PMID:12345678
    - ACL: ACL:P18-1234

    Examples:
        s2cli paper get 10.1038/nature12373
        s2cli paper get arXiv:2103.14030 --fields title,abstract,tldr
        s2cli paper get arXiv:1706.03762 -f record
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        paper = client.get_paper(paper_id, fields=field_list)
        if paper:
            print_output(paper, fmt=output_format, fields=field_list if fields else None)
        else:
            if not quiet:
                print(f"Paper not found: {paper_id}", file=sys.stderr)
            raise typer.Exit(EXIT_NOT_FOUND)
    except typer.Exit:
        raise
    except Exception as e:
        if not quiet:
            if is_rate_limit_error(e):
                print("Error: Rate limited. Wait a moment and retry, or set S2_API_KEY.", file=sys.stderr)
            else:
                print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)


@app.command()
def citations(
    paper_id: Annotated[
        str,
        typer.Argument(
            help="Paper ID (S2ID, DOI, ArXiv:xxx, PMID:xxx, ACL:xxx, CorpusId:xxx)"
        ),
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
    ] = 100,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get papers that cite this paper.

    Examples:
        s2cli paper citations 10.1038/nature12373 --limit 20
        s2cli paper citations arXiv:1706.03762 --fields title,year,citationCount
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.get_paper_citations(paper_id, fields=field_list, limit=1000)
        # Results are Citation objects with a 'paper' attribute
        # Only take the number we actually want
        papers = [c.paper for c in islice(results, limit) if c.paper]
        print_output(papers, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            if is_rate_limit_error(e):
                print("Error: Rate limited. Wait a moment and retry, or set S2_API_KEY.", file=sys.stderr)
            else:
                print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)


@app.command()
def references(
    paper_id: Annotated[
        str,
        typer.Argument(
            help="Paper ID (S2ID, DOI, ArXiv:xxx, PMID:xxx, ACL:xxx, CorpusId:xxx)"
        ),
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
    ] = 100,
    fmt: FormatOption = None,
    quiet: QuietOption = False,
    api_key: ApiKeyOption = None,
):
    """Get papers this paper references.

    Examples:
        s2cli paper references 10.1038/nature12373 --limit 20
        s2cli paper references arXiv:1706.03762 --fields title,year
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    try:
        results = client.get_paper_references(paper_id, fields=field_list, limit=1000)
        # Results are Reference objects with a 'paper' attribute
        # Only take the number we actually want
        papers = [r.paper for r in islice(results, limit) if r.paper]
        print_output(papers, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            if is_rate_limit_error(e):
                print("Error: Rate limited. Wait a moment and retry, or set S2_API_KEY.", file=sys.stderr)
            else:
                print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(EXIT_RATE_LIMITED if is_rate_limit_error(e) else EXIT_API_ERROR)
