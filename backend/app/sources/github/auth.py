"""Authentication helpers for GitHub API requests."""

from __future__ import annotations

from app.config import GITHUB_TOKEN


def build_auth_headers() -> dict[str, str]:
    """Build optional authentication headers for GitHub API requests."""

    token = GITHUB_TOKEN
    if not token:
        return {}

    return {"Authorization": f"Bearer {token}"}
