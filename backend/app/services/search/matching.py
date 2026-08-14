"""Deterministic V0 matching between signals and research profiles."""

from __future__ import annotations

from app.models.signal import NormalizedSignal, SignalMatch
from app.models.subscription import SubscriptionQueryProfile


def match_signal_to_profile(
    signal: NormalizedSignal,
    profile: SubscriptionQueryProfile,
) -> SignalMatch:
    """Return a simple deterministic match result for V0."""

    haystack = signal.normalized_text.casefold()
    matched_terms = tuple(
        term for term in profile.query_terms if term.casefold() in haystack
    )

    score = float(len(matched_terms))
    matched = score > 0.0

    if matched_terms:
        reason = f"Matched profile terms: {', '.join(matched_terms)}"
    else:
        reason = "No profile terms matched."

    return SignalMatch(
        subscription_id=profile.subscription_id,
        source=signal.source,
        item_id=signal.item_id,
        matched=matched,
        score=score,
        matched_terms=matched_terms,
        reason=reason,
    )
