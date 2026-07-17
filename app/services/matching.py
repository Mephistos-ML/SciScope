"""Deterministic V0 matching between signals and research profiles."""

from __future__ import annotations

from app.models.signal import NormalizedSignal, SignalMatch
from app.models.topic import ResearchProfile


def match_signal_to_profile(
    signal: NormalizedSignal,
    profile: ResearchProfile,
) -> SignalMatch:
    """Return a simple deterministic match result for V0."""

    haystack = signal.normalized_text.casefold()
    positive_terms = _collect_positive_terms(profile)
    negative_terms = tuple(term for term in profile.negative_terms if term.strip())

    matched_terms = tuple(
        term for term in positive_terms if term.casefold() in haystack
    )
    excluded_terms = tuple(
        term for term in negative_terms if term.casefold() in haystack
    )

    positive_score = float(len(matched_terms))
    negative_penalty = float(len(excluded_terms))
    score = max(0.0, positive_score - negative_penalty)
    matched = score > 0.0

    if matched_terms:
        reason = f"Matched profile terms: {', '.join(matched_terms)}"
    elif excluded_terms:
        reason = f"Only excluded terms matched: {', '.join(excluded_terms)}"
    else:
        reason = "No profile terms matched."

    return SignalMatch(
        topic_slug=profile.topic_slug,
        source=signal.source,
        item_id=signal.item_id,
        matched=matched,
        score=score,
        matched_terms=matched_terms,
        excluded_terms=excluded_terms,
        reason=reason,
    )


def _collect_positive_terms(profile: ResearchProfile) -> tuple[str, ...]:
    ordered_terms = [
        *profile.core_terms,
        *profile.synonyms,
        *profile.related_terms,
    ]
    cleaned_terms: list[str] = []
    seen: set[str] = set()
    for term in ordered_terms:
        normalized = term.strip()
        if not normalized:
            continue
        folded = normalized.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        cleaned_terms.append(normalized)

    return tuple(cleaned_terms)
