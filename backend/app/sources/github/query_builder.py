"""Build GitHub discovery queries from generic research profiles."""

from __future__ import annotations

from app.models.topic import ResearchProfile


MAX_DISCOVERY_QUERIES = 5


def build_repository_search_queries(profile: ResearchProfile) -> tuple[str, ...]:
    """Build a small set of GitHub repository discovery queries."""

    candidates: list[str] = []
    candidates.extend(profile.seed_queries)

    core_terms = tuple(term for term in profile.core_terms if term.strip())
    if core_terms:
        candidates.append(f"{core_terms[0]} software")
    if len(core_terms) > 1:
        candidates.append(f"{core_terms[0]} {core_terms[1]}")

    related_terms = tuple(term for term in profile.related_terms if term.strip())
    if core_terms and related_terms:
        candidates.append(f"{core_terms[0]} {related_terms[0]}")

    deduped: list[str] = []
    seen: set[str] = set()
    for query in candidates:
        normalized = " ".join(query.split()).strip()
        if not normalized:
            continue
        folded = normalized.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        deduped.append(normalized)
        if len(deduped) >= MAX_DISCOVERY_QUERIES:
            break

    return tuple(deduped)
