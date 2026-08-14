"""Gitee repository discovery placeholder."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.signal import RawSignal
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
