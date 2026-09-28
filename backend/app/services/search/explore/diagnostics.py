"""Diagnostics for explaining incremental Explore search stages."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.search.explore.evaluation import ExploreSearchEvaluation
from app.services.search.explore.execution import ExploreStageSnapshot
from app.services.search.explore.canonical import select_canonical_candidates


def build_explore_stage_snapshot(
    evaluation: ExploreSearchEvaluation,
    *,
    stage: int,
    queries: Sequence[str],
    executed_queries: Sequence[str],
) -> ExploreStageSnapshot:
    """Capture the candidate-to-response path for one beta search stage."""

    ranked_candidates = tuple(evaluation.ranking.ranked_candidates)
    admission_by_repository_id = {
        evaluated.candidate.repository_id: evaluated.admission
        for evaluated in evaluation.admission.evaluated_candidates
    }
    ranked_snapshot = tuple(
        {
            "rank": rank,
            "itemId": ranked.candidate.repository_id,
            "fullName": ranked.candidate.signal.title,
            "score": ranked.score,
            "admission": admission_by_repository_id[
                ranked.candidate.repository_id
            ].decision,
            "admissionBucket": admission_by_repository_id[
                ranked.candidate.repository_id
            ].bucket,
        }
        for rank, ranked in enumerate(ranked_candidates, start=1)
    )
    canonical_item_ids = tuple(
        ranked.candidate.repository_id
        for ranked in select_canonical_candidates(evaluation)
    )

    return ExploreStageSnapshot(
        stage=stage,
        queries=tuple(queries),
        executed_queries=tuple(executed_queries),
        candidate_pool=tuple(
            {
                "itemId": candidate.repository_id,
                "fullName": candidate.signal.title,
            }
            for candidate in evaluation.retrieved.candidates
        ),
        ranked_candidates=ranked_snapshot,
        canonical_item_ids=canonical_item_ids,
    )


def serialize_explore_stage_snapshots(
    snapshots: Sequence[ExploreStageSnapshot],
) -> list[dict[str, object]]:
    """Serialize internal stage snapshots for the beta response only."""

    return [
        {
            "stage": snapshot.stage,
            "queries": list(snapshot.queries),
            "executedQueries": list(snapshot.executed_queries),
            "candidatePoolCount": len(snapshot.candidate_pool),
            "candidatePool": list(snapshot.candidate_pool),
            "rankedCandidateCount": len(snapshot.ranked_candidates),
            "rankedCandidates": list(snapshot.ranked_candidates),
            "canonicalItemIds": list(snapshot.canonical_item_ids),
        }
        for snapshot in snapshots
    ]
