"""Repository query planning for topic-driven search."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.topic import ResearchProfile
from app.sources.repositories.common.query_builder import (
    build_repository_search_queries,
)


@dataclass(frozen=True)
class RepositoryQueryPlan:
    """Resolved repository queries for one topic."""

    queries: tuple[str, ...]


def build_repository_query_plan(
    profile: ResearchProfile,
) -> RepositoryQueryPlan:
    """Resolve repository queries from one already-built research profile."""

    return RepositoryQueryPlan(queries=tuple(build_repository_search_queries(profile)))
