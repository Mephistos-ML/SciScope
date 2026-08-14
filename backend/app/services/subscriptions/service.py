"""User subscription application service."""

from __future__ import annotations

from app.services.auth import User
from app.sources.common import build_repository_entity
from app.sources.runtime import sync_repository_baseline
from app.storage.repositories import (
    delete_repository_checkpoints_for_subscription,
    upsert_repositories,
)
from app.storage.subscriptions import (
    create_subscription,
    delete_subscription_for_user,
    list_subscription_watches_for_user,
)
from app.models.signal import RawSignal


def list_subscription_payloads(user: User) -> dict[str, object]:
    """Return serialized subscriptions for the current user."""

    subscriptions = list_subscription_watches_for_user(user.user_id)
    return {
        "items": [
            {
                "subscriptionId": item.subscription_id,
                "repository": {
                    "repositoryId": item.repository.repository_id,
                    "source": item.repository.source,
                    "fullName": item.repository.full_name,
                    "url": item.repository.url,
                },
                "selectedQuery": item.selected_query,
                "createdAt": item.created_at,
            }
            for item in subscriptions
        ]
    }


def create_subscription_payload(
    user: User,
    *,
    repository_item_id: str,
    repository_source: str,
    repository_full_name: str,
    repository_url: str,
    selected_query: str | None,
) -> dict[str, object]:
    """Persist and serialize one direct repository watch."""

    repository_signal = RawSignal(
        source=repository_source,
        kind="repository",
        item_id=repository_item_id,
        title=repository_full_name,
        url=repository_url,
        published_at=None,
        raw_text=repository_full_name,
        payload={
            "repo": repository_full_name,
            "query": selected_query,
        },
    )
    repository = build_repository_entity(repository_signal)
    upsert_repositories((repository,))
    subscription = create_subscription(
        user_id=user.user_id,
        repository_id=repository.repository_id,
        selected_query=selected_query,
    )
    sync_repository_baseline(subscription.subscription_id, repository)

    return {
        "subscriptionId": subscription.subscription_id,
        "repository": {
            "repositoryId": repository.repository_id,
            "source": repository.source,
            "fullName": repository.full_name,
            "url": repository.url,
        },
        "selectedQuery": subscription.selected_query,
        "createdAt": subscription.created_at,
    }


def delete_subscription_payload(user: User, subscription_id: str) -> bool:
    """Delete one repository watch and its monitoring cursor."""

    deleted = delete_subscription_for_user(user.user_id, subscription_id)
    if not deleted:
        return False

    delete_repository_checkpoints_for_subscription(subscription_id)
    return True
