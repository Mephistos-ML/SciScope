"""GitVerse repository discovery placeholder."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.discovery import DiscoveryResult
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile
from app.sources.repositories.common import RepositorySourceError


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[RawSignal]:
    """Raise until GitVerse repository discovery is implemented."""

    del queries, per_query_limit
    raise RepositorySourceError(
        source="gitverse",
        status="disabled",
        public_message="GitVerse repository search is not implemented yet.",
    )


def discover_gitverse_entities_for_profile(
    profile: ResearchProfile,
    *,
    database_url: str | None = None,
) -> DiscoveryResult:
    """Raise until GitVerse entity discovery is implemented."""

    del profile, database_url
    raise RepositorySourceError(
        source="gitverse",
        status="disabled",
        public_message="GitVerse repository search is not implemented yet.",
    )
