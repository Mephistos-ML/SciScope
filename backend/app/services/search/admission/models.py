"""Admission filter result models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.search.retrieval.models import RepositoryCandidate

AdmissionMode = Literal["off", "enforced"]
AdmissionDecisionLabel = Literal["keep", "reject"]
AdmissionPathStrength = Literal["strong", "descriptive", "weak", "none"]


@dataclass(frozen=True)
class AdmissionEvidence:
    """Cheap evidence computed for one repository candidate."""

    matched_channels: tuple[str, ...]
    matched_query_count: int
    hit_count: int
    path_strength: AdmissionPathStrength
    has_language: bool
    software_term_hits: tuple[str, ...]
    data_like_term_hits: tuple[str, ...]
    paper_like_term_hits: tuple[str, ...]
    collection_term_hits: tuple[str, ...]
    education_term_hits: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionDecision:
    """One keep or reject decision for one repository candidate."""

    decision: AdmissionDecisionLabel
    reasons: tuple[str, ...]
    evidence: AdmissionEvidence

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
        if self.mode == "off":
            return self.evaluated_candidates
        return tuple(
            candidate
            for candidate in self.evaluated_candidates
            if candidate.admission.keep
        )
