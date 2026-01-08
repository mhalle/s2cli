"""Output formatting utilities."""

import csv
import io
import json
import sys
from typing import Any


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SemanticScholar object to a dictionary."""
    if hasattr(obj, "raw_data"):
        return obj.raw_data
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj


def _flatten_for_csv(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested dict for CSV output."""
    items: dict[str, str] = {}
    for key, value in data.items():
        new_key = f"{prefix}{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten_for_csv(value, f"{new_key}."))
        elif isinstance(value, list):
            if value and isinstance(value[0], dict):
                # For lists of dicts (like authors), join key fields
                if "name" in value[0]:
                    items[new_key] = "; ".join(str(v.get("name", "")) for v in value)
                else:
                    items[new_key] = json.dumps(value)
            else:
                items[new_key] = "; ".join(str(v) for v in value)
        else:
            items[new_key] = str(value) if value is not None else ""
    return items


def _format_record(data: dict[str, Any], indent: int = 0) -> str:
    """Format a single record for human/LLM readable output."""
    lines = []
    prefix = "  " * indent

    for key, value in data.items():
        if value is None:
            continue

        # Format key nicely (paperId -> Paper ID, citationCount -> Citation Count)
        display_key = key
        if key[0].islower():
            # Convert camelCase to Title Case
            display_key = "".join(
                f" {c}" if c.isupper() else c for c in key
            ).strip().title()

        if isinstance(value, dict):
            lines.append(f"{prefix}{display_key}:")
            lines.append(_format_record(value, indent + 1))
        elif isinstance(value, list):
            if not value:
                continue
            if isinstance(value[0], dict):
                # Handle list of objects (like authors)
                if "name" in value[0]:
                    # Authors list - format nicely
                    names = [v.get("name", "Unknown") for v in value]
                    lines.append(f"{prefix}{display_key}: {', '.join(names)}")
                else:
                    lines.append(f"{prefix}{display_key}:")
                    for i, item in enumerate(value[:10]):  # Limit to 10 items
                        lines.append(f"{prefix}  [{i+1}]")
                        lines.append(_format_record(item, indent + 2))
                    if len(value) > 10:
                        lines.append(f"{prefix}  ... and {len(value) - 10} more")
            else:
                # Simple list
                lines.append(f"{prefix}{display_key}: {', '.join(str(v) for v in value)}")
        else:
            # Handle long text (like abstracts)
            str_value = str(value)
            if len(str_value) > 200 and "\n" not in str_value:
                # Wrap long text
                lines.append(f"{prefix}{display_key}:")
                words = str_value.split()
                current_line = prefix + "  "
                for word in words:
                    if len(current_line) + len(word) + 1 > 80:
                        lines.append(current_line)
                        current_line = prefix + "  " + word
                    else:
                        current_line += (" " if current_line.strip() else "") + word
                if current_line.strip():
                    lines.append(current_line)
            else:
                lines.append(f"{prefix}{display_key}: {str_value}")

    return "\n".join(lines)


def format_output(
    data: Any,
    fmt: str = "json",
    fields: list[str] | None = None,
) -> str:
    """Format output data according to the specified format.

    Args:
        data: Data to format (object, dict, or list)
        fmt: Output format (json, jsonl, csv, record)
        fields: Optional list of fields to include

    Returns:
        Formatted string
    """
    # Convert to dict(s)
    if isinstance(data, list):
        records = [_to_dict(item) for item in data]
    else:
        records = [_to_dict(data)]

    # Filter fields if specified
    if fields:
        filtered = []
        for record in records:
            filtered.append({k: v for k, v in record.items() if k in fields})
        records = filtered

    if fmt == "json":
        if len(records) == 1:
            return json.dumps(records[0], indent=2)
        return json.dumps(records, indent=2)

    elif fmt == "jsonl":
        return "\n".join(json.dumps(record) for record in records)

    elif fmt == "csv":
        if not records:
            return ""
        flat_records = [_flatten_for_csv(r) for r in records]
        all_keys = set()
        for r in flat_records:
            all_keys.update(r.keys())
        fieldnames = sorted(all_keys)

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flat_records)
        return output.getvalue()

    elif fmt == "record":
        output_lines = []
        for i, record in enumerate(records):
            if i > 0:
                output_lines.append("\n" + "─" * 60 + "\n")
            output_lines.append(_format_record(record))
        return "\n".join(output_lines)

    else:
        raise ValueError(f"Unknown format: {fmt}")


def print_output(
    data: Any,
    fmt: str = "json",
    fields: list[str] | None = None,
    quiet: bool = False,
    file=None,
):
    """Format and print output data.

    Args:
        data: Data to format
        fmt: Output format
        fields: Optional field filter
        quiet: Suppress if True and data is empty
        file: Output file (default: stdout)
    """
    if file is None:
        file = sys.stdout

    if quiet and not data:
        return

    output = format_output(data, fmt=fmt, fields=fields)
    print(output, file=file)
