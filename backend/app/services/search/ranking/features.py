"""Feature extraction for source-agnostic repository ranking."""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.services.search.ranking.models import RankingFeatures
from app.services.search.retrieval import RepositoryCandidate


_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "based",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "the",
        "to",
        "with",
    }
)


def build_ranking_features(
    candidate: RepositoryCandidate,
    queries: Sequence[str],
) -> RankingFeatures:
    """Build ranking features without relying on source or retrieval channel."""

    normalized_queries = tuple(
        query.strip() for query in queries if query.strip()
    )
    name_text = candidate.signal.title
    description_text = _read_description_text(candidate)
    topics_text = _read_topics_text(candidate)

    return RankingFeatures(
        matched_query_count=len(candidate.provenance.matched_queries),
        total_query_count=len(normalized_queries),
        hit_count=candidate.provenance.hit_count,
        name_match=_best_query_coverage(name_text, normalized_queries),
        description_match=_best_query_coverage(description_text, normalized_queries),
        topics_match=_best_query_coverage(topics_text, normalized_queries),
    )


def _read_description_text(candidate: RepositoryCandidate) -> str:
    signal = candidate.signal
    language = str(signal.payload.get("language") or "").strip().casefold()
    topics_text = _read_topics_text(candidate).casefold()
    lines: list[str] = []

    for line in signal.raw_text.splitlines():
        normalized_line = line.strip()
        if not normalized_line:
            continue
        if normalized_line.casefold() == signal.title.casefold():
            continue
        if normalized_line.startswith("Matched code path:"):
            continue
        if language and normalized_line.casefold() == language:
            continue
        if topics_text and normalized_line.casefold() == topics_text:
            continue
        lines.append(normalized_line)

    return " ".join(lines)


def _read_topics_text(candidate: RepositoryCandidate) -> str:
    topics = candidate.signal.payload.get("topics", [])
    if not isinstance(topics, list):
        return ""
    return " ".join(str(topic).strip() for topic in topics if str(topic).strip())


def _best_query_coverage(text: str, queries: Sequence[str]) -> float:
    text_tokens = set(_tokenize(text))
    if not text_tokens:
        return 0.0

    coverages = [_term_coverage(text_tokens, query) for query in queries]
    return max(coverages, default=0.0)


def _term_coverage(text_tokens: set[str], query: str) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0
    return len(text_tokens & query_tokens) / len(query_tokens)


def _tokenize(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _WORD_PATTERN.findall(text.casefold())
        if token not in _STOP_WORDS
    )
