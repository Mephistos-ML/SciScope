"""Application capability and provenance for an already selected planner."""

from dataclasses import dataclass
from typing import Protocol

from app.models.ai import AiSearchPlan, AiPlannerIdentity


class SearchPlanBuilder(Protocol):
    def __call__(self, *, topic_description: str) -> AiSearchPlan: ...


@dataclass(frozen=True)
class AiSearchPlanner:
    """The executable planner and the facts used to identify its output."""

    build_search_plan: SearchPlanBuilder
    identity: AiPlannerIdentity
