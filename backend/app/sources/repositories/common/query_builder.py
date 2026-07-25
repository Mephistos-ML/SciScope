"""Shared repository-family query building."""

from __future__ import annotations

from app.models.topic import ResearchProfile


def build_repository_search_queries(profile: ResearchProfile) -> tuple[str, ...]:
    """Build repository search queries directly from profile terms.

    Manual queries are currently treated as already-normalized profile terms,
    so this builder only trims and deduplicates them.
    """

    candidates = [
        *profile.core_terms,
        *profile.synonyms,
        *profile.related_terms,
    ]

    queries: list[str] = []
    seen: set[str] = set()
    for term in candidates:
        normalized = " ".join(term.split()).strip()
        if not normalized:
            continue

        folded = normalized.casefold()
        if folded in seen:
            continue

        seen.add(folded)
        queries.append(normalized)

    return tuple(queries)
