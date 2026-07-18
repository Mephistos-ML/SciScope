"""Low-level GitHub HTTP client helpers."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.config import APP_VERSION


GITHUB_API_BASE = "https://api.github.com"


def build_user_agent() -> str:
    """Build the application user agent for outbound GitHub requests."""

    return f"SciScope/{APP_VERSION}"


def fetch_json(url: str) -> object:
    """Fetch one JSON payload from the GitHub API."""

    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": build_user_agent(),
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)
