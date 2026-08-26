"""Cheap repository admission decision logic."""

from app.services.search.admission.facts import build_candidate_facts
from app.services.search.admission.checks.candidate import (
    build_candidate_admission_decision,
)
from app.services.search.admission.gates.name import apply_repo_name_gate
from app.services.search.admission.models import AdmissionDecision
from app.services.search.retrieval.models import RepositoryCandidate


def build_admission_decision(candidate: RepositoryCandidate) -> AdmissionDecision:
    """Return one conservative keep or reject decision."""

    facts = build_candidate_facts(candidate)
    gate_decision = apply_repo_name_gate(facts)
    if gate_decision is not None:
        return gate_decision
    return build_candidate_admission_decision(facts)
