"""Hard repository-name gate for admission."""

from __future__ import annotations

from app.services.search.admission.facts import CandidateFacts
from app.services.search.admission.models import AdmissionDecision


def apply_repo_name_gate(facts: CandidateFacts) -> AdmissionDecision | None:
    """Reject obvious non-software repositories based on short repo name only."""

    if not facts.repo_name_negative_hits:
        return None

    return AdmissionDecision(
        decision="reject",
        evidence=facts.evidence,
    )
