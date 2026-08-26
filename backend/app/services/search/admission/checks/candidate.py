"""Cheap repository-level admission check."""

from __future__ import annotations

from app.services.search.admission.facts import CandidateFacts
from app.services.search.admission.models import AdmissionDecision


def build_candidate_admission_decision(facts: CandidateFacts) -> AdmissionDecision:
    """Build one admission decision for a candidate that passed early gates."""

    if facts.path_strength == "strong":
        return AdmissionDecision(
            decision="keep",
            evidence=facts.evidence,
        )

    if facts.path_strength == "descriptive" and (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.matched_query_count >= 2
        or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            evidence=facts.evidence,
        )

    if facts.has_code_search and (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.matched_query_count >= 2
        or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            evidence=facts.evidence,
        )

    if bool(facts.software_term_hits) and (
        facts.has_language or facts.matched_query_count >= 2 or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            evidence=facts.evidence,
        )

    if facts.has_language and (facts.matched_query_count >= 2 or facts.hit_count >= 2):
        return AdmissionDecision(
            decision="keep",
            evidence=facts.evidence,
        )

    if _is_clear_candidate_reject(facts):
        return AdmissionDecision(
            decision="reject",
            evidence=facts.evidence,
        )

    return AdmissionDecision(
        decision="keep",
        evidence=facts.evidence,
    )


def _is_clear_candidate_reject(facts: CandidateFacts) -> bool:
    if _has_strong_software_evidence(facts):
        return False

    has_negative_intent = bool(
        facts.data_like_term_hits
        or facts.paper_like_term_hits
        or facts.collection_term_hits
        or facts.education_term_hits
    )
    if not has_negative_intent:
        return False

    if bool(facts.data_like_term_hits) and not bool(facts.software_term_hits):
        return True

    if bool(facts.paper_like_term_hits) and bool(facts.collection_term_hits):
        return True

    if bool(facts.education_term_hits) and not (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.path_strength == "descriptive"
    ):
        return True

    if facts.path_strength == "weak" and not (
        facts.has_language or bool(facts.software_term_hits)
    ):
        return True

    return False


def _has_strong_software_evidence(facts: CandidateFacts) -> bool:
    if facts.path_strength == "strong":
        return True
    if facts.has_code_search and (facts.has_language or bool(facts.software_term_hits)):
        return True
    if bool(facts.software_term_hits) and (
        facts.has_language or facts.matched_query_count >= 2 or facts.hit_count >= 2
    ):
        return True
    return False
