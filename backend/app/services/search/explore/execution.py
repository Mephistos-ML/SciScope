"""Internal state retained for one incrementally executed Explore search plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.ai import AiSearchPlan
from app.services.search.retrieval import RetrievedCandidates


@dataclass(frozen=True)
class ExploreQueryAttempt:
    """One provider retrieval attempt for one planned query."""

    query: str
    attempt: int
    status: Literal["completed", "timed_out"]
    duration_ms: int
    candidate_count: int


@dataclass(frozen=True)
class ExploreStageSnapshot:
    """Beta-only state needed to explain one incremental search stage."""

    stage: int
    queries: tuple[str, ...]
    executed_queries: tuple[str, ...]
    candidate_pool: tuple[dict[str, object], ...]
    ranked_candidates: tuple[dict[str, object], ...]
    canonical_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class ExploreSearchExecution:
    """A completed portion of one AI-generated Explore search plan."""

    ai_search_plan: AiSearchPlan
    executed_queries: tuple[str, ...]
    retrieved: RetrievedCandidates
    attempts: tuple[ExploreQueryAttempt, ...] = ()
    stage_snapshots: tuple[ExploreStageSnapshot, ...] = ()

    @property
    def pending_queries(self) -> tuple[str, ...]:
        return self.ai_search_plan.queries[len(self.executed_queries) :]
