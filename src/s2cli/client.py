"""Semantic Scholar client wrapper."""

from functools import lru_cache

from semanticscholar import SemanticScholar

from .config import get_api_key


@lru_cache(maxsize=1)
def get_client(api_key: str | None = None) -> SemanticScholar:
    """Get a SemanticScholar client instance.

    Uses caching to reuse the same client within a session.
    """
    key = get_api_key(api_key)
    if key:
        return SemanticScholar(api_key=key)
    return SemanticScholar()


# Default field sets for different entity types
PAPER_FIELDS_DEFAULT = ["paperId", "title", "year", "authors", "citationCount"]
PAPER_FIELDS_FULL = [
    "paperId",
    "externalIds",
    "url",
    "title",
    "abstract",
    "venue",
    "publicationVenue",
    "year",
    "referenceCount",
    "citationCount",
    "influentialCitationCount",
    "isOpenAccess",
    "openAccessPdf",
    "fieldsOfStudy",
    "s2FieldsOfStudy",
    "publicationTypes",
    "publicationDate",
    "journal",
    "authors",
    "tldr",
]

AUTHOR_FIELDS_DEFAULT = ["authorId", "name", "paperCount", "citationCount"]
AUTHOR_FIELDS_FULL = [
    "authorId",
    "externalIds",
    "url",
    "name",
    "affiliations",
    "homepage",
    "paperCount",
    "citationCount",
    "hIndex",
]


def parse_fields(
    fields_str: str | None,
    default: list[str],
    full: list[str] | None = None,
) -> list[str]:
    """Parse comma-separated fields string into a list.

    Args:
        fields_str: Comma-separated field names, or "all" for all fields
        default: Default fields if fields_str is None
        full: Full field list to use when fields_str is "all"

    Returns:
        List of field names
    """
    if not fields_str:
        return default
    if fields_str.strip().lower() == "all":
        return full if full else default
    return [f.strip() for f in fields_str.split(",") if f.strip()]
