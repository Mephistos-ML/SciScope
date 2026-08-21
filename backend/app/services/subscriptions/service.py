"""User subscription application service."""

from __future__ import annotations

from app.config import DATABASE_URL
from app.services.monitoring import sync_repository_baseline
from app.models.repository import Repository
from app.services.auth import User
from app.services.subscriptions.repositories import build_subscribed_repository
from app.storage.repositories import (
    delete_repository_checkpoints_for_subscription,
    upsert_repositories,
)
from app.storage.subscriptions import (
    create_subscription,
    delete_subscription_for_user,
    list_subscription_watches_for_user,
)


def list_subscription_payloads(
    user: User,
    *,
    database_url: str = DATABASE_URL,
) -> dict[str, object]:
    """Return serialized subscriptions for the current user."""

    subscriptions = list_subscription_watches_for_user(
        user.user_id,
        database_url=database_url,
    )
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
    database_url: str = DATABASE_URL,
) -> dict[str, object]:
    """Persist and serialize one direct repository watch."""

    repository: Repository = build_subscribed_repository(
        repository_item_id=repository_item_id,
        repository_source=repository_source,
        repository_full_name=repository_full_name,
        repository_url=repository_url,
        selected_query=selected_query,
    )
    upsert_repositories((repository,), database_url=database_url)
    subscription = create_subscription(
        user_id=user.user_id,
        repository_id=repository.repository_id,
        selected_query=selected_query,
        database_url=database_url,
    )
    sync_repository_baseline(
        subscription.subscription_id,
        repository,
        database_url=database_url,
    )

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


def delete_subscription_payload(
    user: User,
    subscription_id: str,
    *,
    database_url: str = DATABASE_URL,
) -> bool:
    """Delete one repository watch and its monitoring cursor."""

    deleted = delete_subscription_for_user(
        user.user_id,
        subscription_id,
        database_url=database_url,
    )
    if not deleted:
        return False

    delete_repository_checkpoints_for_subscription(
        subscription_id,
        database_url=database_url,
    )
    return True
