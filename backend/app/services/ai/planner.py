"""AI search-plan service boundary."""

from __future__ import annotations

from typing import Protocol

from app import config
from app.models.ai import AiSearchPlan
from app.services.ai.openai.planner import OpenAiSearchPlanner
from app.services.ai.search_plans import build_bootstrap_ai_search_plan


class AiSearchPlanner(Protocol):
    """Build a structured search plan from one topic description."""

    def build_search_plan(
        self,
        *,
        topic_description: str,
    ) -> AiSearchPlan: ...


class BootstrapAiSearchPlanner:
    """Temporary planner used until the real LLM-backed planner lands."""

    def build_search_plan(
        self,
        *,
        topic_description: str,
    ) -> AiSearchPlan:
        return build_bootstrap_ai_search_plan(
            topic_description=topic_description,
        )


def get_ai_search_planner() -> AiSearchPlanner:
    """Return the active planner implementation for this runtime."""

    if config.AI_PLANNER_MODE == "openai":
        return OpenAiSearchPlanner()
    return BootstrapAiSearchPlanner()


def build_ai_search_plan(
    *,
    topic_description: str,
) -> AiSearchPlan:
    """Build one search plan through the active planner boundary."""

    planner = get_ai_search_planner()
    return planner.build_search_plan(
        topic_description=topic_description,
    )
