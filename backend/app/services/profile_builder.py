"""Research topic to research profile generation lives here."""

from __future__ import annotations

import re

from app.models.topic import ResearchProfile, ResearchTopic

CLAUSE_SPLIT_PATTERN = re.compile(r"[\n,;|]+")
FOCUS_SPLIT_PATTERN = re.compile(
    r"\b(?:around|about|for|with|using|focused on|focused|on)\b",
    re.IGNORECASE,
)


def build_profile(topic: ResearchTopic) -> ResearchProfile:
    """Build one deterministic research profile from a user topic."""

    source_text = _normalize_phrase(topic.description or topic.label)
    search_queries = _extract_query_candidates(source_text)
    match_terms = _extract_match_terms(search_queries)

    return ResearchProfile(
        topic_slug=topic.slug,
        core_terms=tuple(match_terms),
        seed_queries=tuple(search_queries),
        metadata={
            "profileSource": "topic-description",
        },
    )


def _extract_query_candidates(source_text: str) -> list[str]:
    if not source_text:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        normalized = _normalize_phrase(value).strip(" .")
        if not normalized:
            return

        folded = normalized.casefold()
        if folded in seen:
            return

        seen.add(folded)
        candidates.append(normalized)

    add_candidate(source_text)

    for clause in CLAUSE_SPLIT_PATTERN.split(source_text):
        add_candidate(clause)

        focus_chunks = FOCUS_SPLIT_PATTERN.split(clause)
        if len(focus_chunks) >= 2:
            add_candidate(focus_chunks[-1])

    return candidates


def _extract_match_terms(search_queries: list[str]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        normalized = _normalize_phrase(value).strip(" .")
        if not normalized:
            return

        folded = normalized.casefold()
        if folded in seen:
            return

        seen.add(folded)
        candidates.append(normalized)

    for query in search_queries:
        tokens = [token for token in query.replace("/", " ").split() if token]
        if not tokens:
            continue

        if len(tokens) <= 3:
            add_candidate(" ".join(tokens))
            continue

        add_candidate(" ".join(tokens[:2]))
        add_candidate(" ".join(tokens[:3]))

    return candidates


def _normalize_phrase(value: str) -> str:
    return " ".join(value.split()).strip()
