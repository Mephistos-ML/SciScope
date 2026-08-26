"""Admission filter result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.search.retrieval.models import RepositoryCandidate

AdmissionMode = Literal["off", "shadow", "enforced"]
AdmissionDecisionLabel = Literal["keep", "reject"]


@dataclass(frozen=True)
class AdmissionDecision:
    """One keep or reject decision for one repository candidate."""

    decision: AdmissionDecisionLabel
    reasons: tuple[str, ...]

    @property
    def keep(self) -> bool:
        return self.decision == "keep"


@dataclass(frozen=True)
class EvaluatedRepositoryCandidate:
    """One retrieved candidate paired with its admission decision."""

    candidate: RepositoryCandidate
    admission: AdmissionDecision


@dataclass(frozen=True)
class AdmissionResult:
    """Admission evaluation over one deduplicated candidate pool."""

    mode: AdmissionMode
    evaluated_candidates: tuple[EvaluatedRepositoryCandidate, ...]
    kept_count: int
    rejected_count: int

    @property
    def visible_candidates(self) -> tuple[EvaluatedRepositoryCandidate, ...]:
        if self.mode == "enforced":
            return tuple(
                candidate
                for candidate in self.evaluated_candidates
                if candidate.admission.keep
            )
        return self.evaluated_candidates
