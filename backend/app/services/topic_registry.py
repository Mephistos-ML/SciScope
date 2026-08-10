"""Accessors for runtime topics and profiles."""

from __future__ import annotations

from app.models.topic import ResearchProfile, ResearchTopic
from app.services.auth import get_current_user
from app.storage.subscriptions import list_subscriptions_for_user


def list_runtime_topics() -> tuple[ResearchTopic, ...]:
    """Return all topics that should participate in runtime processing."""

    subscriptions = _list_user_subscriptions()
    if subscriptions:
        return tuple(
            ResearchTopic(
                slug=subscription.subscription_id,
                label=subscription.topic_description.strip() or "Manual subscription",
                description=subscription.topic_description,
            )
            for subscription in subscriptions
        )

    return ()


def list_runtime_profiles() -> tuple[ResearchProfile, ...]:
    """Return all profiles that should participate in runtime processing."""

    subscriptions = _list_user_subscriptions()
    if subscriptions:
        return tuple(
            ResearchProfile(
                topic_slug=subscription.subscription_id,
                core_terms=subscription.manual_keywords,
            )
            for subscription in subscriptions
        )

    return ()


def _list_user_subscriptions():
    user = get_current_user()
    if user is None:
        return ()
    return tuple(list_subscriptions_for_user(user.user_id))
