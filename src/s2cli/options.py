"""Shared CLI options."""

from enum import Enum
from typing import Annotated, Optional

import typer

from .config import get_api_key, get_default_format


# Exit codes
EXIT_SUCCESS = 0
EXIT_NOT_FOUND = 1      # Resource not found (specific ID lookup)
EXIT_INPUT_ERROR = 2    # Invalid input, missing arguments, file not found
EXIT_API_ERROR = 3      # API error (non-retriable)
EXIT_RATE_LIMITED = 4   # Rate limited (retriable)


def is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate limit error."""
    err_str = str(e)
    return "429" in err_str or "rate" in err_str.lower()


def is_retriable_error(e: Exception) -> bool:
    """Check if an exception is retriable (transient network/server issue)."""
    err_str = str(e)
    type_name = type(e).__name__
    # Check exception type names
    if any(x in type_name for x in ["Timeout", "Gateway", "Connection"]):
        return True
    # Check error message patterns
    return any(x in err_str for x in [
        "ConnectionRefusedError",
        "ConnectionError",
        "TimeoutError",
        "GatewayTimeout",
        "Network error",
    ])


def format_api_error(e: Exception) -> str:
    """Format an API exception into a user-friendly message."""
    err_str = str(e)
    type_name = type(e).__name__

    if is_rate_limit_error(e):
        return "Rate limited. Wait a moment and retry, or set S2_API_KEY."

    # Gateway/server errors
    if "GatewayTimeout" in type_name or "Gateway" in err_str:
        return "API gateway timeout. The server may be overloaded, try again later."
    if "Network error" in err_str:
        return "API network error. The server may be overloaded, try again later."

    # Connection errors
    if "ConnectionRefusedError" in err_str:
        return "Connection refused. The API may be unavailable."
    if "ConnectionError" in err_str or "Connection" in type_name:
        return "Connection failed. Check your network or try again later."
    if "TimeoutError" in err_str or "Timeout" in type_name:
        return "Request timed out. Try again later."

    # Strip RetryError wrapper noise
    if "RetryError" in err_str:
        if "ConnectionRefusedError" in err_str:
            return "Connection refused. The API may be unavailable."
        if "TimeoutError" in err_str:
            return "Request timed out. Try again later."
        return "Request failed after retries. Try again later."

    return str(e)


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
