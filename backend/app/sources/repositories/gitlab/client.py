"""Low-level GitLab HTTP client helpers."""

from __future__ import annotations

import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import APP_VERSION
from app.sources.repositories.gitlab.auth import build_auth_headers


GITLAB_API_BASE = "https://gitlab.com/api/v4"
GITLAB_REQUEST_TIMEOUT_SECONDS = 30
GITLAB_REQUEST_RETRIES = 3
GITLAB_RETRY_BACKOFF_SECONDS = 1.5


def build_user_agent() -> str:
    """Build the application user agent for outbound GitLab requests."""

    return f"SciScope/{APP_VERSION}"


def fetch_json(url: str) -> object:
    """Fetch one JSON payload from the GitLab API with simple retries."""

    headers = {
        "Accept": "application/json",
        "User-Agent": build_user_agent(),
    }
    headers.update(build_auth_headers())

    request = Request(
        url,
        headers=headers,
    )

    last_error: Exception | None = None
    for attempt in range(1, GITLAB_REQUEST_RETRIES + 1):
        try:
            with urlopen(request, timeout=GITLAB_REQUEST_TIMEOUT_SECONDS) as response:
                return json.load(response)
        except (TimeoutError, URLError, OSError) as exc:
            last_error = exc
            if attempt == GITLAB_REQUEST_RETRIES:
                break
            time.sleep(GITLAB_RETRY_BACKOFF_SECONDS * attempt)

    if last_error is not None:
        raise last_error

    raise RuntimeError("GitLab fetch failed without a captured error.")
