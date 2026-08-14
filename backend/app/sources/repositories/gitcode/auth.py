"""Authentication helpers for GitCode API requests."""

from __future__ import annotations

from app.sources.repositories.common import RepositorySourceError


def build_auth_headers() -> dict[str, str]:
    """Raise until the GitCode source is implemented."""

    raise RepositorySourceError(
        source="gitcode",
        status="disabled",
        public_message="GitCode repository search is not implemented yet.",
    )
