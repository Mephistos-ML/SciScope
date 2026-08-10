"""User subscription application service."""

from __future__ import annotations

from app.services.auth import User
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
                "manualQueries": list(item.manual_keywords),
                "createdAt": item.created_at,
            }
            for item in subscriptions
        ]
    }


def create_subscription_payload(
    user: User,
    *,
    topic_description: str,
    manual_keywords: list[str],
) -> dict[str, object]:
    """Persist and serialize one new subscription."""

    subscription = create_subscription(
        user_id=user.user_id,
        topic_description=topic_description,
        manual_keywords=manual_keywords,
    )
    return {
        "subscriptionId": subscription.subscription_id,
        "topicDescription": subscription.topic_description,
        "manualQueries": list(subscription.manual_keywords),
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
