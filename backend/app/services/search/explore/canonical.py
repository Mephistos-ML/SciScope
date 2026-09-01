"""Canonical Explore result projection."""

from __future__ import annotations

from app.services.search.explore.evaluation import ExploreSearchEvaluation
from app.services.search.explore.items import build_repository_item
from app.services.search.ranking import RankedRepositoryCandidate


def build_canonical_items(
    evaluation: ExploreSearchEvaluation,
) -> list[dict[str, object]]:
    """Return only repositories eligible for the public Explore output."""

    return [
        build_repository_item(candidate)
        for candidate in select_canonical_candidates(evaluation)
    ]


def select_canonical_candidates(
    evaluation: ExploreSearchEvaluation,
) -> tuple[RankedRepositoryCandidate, ...]:
    """Select admitted repositories that meet the ranking cutoff."""

    admitted_repository_ids = {
        evaluated.candidate.repository_id
        for evaluated in evaluation.admission.visible_candidates
    }
    return tuple(
        ranked
        for ranked in evaluation.ranking.ranked_candidates
        if ranked.candidate.repository_id in admitted_repository_ids
        and ranked.score >= evaluation.ranking.relevance_cutoff
    )
