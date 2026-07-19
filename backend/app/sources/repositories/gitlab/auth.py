"""Authentication helpers for GitLab API requests."""

from __future__ import annotations

from app.config import GITLAB_TOKEN


def build_auth_headers() -> dict[str, str]:
    """Build optional authentication headers for GitLab API requests."""

    token = GITLAB_TOKEN
    if not token:
        return {}

    return {"PRIVATE-TOKEN": token}
