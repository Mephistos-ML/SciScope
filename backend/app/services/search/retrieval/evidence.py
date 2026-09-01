"""Canonical retrieval evidence classification."""

from __future__ import annotations

import re

from app.models.signal import Signal
from app.services.search.retrieval.models import (
    RetrievalHit,
    RetrievalMatchEvidence,
    RetrievalMatchLocation,
)


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
_README_NAMES = frozenset({"readme", "readme.md", "readme.rst", "readme.txt"})
_DOCUMENTATION_SEGMENTS = frozenset({"doc", "docs", "documentation"})
_CODE_EXTENSIONS = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".cu",
        ".f",
        ".f90",
        ".f95",
        ".f03",
        ".for",
        ".go",
        ".h",
        ".hpp",
        ".java",
        ".jl",
        ".js",
        ".kt",
        ".lua",
        ".m",
        ".mm",
        ".php",
        ".pl",
        ".py",
        ".r",
        ".rb",
        ".rs",
        ".scala",
        ".sh",
        ".swift",
        ".ts",
        ".tsx",
    }
)


def build_retrieval_match_evidence(hit: RetrievalHit) -> RetrievalMatchEvidence:
    """Classify one raw retrieval hit into a source-independent match location."""

    signal = hit.signal
    query = hit.query.strip()
    location = _classify_metadata_location(signal, query)
    path = str(signal.payload.get("matched_path") or "").strip()

    if location is None:
        location = _classify_path_location(path, fallback=hit.channel)

    return RetrievalMatchEvidence(
        query=query,
        location=location,
        path=path,
    )


def _classify_metadata_location(
    signal: Signal,
    query: str,
) -> RetrievalMatchLocation | None:
    if _contains_query(signal.title, query):
        return "name"

    description = str(signal.payload.get("description") or "")
    if _contains_query(description, query):
        return "description"

    topics = signal.payload.get("topics", [])
    topics_text = " ".join(
        str(topic).strip() for topic in topics if str(topic).strip()
    ) if isinstance(topics, list) else ""
    if _contains_query(topics_text, query):
        return "topic"

    return None


def _classify_path_location(
    path: str,
    *,
    fallback: str,
) -> RetrievalMatchLocation:
    normalized_path = path.replace("\\", "/").casefold()
    path_parts = tuple(part for part in normalized_path.split("/") if part)
    filename = path_parts[-1] if path_parts else ""

    if filename in _README_NAMES:
        return "readme"
    if any(part in _DOCUMENTATION_SEGMENTS for part in path_parts[:-1]):
        return "documentation"
    if any(filename.endswith(extension) for extension in _CODE_EXTENSIONS):
        return "code"
    if path:
        return "other"
    if fallback == "repository_search":
        return "metadata"
    return "other"


def _contains_query(text: str, query: str) -> bool:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return False
    return query_tokens.issubset(set(_tokenize(text)))


def _tokenize(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in _WORD_PATTERN.findall(text.casefold())
        if token not in _STOP_WORDS
    )
