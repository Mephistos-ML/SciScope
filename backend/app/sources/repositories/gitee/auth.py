"""Authentication helpers for Gitee API requests."""

from __future__ import annotations

from app.sources.repositories.common import RepositorySourceError


def build_auth_headers() -> dict[str, str]:
    """Raise until the Gitee source is implemented."""

    raise RepositorySourceError(
        source="gitee",
        status="disabled",
        public_message="Gitee repository search is not implemented yet.",
    )
