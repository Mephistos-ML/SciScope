"""Low-level GitHub HTTP client helpers."""

from __future__ import annotations

import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import APP_VERSION


GITHUB_API_BASE = "https://api.github.com"
GITHUB_REQUEST_TIMEOUT_SECONDS = 30
GITHUB_REQUEST_RETRIES = 3
GITHUB_RETRY_BACKOFF_SECONDS = 1.5


def build_user_agent() -> str:
    """Build the application user agent for outbound GitHub requests."""

    return f"SciScope/{APP_VERSION}"


def fetch_json(url: str) -> object:
    """Fetch one JSON payload from the GitHub API with simple retries."""

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": build_user_agent(),
        },
    )

    last_error: Exception | None = None
    for attempt in range(1, GITHUB_REQUEST_RETRIES + 1):
        try:
            with urlopen(request, timeout=GITHUB_REQUEST_TIMEOUT_SECONDS) as response:
                return json.load(response)
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            if attempt == GITHUB_REQUEST_RETRIES:
                break
            time.sleep(GITHUB_RETRY_BACKOFF_SECONDS * attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError("GitHub fetch failed without a captured error.")
