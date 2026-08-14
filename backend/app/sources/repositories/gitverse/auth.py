"""Authentication helpers for GitVerse API requests."""

from __future__ import annotations

from app.sources.repositories.common import RepositorySourceError


def build_auth_headers() -> dict[str, str]:
    """Raise until the GitVerse source is implemented."""

    raise RepositorySourceError(
        source="gitverse",
        status="disabled",
        public_message="GitVerse repository search is not implemented yet.",
    )
