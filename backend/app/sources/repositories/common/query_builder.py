"""Shared repository-family query building."""

from __future__ import annotations

from app.models.topic import ResearchProfile


MAX_DISCOVERY_QUERIES = 5


def build_repository_search_queries(profile: ResearchProfile) -> tuple[str, ...]:
    """Build repository search queries directly from profile terms."""

    candidates = [
        *profile.core_terms,
        *profile.synonyms,
        *profile.related_terms,
    ]

    queries: list[str] = []
    seen: set[str] = set()
    for term in candidates:
        normalized = " ".join(term.split()).strip()
        if not _is_usable_repository_query(normalized):
            continue

        folded = normalized.casefold()
        if folded in seen:
            continue

        seen.add(folded)
        queries.append(normalized)
        if len(queries) >= MAX_DISCOVERY_QUERIES:
            break

    return tuple(queries)


def _is_usable_repository_query(term: str) -> bool:
    if not term:
        return False

    if len(term) < 5:
        return False

    # Drop short abbreviations like PCS/PRE that are too noisy in repository search.
    if " " not in term and len(term) < 8:
        return False

    return True
