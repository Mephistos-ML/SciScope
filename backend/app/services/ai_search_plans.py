"""AI search-plan helpers."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.ai import AiSearchPlan


def build_bootstrap_ai_search_plan(
    *,
    topic_description: str,
) -> AiSearchPlan:
    """Build one temporary pending search plan before the real LLM planner lands."""

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


def normalize_search_queries(values: Iterable[str]) -> tuple[str, ...]:
    """Normalize one query list for one AI-generated source plan."""

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
def serialize_ai_search_plan(plan: AiSearchPlan) -> dict[str, object]:
    """Serialize one search plan for API responses."""

    return {
        "status": plan.status,
        "queries": list(plan.queries),
    }
