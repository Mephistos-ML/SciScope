"""Shared GitHub HTTP protocol values and error-body decoding."""

import json
from http.client import HTTPException
from urllib.error import HTTPError

from app.__version__ import __version__
from app.integrations.repositories.common.response_body import read_response_body
from app.integrations.repositories.common.source_status import RepositorySourceError

GITHUB_API_BASE = "https://api.github.com"


def build_user_agent() -> str:
    """Identify the application revision in outbound requests."""
    return f"SciScope/{__version__}"


def read_error_message(exc: HTTPError, *, deadline_monotonic: float | None = None) -> str:
    """Consume an error body once, falling back to its HTTP reason."""
    try:
        if deadline_monotonic is None or exc.fp is None:
            payload = json.load(exc)
        else:
            payload = json.loads(read_response_body(exc, source="github",
                                                   deadline_monotonic=deadline_monotonic, max_response_bytes=64 * 1024))
    except TimeoutError:
        raise
    except (HTTPException, ValueError, TypeError, OSError, RepositorySourceError):
        return str(exc.reason)
    if isinstance(payload, dict):
        return str(payload.get("message") or exc.reason)
    return str(exc.reason)
