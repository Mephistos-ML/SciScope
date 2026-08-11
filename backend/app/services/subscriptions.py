"""User subscription application service."""

from __future__ import annotations

from app.services.auth import User
from app.models.topic import ResearchTopic
from app.services.profile_builder import build_profile
from app.services.search_queries import build_repository_query_plan
from app.storage.entities import (
    delete_entity_checkpoints_for_subscription,
    delete_subscription_entity_matches,
)
from app.storage.subscriptions import (
    create_subscription,
    delete_subscription_for_user,
    list_subscriptions_for_user,
)


def list_subscription_payloads(user: User) -> dict[str, object]:
    """Return serialized subscriptions for the current user."""

    subscriptions = list_subscriptions_for_user(user.user_id)
    return {
        "items": [
            {
                "subscriptionId": item.subscription_id,
                "topicDescription": item.topic_description,
                "queryStrategy": item.query_strategy,
                "queries": list(item.query_terms),
                "createdAt": item.created_at,
            }
            for item in subscriptions
        ]
    }


def create_subscription_payload(
    user: User,
    *,
    topic_description: str,
    profile_query_terms: tuple[str, ...] = (),
) -> dict[str, object]:
    """Persist and serialize one new subscription."""

    topic = ResearchTopic(
        slug="pending-subscription",
        label=topic_description or "Untitled topic",
        description=topic_description,
    )
    profile = build_profile(
        topic,
        profile_query_terms=profile_query_terms,
    )
    query_plan = build_repository_query_plan(profile)
    subscription = create_subscription(
        user_id=user.user_id,
        topic_description=topic_description,
        query_strategy=query_plan.strategy,
        query_terms=query_plan.queries,
    )
    return {
        "subscriptionId": subscription.subscription_id,
        "topicDescription": subscription.topic_description,
        "queryStrategy": subscription.query_strategy,
        "queries": list(subscription.query_terms),
        "createdAt": subscription.created_at,
    }


def delete_subscription_payload(user: User, subscription_id: str) -> bool:
    """Delete one subscription and its topic-scoped watch memory."""

    deleted = delete_subscription_for_user(user.user_id, subscription_id)
    if not deleted:
        return False

    delete_subscription_entity_matches(subscription_id)
    delete_entity_checkpoints_for_subscription(subscription_id)
    return True
