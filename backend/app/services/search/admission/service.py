"""Admission service for repository candidate pools."""

from __future__ import annotations

from app.config import EXPLORE_ADMISSION_MODE
from app.services.search.admission.models import (
    AdmissionDecision,
    AdmissionMode,
    AdmissionResult,
    EvaluatedRepositoryCandidate,
)
from app.services.search.admission.rules import build_admission_decision
from app.services.search.retrieval.models import RepositoryCandidate


def run_repository_admission(
    candidates: tuple[RepositoryCandidate, ...],
    *,
    mode: AdmissionMode | None = None,
) -> AdmissionResult:
    """Evaluate one candidate pool under the configured admission mode."""

    active_mode = EXPLORE_ADMISSION_MODE if mode is None else mode
    if active_mode == "off":
        evaluated_candidates = tuple(
            EvaluatedRepositoryCandidate(
                candidate=candidate,
                admission=AdmissionDecision(
                    decision="keep",
                    reasons=("Admission filter is disabled.",),
                ),
            )
            for candidate in candidates
        )
        return AdmissionResult(
            mode=active_mode,
            evaluated_candidates=evaluated_candidates,
            kept_count=len(evaluated_candidates),
            rejected_count=0,
        )

    evaluated_candidates = tuple(
        EvaluatedRepositoryCandidate(
            candidate=candidate,
            admission=build_admission_decision(candidate),
        )
        for candidate in candidates
    )
    kept_count = sum(1 for candidate in evaluated_candidates if candidate.admission.keep)
    rejected_count = len(evaluated_candidates) - kept_count

    return AdmissionResult(
        mode=active_mode,
        evaluated_candidates=evaluated_candidates,
        kept_count=kept_count,
        rejected_count=rejected_count,
    )
