"""YAML configuration parsing for citetree commands."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CitetreeConfig:
    """Configuration for citetree crawl operations."""

    # Crawl settings
    depth: int = 2
    direction: str = "citations"  # or "references"
    limit: int = 1000
    influential_only: bool = False

    # Paper IDs to crawl
    papers: list[str] = field(default_factory=list)


def parse_paper_entry(entry: Any) -> str | None:
    """Parse a paper entry from YAML - can be string or object with 'id' field.

    Args:
        entry: A string paper ID or dict with 'id' key

    Returns:
        Paper ID string, or None if invalid
    """
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict) and "id" in entry:
        return entry["id"]
    return None


def load_config(config_path: Path) -> CitetreeConfig:
    """Load citetree configuration from a YAML file.

    Args:
        config_path: Path to the YAML config file

    Returns:
        CitetreeConfig with parsed settings

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ValueError: If config format is invalid
    """
    with open(config_path) as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    config = CitetreeConfig()

    # Parse global settings
    if "depth" in data:
        config.depth = int(data["depth"])

    if "direction" in data:
        direction = data["direction"]
        if direction not in ("citations", "references"):
            raise ValueError(f"Invalid direction '{direction}': must be 'citations' or 'references'")
        config.direction = direction

    if "limit" in data:
        config.limit = int(data["limit"])

    if "influential_only" in data:
        config.influential_only = bool(data["influential_only"])

    # Parse papers list
    if "papers" in data:
        papers_data = data["papers"]
        if not isinstance(papers_data, list):
            raise ValueError("'papers' must be a list")

        for entry in papers_data:
            paper_id = parse_paper_entry(entry)
            if paper_id:
                config.papers.append(paper_id)
            else:
                raise ValueError(f"Invalid paper entry: {entry} (must be string or object with 'id' field)")

    return config
