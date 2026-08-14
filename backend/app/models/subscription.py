"""Subscription-bound query profile models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionQueryProfile:
    """The only matching profile SciScope needs in repository-only mode."""

    subscription_id: str
    topic_description: str
    query_terms: tuple[str, ...] = ()
