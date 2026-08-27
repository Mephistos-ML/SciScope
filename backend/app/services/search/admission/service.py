"""Admission service for repository candidate pools."""

from __future__ import annotations

import logging
from time import monotonic

from app.config import EXPLORE_ADMISSION_MODE
from app.services.search.admission.models import (
    AdmissionDecision,
    AdmissionEvidence,
    AdmissionMode,
    AdmissionResult,
    EvaluatedRepositoryCandidate,
)
from app.services.search.admission.decision import build_admission_decision
from app.services.search.observability import (
    SearchLogContext,
    build_duration_ms,
    log_search_event,
)
from app.services.search.retrieval.models import RepositoryCandidate

logger = logging.getLogger(__name__)


def run_repository_admission(
    candidates: tuple[RepositoryCandidate, ...],
    *,
    mode: AdmissionMode | None = None,
    log_context: SearchLogContext | None = None,
) -> AdmissionResult:
    """Evaluate one candidate pool under the configured admission mode."""

    admission_started_at = monotonic()
    active_mode = EXPLORE_ADMISSION_MODE if mode is None else mode
    if active_mode == "off":
        evaluated_candidates = tuple(
            EvaluatedRepositoryCandidate(
                candidate=candidate,
                admission=AdmissionDecision(
                    decision="keep",
                    evidence=AdmissionEvidence(
                        matched_channels=candidate.provenance.matched_channels,
                        matched_query_count=len(candidate.provenance.matched_queries),
                        hit_count=candidate.provenance.hit_count,
                        path_strength="none",
                        has_language=bool(str(candidate.signal.payload.get("language") or "").strip()),
                        software_term_hits=(),
                        data_like_term_hits=(),
                        paper_like_term_hits=(),
                        collection_term_hits=(),
                        education_term_hits=(),
                    ),
                ),
            )
            for candidate in candidates
        )
        result = AdmissionResult(
            mode=active_mode,
            evaluated_candidates=evaluated_candidates,
            kept_count=len(evaluated_candidates),
            rejected_count=0,
        )
        if log_context is not None:
            log_search_event(
                logger=logger,
                event="explore_admission_completed",
                context=log_context,
                duration_ms=build_duration_ms(admission_started_at),
                candidate_count_in=len(candidates),
                kept_count=result.kept_count,
                rejected_count=result.rejected_count,
                mode=result.mode,
            )
        return result

    evaluated_candidates = tuple(
        EvaluatedRepositoryCandidate(
            candidate=candidate,
            admission=build_admission_decision(candidate),
        )
        for candidate in candidates
    )
    kept_count = sum(1 for candidate in evaluated_candidates if candidate.admission.keep)
    rejected_count = len(evaluated_candidates) - kept_count

    result = AdmissionResult(
        mode=active_mode,
        evaluated_candidates=evaluated_candidates,
        kept_count=kept_count,
        rejected_count=rejected_count,
    )
    if log_context is not None:
        log_search_event(
            logger=logger,
            event="explore_admission_completed",
            context=log_context,
            duration_ms=build_duration_ms(admission_started_at),
            candidate_count_in=len(candidates),
            kept_count=result.kept_count,
            rejected_count=result.rejected_count,
            mode=result.mode,
        )
    return result
