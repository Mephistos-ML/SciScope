"""Gitee repository discovery placeholder."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.discovery import DiscoveryResult
from app.models.signal import RawSignal
from app.models.subscription import SubscriptionQueryProfile
from app.sources.common import RepositorySourceError


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[RawSignal]:
    """Raise until Gitee repository discovery is implemented."""

    del queries, per_query_limit
    raise RepositorySourceError(
        source="gitee",
        status="disabled",
        public_message="Gitee repository search is not implemented yet.",
    )


def discover_gitee_repositories_for_profile(
    profile: SubscriptionQueryProfile,
    *,
    database_url: str | None = None,
) -> DiscoveryResult:
    """Raise until Gitee entity discovery is implemented."""

    del profile, database_url
    raise RepositorySourceError(
        source="gitee",
        status="disabled",
        public_message="Gitee repository search is not implemented yet.",
    )
