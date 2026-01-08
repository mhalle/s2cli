"""Authors commands - bulk author operations."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from ..client import AUTHOR_FIELDS_DEFAULT, AUTHOR_FIELDS_FULL, get_client, parse_fields
from ..input import parse_ids_from_stdin
from ..options import (
    AUTHOR_FIELDS_HELP,
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
    author_ids: Annotated[
        Optional[list[str]],
        typer.Argument(help="Author IDs to retrieve"),
    ] = None,
    file: Annotated[
        Optional[Path],
        typer.Option(
            "--file",
            "-i",
            help="File with author IDs (one per line)",
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
    ] = "authorId",
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
    """Get multiple authors by ID.

    Provide IDs as arguments, from a file, or via stdin.

    Stdin accepts:
    - Plain text (one ID per line)
    - JSON array of objects with authorId field
    - JSONL (one JSON object per line)

    Examples:
        s2 authors get 1741101 2059281478 --fields name,hIndex,paperCount
        s2 authors get --file author_ids.txt
        s2 paper get arXiv:1706.03762 --fields authors | s2 authors get --stdin
    """
    client = get_client(resolve_api_key(api_key))
    field_list = parse_fields(fields, AUTHOR_FIELDS_DEFAULT, AUTHOR_FIELDS_FULL)
    output_format = resolve_format(fmt)

    # Collect all author IDs from various sources
    ids: list[str] = []
    if author_ids:
        ids.extend(author_ids)
    if file:
        if not file.exists():
            print(f"Error: File not found: {file}", file=sys.stderr)
            raise typer.Exit(2)
        ids.extend(line.strip() for line in file.read_text().splitlines() if line.strip())
    if stdin:
        ids.extend(parse_ids_from_stdin(id_field))

    if not ids:
        print("Error: No author IDs provided", file=sys.stderr)
        raise typer.Exit(2)

    try:
        # Always include externalIds to suppress false "not found" warnings
        # (library bug: can't match input IDs without externalIds in response)
        request_fields = field_list.copy()
        if "externalIds" not in request_fields:
            request_fields.append("externalIds")

        authors = client.get_authors(ids, fields=request_fields)
        # Filter out None results
        authors = [a for a in authors if a]
        # Only output the fields the user requested
        print_output(authors, fmt=output_format, fields=field_list if fields else None)
    except Exception as e:
        if not quiet:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(3)
