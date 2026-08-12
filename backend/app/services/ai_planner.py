"""AI search-plan service boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.models.ai import AiSearchPlan, SearchScope
from app.services.ai_search_plans import build_bootstrap_ai_search_plan


class AiSearchPlanner(Protocol):
    """Build a structured search plan from one topic description."""

    def build_search_plan(
        self,
        *,
        topic_description: str,
        search_scope: SearchScope,
        override_queries: Sequence[str] = (),
    ) -> AiSearchPlan: ...


class BootstrapAiSearchPlanner:
    """Temporary planner used until the real LLM-backed planner lands."""

    def build_search_plan(
        self,
        *,
        topic_description: str,
        search_scope: SearchScope,
        override_queries: Sequence[str] = (),
    ) -> AiSearchPlan:
        return build_bootstrap_ai_search_plan(
            topic_description=topic_description,
            search_scope=search_scope,
            override_queries=override_queries,
        )


def get_ai_search_planner() -> AiSearchPlanner:
    """Return the active planner implementation for this runtime."""

    return BootstrapAiSearchPlanner()


def build_ai_search_plan(
    *,
    topic_description: str,
    search_scope: SearchScope,
    override_queries: Sequence[str] = (),
) -> AiSearchPlan:
    """Build one search plan through the active planner boundary."""

    planner = get_ai_search_planner()
    return planner.build_search_plan(
        topic_description=topic_description,
        search_scope=search_scope,
        override_queries=override_queries,
    )
