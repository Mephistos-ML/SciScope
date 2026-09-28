"""Internal state retained for one incrementally executed Explore search plan."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.ai import AiSearchPlan
from app.services.search.retrieval import RetrievedCandidates


@dataclass(frozen=True)
class ExploreSearchExecution:
    """A completed portion of one AI-generated Explore search plan."""

    ai_search_plan: AiSearchPlan
    executed_queries: tuple[str, ...]
    retrieved: RetrievedCandidates

    @property
    def pending_queries(self) -> tuple[str, ...]:
        return self.ai_search_plan.queries[len(self.executed_queries) :]
