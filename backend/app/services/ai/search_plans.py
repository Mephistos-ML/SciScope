# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""AI search-plan helpers."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.ai import AiSearchPlan, normalize_search_queries
from app.models.scientific_domain import ScientificDomain, parse_scientific_domain


# Natural-language planner context, separate from persisted domain IDs.
_DOMAIN_CONTEXT_LABELS = {
    ScientificDomain.PHYSICS: "Physics",
    ScientificDomain.CHEMISTRY: "Chemistry",
    ScientificDomain.MATERIALS_SCIENCE: "Materials Science",
    ScientificDomain.BIOLOGY_BIOINFORMATICS: "Biology & Bioinformatics",
    ScientificDomain.EARTH_ENVIRONMENTAL_SCIENCE: "Earth & Environmental Science",
    ScientificDomain.ASTRONOMY_SPACE_SCIENCE: "Astronomy & Space Science",
    ScientificDomain.MATHEMATICS_STATISTICS: "Mathematics & Statistics",
    ScientificDomain.COMPUTER_SCIENCE: "Computer Science",
}


def format_search_plan_topic(
    *, topic_description: str, scientific_domain: ScientificDomain | None = None,
) -> str:
    """Render supplied context for planning without changing the stored question."""
    domain = parse_scientific_domain(scientific_domain)
    if domain is None:
        return topic_description
    return f"Scientific domain: {_DOMAIN_CONTEXT_LABELS[domain]}\n\n{topic_description}"


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
