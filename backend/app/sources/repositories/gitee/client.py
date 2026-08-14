"""Low-level Gitee HTTP client placeholder helpers."""

from __future__ import annotations

from app.config import APP_VERSION
from app.sources.repositories.common import RepositorySourceError


GITEE_API_BASE = "https://gitee.com/api/v5"


def build_user_agent() -> str:
    """Build the application user agent for outbound Gitee requests."""

    return f"SciScope/{APP_VERSION}"


def fetch_json(url: str) -> object:
    """Raise until the Gitee source is implemented."""

    del url
    raise RepositorySourceError(
        source="gitee",
        status="disabled",
        public_message="Gitee repository search is not implemented yet.",
    )
