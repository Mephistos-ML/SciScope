"""Accessors for active subscription query profiles."""

from __future__ import annotations

from app.models.subscription import SubscriptionQueryProfile
from app.storage.subscriptions import list_all_subscriptions


def build_query_profile(
    *,
    subscription_id: str,
    topic_description: str,
    query_terms: tuple[str, ...],
) -> SubscriptionQueryProfile:
    """Build the only runtime profile shape SciScope needs."""

    return SubscriptionQueryProfile(
        subscription_id=subscription_id,
        topic_description=topic_description,
        query_terms=query_terms,
    )


def list_query_profiles() -> tuple[SubscriptionQueryProfile, ...]:
    """Return all query profiles that should participate in runtime processing."""

    subscriptions = _list_user_subscriptions()
    if subscriptions:
        return tuple(
            build_query_profile(
                subscription_id=subscription.subscription_id,
                topic_description=subscription.topic_description,
                query_terms=subscription.query_terms,
            )
            for subscription in subscriptions
        )

    return ()


def _list_user_subscriptions():
    return tuple(list_all_subscriptions())
