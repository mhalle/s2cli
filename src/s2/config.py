"""Configuration and environment handling."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from current directory or parent directories
load_dotenv()

# Also try loading from the package directory (for development)
_package_dir = Path(__file__).parent.parent.parent
_env_file = _package_dir / ".env"
if _env_file.exists():
    load_dotenv(_env_file)


def get_api_key(cli_key: str | None = None) -> str | None:
    """Get API key from CLI argument or environment.

    Priority:
    1. CLI argument (--api-key)
    2. S2_API_KEY environment variable
    """
    if cli_key:
        return cli_key
    return os.environ.get("S2_API_KEY") or None


def get_default_format() -> str:
    """Get default output format from environment."""
    return os.environ.get("S2_OUTPUT_FORMAT", "json")
