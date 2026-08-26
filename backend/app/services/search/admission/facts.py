"""Fact extraction for repository admission decisions."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.signal import Signal
from app.services.search.admission.checks.path import classify_path_strength
from app.services.search.admission.terms.metadata import (
    COLLECTION_TERMS,
    DATA_LIKE_TERMS,
    EDUCATION_TERMS,
    PAPER_LIKE_TERMS,
    SOFTWARE_TERMS,
)
from app.services.search.admission.models import AdmissionEvidence, AdmissionPathStrength
from app.services.search.admission.terms.name import REPO_NAME_REJECT_TERMS
from app.services.search.retrieval.models import RepositoryCandidate


@dataclass(frozen=True)
class CandidateFacts:
    """Normalized facts used by cheap admission rules."""

    has_code_search: bool
    matched_query_count: int
    hit_count: int
    has_language: bool
    language: str
    repo_name_negative_hits: tuple[str, ...]
    software_term_hits: tuple[str, ...]
    data_like_term_hits: tuple[str, ...]
    paper_like_term_hits: tuple[str, ...]
    collection_term_hits: tuple[str, ...]
    education_term_hits: tuple[str, ...]
    path_strength: AdmissionPathStrength
    evidence: AdmissionEvidence


def build_candidate_facts(candidate: RepositoryCandidate) -> CandidateFacts:
    """Extract normalized admission facts from one repository candidate."""

    signal = candidate.signal
    raw_text = signal.raw_text.casefold()
    title = signal.title.casefold()
    repository_name = read_repository_name(signal).casefold()
    topics = " ".join(
        str(topic).casefold()
        for topic in signal.payload.get("topics", [])
        if isinstance(topic, str) and topic.strip()
    )
    language = str(signal.payload.get("language") or "").strip()
    combined_text = " ".join(part for part in (title, raw_text, topics) if part)
    matched_path = read_matched_code_path(signal.raw_text)
    path_strength = classify_path_strength(matched_path)
    repo_name_negative_hits = find_repo_name_negative_hits(repository_name)
    software_term_hits = find_term_hits(combined_text, SOFTWARE_TERMS)
    data_like_term_hits = find_term_hits(combined_text, DATA_LIKE_TERMS)
    paper_like_term_hits = find_term_hits(combined_text, PAPER_LIKE_TERMS)
    collection_term_hits = find_term_hits(combined_text, COLLECTION_TERMS)
    education_term_hits = find_term_hits(combined_text, EDUCATION_TERMS)
    matched_query_count = len(
        [query for query in candidate.provenance.matched_queries if query.strip()]
    )
    evidence = AdmissionEvidence(
        matched_channels=candidate.provenance.matched_channels,
        matched_query_count=matched_query_count,
        hit_count=candidate.provenance.hit_count,
        path_strength=path_strength,
        has_language=bool(language),
        software_term_hits=software_term_hits,
        data_like_term_hits=data_like_term_hits,
        paper_like_term_hits=paper_like_term_hits,
        collection_term_hits=collection_term_hits,
        education_term_hits=education_term_hits,
    )

    return CandidateFacts(
        has_code_search="code_search" in candidate.provenance.matched_channels,
        matched_query_count=matched_query_count,
        hit_count=candidate.provenance.hit_count,
        has_language=bool(language),
        language=language,
        repo_name_negative_hits=repo_name_negative_hits,
        software_term_hits=software_term_hits,
        data_like_term_hits=data_like_term_hits,
        paper_like_term_hits=paper_like_term_hits,
        collection_term_hits=collection_term_hits,
        education_term_hits=education_term_hits,
        path_strength=path_strength,
        evidence=evidence,
    )


def read_matched_code_path(raw_text: str) -> str:
    """Extract the matched path emitted by code search, if any."""

    for line in raw_text.splitlines():
        if line.startswith("Matched code path:"):
            return line.split(":", 1)[1].strip().casefold()
    return ""


def read_repository_name(signal: Signal) -> str:
    """Read the short repository name from one signal."""

    payload_repo = str(signal.payload.get("repo") or "").strip()
    if payload_repo:
        return payload_repo.split("/")[-1]
    return signal.title.split("/")[-1].strip()


def find_term_hits(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    """Return every configured term that appears in the text."""

    return tuple(term for term in terms if term in text)


def find_repo_name_negative_hits(repository_name: str) -> tuple[str, ...]:
    """Return negative repo-name patterns that strongly imply non-software intent."""

    normalized_name = repository_name.replace("_", "-").casefold()
    hits = [
        term
        for term in REPO_NAME_REJECT_TERMS
        if f"-{term}-" in f"-{normalized_name}-"
    ]
    return tuple(hits)
