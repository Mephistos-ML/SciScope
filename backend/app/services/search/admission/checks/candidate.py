"""Cheap repository-level admission check."""

from __future__ import annotations

from app.services.search.admission.facts import CandidateFacts
from app.services.search.admission.models import AdmissionDecision


def build_candidate_admission_decision(facts: CandidateFacts) -> AdmissionDecision:
    """Build one admission decision for a candidate that passed early gates."""

    if facts.path_strength == "strong":
        return AdmissionDecision(
            decision="keep",
            bucket="strong_code_keep",
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
            bucket="descriptive_path_keep",
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
            bucket="code_search_keep",
            evidence=facts.evidence,
        )

    if bool(facts.software_term_hits) and (
        facts.has_language or facts.matched_query_count >= 2 or facts.hit_count >= 2
    ):
        return AdmissionDecision(
            decision="keep",
            bucket="metadata_software_keep",
            evidence=facts.evidence,
        )

    if facts.has_language and (facts.matched_query_count >= 2 or facts.hit_count >= 2):
        return AdmissionDecision(
            decision="keep",
            bucket="language_overlap_keep",
            evidence=facts.evidence,
        )

    reject_bucket = _build_reject_bucket(facts)
    if reject_bucket is not None:
        return AdmissionDecision(
            decision="reject",
            bucket=reject_bucket,
            evidence=facts.evidence,
        )

    return AdmissionDecision(
        decision="keep",
        bucket="conservative_keep",
        evidence=facts.evidence,
    )


def _build_reject_bucket(facts: CandidateFacts) -> str | None:
    if _has_strong_software_evidence(facts):
        return None

    has_negative_intent = bool(
        facts.data_like_term_hits
        or facts.paper_like_term_hits
        or facts.collection_term_hits
        or facts.education_term_hits
    )
    if not has_negative_intent:
        return None

    if bool(facts.data_like_term_hits) and not bool(facts.software_term_hits):
        return "data_like_reject"

    if bool(facts.paper_like_term_hits) and bool(facts.collection_term_hits):
        return "paper_like_reject"

    if bool(facts.education_term_hits) and not (
        facts.has_language
        or bool(facts.software_term_hits)
        or facts.path_strength == "descriptive"
    ):
        return "education_like_reject"

    if facts.path_strength == "weak" and not (
        facts.has_language or bool(facts.software_term_hits)
    ):
        return "weak_path_reject"

    return None


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
