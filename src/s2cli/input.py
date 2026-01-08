"""Input parsing utilities for reading IDs from various sources."""

import json
import sys
from typing import Any


def parse_ids_from_stdin(id_field: str = "paperId") -> list[str]:
    """Parse IDs from stdin.

    Supports multiple formats:
    - Plain text: one ID per line
    - JSON array: extracts id_field from each object
    - JSONL: one JSON object per line, extracts id_field from each

    Args:
        id_field: Field name to extract from JSON objects (default: paperId)

    Returns:
        List of ID strings
    """
    if sys.stdin.isatty():
        return []

    content = sys.stdin.read().strip()
    if not content:
        return []

    # Try to detect format
    ids: list[str] = []

    # Check if it looks like JSON (starts with [ or {)
    if content.startswith("["):
        # JSON array
        ids = _parse_json_array(content, id_field)
    elif content.startswith("{"):
        # JSONL (multiple JSON objects, one per line)
        ids = _parse_jsonl(content, id_field)
    else:
        # Plain text, one ID per line
        ids = [line.strip() for line in content.splitlines() if line.strip()]

    return ids


def _parse_json_array(content: str, id_field: str) -> list[str]:
    """Parse a JSON array and extract IDs."""
    try:
        data = json.loads(content)
        if not isinstance(data, list):
            return []
        return _extract_ids_from_objects(data, id_field)
    except json.JSONDecodeError:
        return []


def _parse_jsonl(content: str, id_field: str) -> list[str]:
    """Parse JSONL (one JSON object per line) and extract IDs."""
    ids: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            extracted = _extract_ids_from_objects([obj], id_field)
            ids.extend(extracted)
        except json.JSONDecodeError:
            # Not JSON, treat as plain ID
            ids.append(line)
    return ids


def _extract_ids_from_objects(objects: list[Any], id_field: str) -> list[str]:
    """Extract ID field from a list of objects."""
    ids: list[str] = []
    for obj in objects:
        if isinstance(obj, dict):
            # Try the specified field
            if id_field in obj:
                value = obj[id_field]
                if isinstance(value, str):
                    ids.append(value)
                elif isinstance(value, (int, float)):
                    ids.append(str(value))
            # Also check for nested 'paper' or 'author' objects (for citations/references)
            elif "paper" in obj and isinstance(obj["paper"], dict):
                nested = obj["paper"]
                if id_field in nested:
                    ids.append(str(nested[id_field]))
            elif "author" in obj and isinstance(obj["author"], dict):
                nested = obj["author"]
                if id_field in nested:
                    ids.append(str(nested[id_field]))
        elif isinstance(obj, str):
            # It's just a string ID
            ids.append(obj)
    return ids
