"""Shared GitHub HTTP protocol values and error-body decoding."""

import json
from urllib.error import HTTPError

from app.__version__ import __version__

GITHUB_API_BASE = "https://api.github.com"


def build_user_agent() -> str:
    """Identify the application revision in outbound requests."""
    return f"SciScope/{__version__}"


def read_error_message(exc: HTTPError) -> str:
    """Consume an error body once, falling back to its HTTP reason."""
    try:
        payload = json.load(exc)
    except (ValueError, TypeError, OSError):
        return str(exc.reason)
    if isinstance(payload, dict):
        return str(payload.get("message") or exc.reason)
    return str(exc.reason)
