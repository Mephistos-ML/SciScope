"""Bootstrap AI search-plan helpers."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.ai import AiSearchPlan, AiSourcePlan, SearchScope


def build_bootstrap_ai_search_plan(
    *,
    topic_description: str,
    search_scope: SearchScope,
    override_queries: Iterable[str] = (),
) -> AiSearchPlan:
    """Build one temporary search plan before the real LLM planner lands."""

    del topic_description

    normalized_queries = normalize_override_queries(override_queries)
    return AiSearchPlan(
        search_scope=search_scope,
        status="ready" if normalized_queries else "pending",
        source_plans=(
            AiSourcePlan(
                source_type="repositories",
                queries=normalized_queries,
            ),
        ),
    )


def normalize_override_queries(values: Iterable[str]) -> tuple[str, ...]:
    """Normalize one temporary operator-provided query list."""

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


def read_source_queries(
    plan: AiSearchPlan,
    *,
    source_type: str,
) -> tuple[str, ...]:
    """Read queries for one source from a structured plan."""

    for source_plan in plan.source_plans:
        if source_plan.source_type == source_type:
            return source_plan.queries
    return ()


def serialize_ai_search_plan(plan: AiSearchPlan) -> dict[str, object]:
    """Serialize one search plan for API responses."""

    return {
        "searchScope": plan.search_scope,
        "status": plan.status,
        "sourcePlans": [
            {
                "sourceType": source_plan.source_type,
                "queries": list(source_plan.queries),
            }
            for source_plan in plan.source_plans
        ],
    }
