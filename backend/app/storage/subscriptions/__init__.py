"""Persistence helpers for subscription-owned records and projections."""

from app.config import DATABASE_URL
from app.storage.subscriptions import subscriptions as subscription_storage
from app.storage.subscriptions import watches as watch_storage
from app.storage.subscriptions.subscriptions import (
    SubscriptionRecord,
)
from app.storage.subscriptions.watches import (
    SubscriptionWatchRecord,
)


def create_subscription(
    *,
    user_id: str,
    repository_id: str,
    selected_query: str | None,
    database_url: str | None = None,
) -> SubscriptionRecord:
    return subscription_storage.create_subscription(
        user_id=user_id,
        repository_id=repository_id,
        selected_query=selected_query,
        database_url=database_url or DATABASE_URL,
    )


def list_subscriptions_for_user(
    user_id: str,
    *,
    database_url: str | None = None,
) -> list[SubscriptionRecord]:
    return subscription_storage.list_subscriptions_for_user(
        user_id,
        database_url=database_url or DATABASE_URL,
    )


def list_all_subscriptions(*, database_url: str | None = None) -> list[SubscriptionRecord]:
    return subscription_storage.list_all_subscriptions(
        database_url=database_url or DATABASE_URL,
    )


def get_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> SubscriptionRecord | None:
    return subscription_storage.get_subscription_for_user(
        user_id,
        subscription_id,
        database_url=database_url or DATABASE_URL,
    )


def delete_subscription_for_user(
    user_id: str,
    subscription_id: str,
    *,
    database_url: str | None = None,
) -> bool:
    return subscription_storage.delete_subscription_for_user(
        user_id,
        subscription_id,
        database_url=database_url or DATABASE_URL,
    )


def list_subscription_watches_for_user(
    user_id: str,
    *,
    database_url: str | None = None,
) -> list[SubscriptionWatchRecord]:
    return watch_storage.list_subscription_watches_for_user(
        user_id,
        database_url=database_url or DATABASE_URL,
    )


def list_all_subscription_watches(
    *,
    database_url: str | None = None,
) -> list[SubscriptionWatchRecord]:
    return watch_storage.list_all_subscription_watches(
        database_url=database_url or DATABASE_URL,
    )

__all__ = [
    "DATABASE_URL",
    "SubscriptionRecord",
    "SubscriptionWatchRecord",
    "create_subscription",
    "delete_subscription_for_user",
    "get_subscription_for_user",
    "list_all_subscription_watches",
    "list_all_subscriptions",
    "list_subscription_watches_for_user",
    "list_subscriptions_for_user",
]
