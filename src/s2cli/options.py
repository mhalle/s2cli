"""Shared CLI options."""

from enum import Enum
from typing import Annotated, Optional

import typer

from .config import get_api_key, get_default_format


class OutputFormat(str, Enum):
    json = "json"
    jsonl = "jsonl"
    csv = "csv"
    record = "record"


# Help text for fields
PAPER_FIELDS_HELP = (
    "Fields to include (comma-separated, or 'all'). "
    "Available: paperId, externalIds, url, title, abstract, venue, year, "
    "referenceCount, citationCount, influentialCitationCount, isOpenAccess, "
    "openAccessPdf, fieldsOfStudy, publicationTypes, publicationDate, "
    "journal, authors, tldr"
)

AUTHOR_FIELDS_HELP = (
    "Fields to include (comma-separated, or 'all'). "
    "Available: authorId, externalIds, url, name, affiliations, "
    "homepage, paperCount, citationCount, hIndex"
)

ID_FORMATS_HELP = (
    "Accepts: S2 Paper ID, DOI (10.xxx), ArXiv (arXiv:xxx), "
    "PubMed (PMID:xxx), ACL (ACL:xxx), Corpus ID (CorpusId:xxx)"
)


# Common option definitions for reuse across commands
FormatOption = Annotated[
    Optional[OutputFormat],
    typer.Option(
        "--format",
        "-f",
        help="Output format: json, jsonl, csv, record",
    ),
]

QuietOption = Annotated[
    bool,
    typer.Option(
        "--quiet",
        "-q",
        help="Suppress progress messages, output only data",
    ),
]

ApiKeyOption = Annotated[
    Optional[str],
    typer.Option(
        "--api-key",
        envvar="S2_API_KEY",
        help="API key for authenticated requests",
    ),
]

LimitOption = Annotated[
    int,
    typer.Option(
        "--limit",
        "-l",
        help="Maximum number of results",
    ),
]


def resolve_format(fmt: OutputFormat | None) -> str:
    """Resolve format option to string, using default if not specified."""
    if fmt is None:
        return get_default_format()
    return fmt.value


def resolve_api_key(api_key: str | None) -> str | None:
    """Resolve API key from option or environment."""
    return get_api_key(api_key)
