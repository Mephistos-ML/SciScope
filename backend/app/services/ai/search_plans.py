"""AI search-plan helpers."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.ai import AiSearchPlan, normalize_search_queries


def build_bootstrap_ai_search_plan(
    *,
    topic_description: str,
) -> AiSearchPlan:
    """Return a pending plan for the configured bootstrap mode."""

    del topic_description

    return AiSearchPlan(
        status="pending",
        queries=(),
    )


def build_ai_search_plan_from_queries(
    *,
    queries: Iterable[str],
) -> AiSearchPlan:
    """Rehydrate one persisted repository search plan from stored queries."""

    normalized_queries = normalize_search_queries(queries)
    return AiSearchPlan(
        status="ready" if normalized_queries else "pending",
        queries=normalized_queries,
    )


def serialize_ai_search_plan(plan: AiSearchPlan) -> dict[str, object]:
    """Serialize one search plan for API responses."""

    return {
        "status": plan.status,
        "queries": list(plan.queries),
    }
