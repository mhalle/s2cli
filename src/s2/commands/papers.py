"""Papers commands - bulk paper operations."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from ..client import PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL, get_client, parse_fields
from ..input import parse_ids_from_stdin
from ..options import (
    ID_FORMATS_HELP,
    PAPER_FIELDS_HELP,
    ApiKeyOption,
    FormatOption,
    OutputFormat,
    QuietOption,
    resolve_api_key,
    resolve_format,
)
from ..output import print_output

app = typer.Typer(no_args_is_help=True)


@app.command()
def get(
    paper_ids: Annotated[
        Optional[list[str]],
        typer.Argument(help=f"Paper IDs to retrieve. {ID_FORMATS_HELP}"),
    ] = None,
    file: Annotated[
        Optional[Path],
        typer.Option(
            "--file",
            "-i",
            help="File with paper IDs (one per line)",
        ),
    ] = None,
    stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read IDs from stdin (supports plain text, JSON array, or JSONL)",
        ),
    ] = False,
    id_field: Annotated[
        str,
        typer.Option(
            "--id-field",
            help="Field name to extract IDs from in JSON input",
        ),
    ] = "paperId",
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
    """Get multiple papers by ID.

    Provide IDs as arguments, from a file, or via stdin.

    Stdin accepts:
    - Plain text (one ID per line)
    - JSON array of objects with paperId field
    - JSONL (one JSON object per line)

    Examples:
        s2 papers get 10.1038/nature12373 arXiv:2103.14030
        s2 papers get --file paper_ids.txt --fields title,year,citationCount
        s2 paper references arXiv:1706.03762 | s2 papers get --stdin --fields title,abstract
        cat ids.json | s2 papers get --stdin --id-field doi
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, PAPER_FIELDS_DEFAULT, PAPER_FIELDS_FULL)
    output_format = resolve_format(fmt)

    # Collect all paper IDs from various sources
    ids: list[str] = []
    if paper_ids:
        ids.extend(paper_ids)
    if file:
        if not file.exists():
            print(f"Error: File not found: {file}", file=sys.stderr)
            raise typer.Exit(2)
        ids.extend(line.strip() for line in file.read_text().splitlines() if line.strip())
    if stdin:
        ids.extend(parse_ids_from_stdin(id_field))

    if not ids:
        print("Error: No paper IDs provided", file=sys.stderr)
        raise typer.Exit(2)

    try:
        # Always include externalIds to suppress false "not found" warnings
        # (library bug: can't match input IDs without externalIds in response)
        request_fields = field_list.copy()
        if "externalIds" not in request_fields:
            request_fields.append("externalIds")

        papers = client.get_papers(ids, fields=request_fields)
        # Filter out None results
        papers = [p for p in papers if p]
        # Only output the fields the user requested
        print_output(papers, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(3)
