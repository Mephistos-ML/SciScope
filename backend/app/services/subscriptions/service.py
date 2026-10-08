"""User subscription application service."""

from __future__ import annotations

from collections.abc import Callable

from app.config import DATABASE_URL
from app.models.repository import Repository, parse_repository_id
from app.models.auth import User
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.storage.repositories.repositories import get_repository, get_or_insert_repository
from app.storage.subscriptions.subscriptions import (
    create_subscription,
    delete_subscription_for_user,
)
from app.storage.subscriptions.watches import list_subscription_watches_for_user


class SubscriptionRepositoryUnavailableError(RuntimeError):
    """A canonical repository profile could not be fetched for a subscription."""


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
                "unreadEventCount": item.unread_event_count,
            }
            for item in subscriptions
        ]
    }


def create_subscription_payload(
    user: User,
    *,
    repository_item_id: str,
    load_repository_profile: Callable[[str], Repository],
    selected_query: str | None,
    database_url: str = DATABASE_URL,
) -> dict[str, object]:
    """Persist and serialize one direct repository watch."""

    repository_item_id = repository_item_id.strip()
    source = repository_item_id.partition(":repo:")[0]
    if source not in {"github", "gitlab"}:
        raise ValueError("This repository source does not support subscriptions.")
    provider_id = parse_repository_id(repository_item_id, source=source)
    if not provider_id.isascii() or not provider_id.isdecimal() or int(provider_id) <= 0:
        raise ValueError("Repository ID must contain a positive numeric provider ID.")

    repository = get_repository(repository_item_id, database_url=database_url)
    if repository is None:
        try:
            repository = load_repository_profile(repository_item_id)
        except RepositorySourceError as exc:
            raise SubscriptionRepositoryUnavailableError(exc.public_message) from exc
        if (
            repository.repository_id != repository_item_id
            or repository.source != source
            or repository.provider_repository_id != provider_id
        ):
            raise ValueError("Provider profile does not match the requested repository ID.")
        repository = get_or_insert_repository(repository, database_url=database_url)
    subscription = create_subscription(
        user_id=user.user_id,
        repository_id=repository.repository_id,
        selected_query=selected_query,
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

    return True
