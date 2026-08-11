"""Repository query planning for topic-driven search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.topic import ResearchProfile
from app.sources.repositories.common.query_builder import (
    build_repository_search_queries,
)

QueryStrategy = Literal["profile_terms", "pending_ai"]


@dataclass(frozen=True)
class RepositoryQueryPlan:
    """Resolved repository queries for one topic."""

    queries: tuple[str, ...]
    strategy: QueryStrategy


def build_repository_query_plan(
    profile: ResearchProfile,
) -> RepositoryQueryPlan:
    """Resolve repository queries from one already-built research profile."""

    queries = tuple(build_repository_search_queries(profile))
    if queries:
        return RepositoryQueryPlan(
            queries=queries,
            strategy="profile_terms",
        )

    return RepositoryQueryPlan(
        queries=(),
        strategy="pending_ai",
    )


def normalize_profile_query_terms(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Normalize one structured query-term list."""

    normalized_values: list[str] = []
    seen: set[str] = set()

    for raw_value in values:
        normalized = " ".join(str(raw_value).split()).strip()
        if not normalized:
            continue

        folded = normalized.casefold()
        if folded in seen:
            continue

        seen.add(folded)
        normalized_values.append(normalized)

    return tuple(normalized_values)
