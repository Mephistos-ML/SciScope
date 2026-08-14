"""Deterministic V0 matching between signals and query terms."""

from __future__ import annotations

from collections.abc import Sequence

from app.models.signal import NormalizedSignal, SignalMatch


def match_signal_to_terms(
    signal: NormalizedSignal,
    query_terms: Sequence[str],
) -> SignalMatch:
    """Return a simple deterministic match result for V0."""

    haystack = signal.normalized_text.casefold()
    matched_terms = tuple(term for term in query_terms if term.casefold() in haystack)

    score = float(len(matched_terms))
    matched = score > 0.0

    if matched_terms:
        reason = f"Matched profile terms: {', '.join(matched_terms)}"
    else:
        reason = "No profile terms matched."

    return SignalMatch(
        source=signal.source,
        item_id=signal.item_id,
        matched=matched,
        score=score,
        matched_terms=matched_terms,
        reason=reason,
    )
