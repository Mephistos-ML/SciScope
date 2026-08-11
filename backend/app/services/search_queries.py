"""Repository query planning for topic-driven search."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.models.topic import ResearchProfile
from app.sources.repositories.common.query_builder import (
    build_repository_search_queries,
)

QueryStrategy = Literal["generated", "override"]


@dataclass(frozen=True)
class RepositoryQueryPlan:
    """Resolved repository queries for one topic."""

    queries: tuple[str, ...]
    strategy: QueryStrategy


def build_repository_query_plan(
    profile: ResearchProfile,
    *,
    query_overrides: Sequence[str] = (),
) -> RepositoryQueryPlan:
    """Resolve repository queries from the topic profile or explicit overrides."""

    normalized_overrides = normalize_query_overrides(query_overrides)
    if normalized_overrides:
        return RepositoryQueryPlan(
            queries=normalized_overrides,
            strategy="override",
        )

    return RepositoryQueryPlan(
        queries=tuple(build_repository_search_queries(profile)),
        strategy="generated",
    )


def normalize_query_overrides(values: Sequence[str]) -> tuple[str, ...]:
    """Normalize one optional operator override list."""

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
