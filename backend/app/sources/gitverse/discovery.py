"""GitVerse repository discovery placeholder."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.signal import Signal
from app.sources.common import RepositorySourceError


def discover_repository_candidates(
    queries: Sequence[str],
    *,
    per_query_limit: int = 10,
) -> list[Signal]:
    """Raise until GitVerse repository discovery is implemented."""

    del queries, per_query_limit
    raise RepositorySourceError(
        source="gitverse",
        status="disabled",
        public_message="GitVerse repository search is not implemented yet.",
    )
