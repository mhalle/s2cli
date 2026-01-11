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
    return SemanticScholar(api_key=key, retry=False)


# Default field sets for different entity types
PAPER_FIELDS_DEFAULT = ["paperId", "externalIds", "title", "year", "authors", "citationCount"]
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


def safe_iterate(results, limit: int):
    """Safely iterate over paginated results, handling empty result bugs.

    The semanticscholar library has a bug where iterating over empty results
    raises a RetryError/ConnectionRefusedError instead of returning empty.
    This wrapper catches that and returns an empty list.
    """
    items = []
    try:
        for item in results:
            items.append(item)
            if len(items) >= limit:
                break
    except Exception as e:
        err_str = str(e)
        # Library bug: empty results cause RetryError with ConnectionRefusedError
        if "RetryError" in err_str or "ConnectionRefusedError" in err_str:
            # Check if we got any results before the error
            if not items:
                return []  # Likely empty results, not a real connection error
        raise  # Re-raise other errors or if we had partial results
    return items


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
