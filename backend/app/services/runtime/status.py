"""Status payload builders for the monitoring runtime."""

from __future__ import annotations

from app.config import DATABASE_URL, MONITORING_INTERVAL_SECONDS
from app.runtime.state import STATE
from app.storage.feed import count_feed_events
from app.storage.repositories import list_repository_checkpoints
from app.storage.subscriptions import (
    SubscriptionWatchRecord,
    list_all_subscription_watches,
)


def get_status_payload(*, database_url: str = DATABASE_URL) -> dict[str, object]:
    """Return a compact JSON-serializable status payload."""

    subscriptions = list_all_subscription_watches(database_url=database_url)
    return {
        "subscriptionCount": len(subscriptions),
        "subscriptions": [
            {
                "subscriptionId": subscription.subscription_id,
                "repositoryId": subscription.repository.repository_id,
                "source": subscription.repository.source,
                "fullName": subscription.repository.full_name,
                "selectedQuery": subscription.selected_query,
            }
            for subscription in subscriptions
        ],
        "autoScanStarted": STATE.auto_scan_started,
        "autoScanIntervalSeconds": MONITORING_INTERVAL_SECONDS,
        "monitoringIntervalSeconds": MONITORING_INTERVAL_SECONDS,
        "lastScanAt": (
            STATE.last_scan_at.isoformat(timespec="seconds")
            if STATE.last_scan_at
            else None
        ),
        "lastScanError": STATE.last_scan_error,
        "watchedRepositories": _describe_watched_repositories(subscriptions),
        "sourceCheckpoints": _describe_repository_checkpoints(
            subscriptions,
            database_url=database_url,
        ),
        "totalFeedEvents": count_feed_events(database_url=database_url),
    }


def _describe_watched_repositories(
    subscriptions: list[SubscriptionWatchRecord],
) -> list[dict[str, object]]:
    return [
        {
            "subscriptionId": subscription.subscription_id,
            "repositoryId": subscription.repository.repository_id,
            "source": subscription.repository.source,
            "fullName": subscription.repository.full_name,
            "url": subscription.repository.url,
            "selectedQuery": subscription.selected_query,
            "stars": subscription.repository.metadata.get("stars"),
            "language": subscription.repository.metadata.get("language"),
        }
        for subscription in subscriptions
    ]


def _describe_repository_checkpoints(
    subscriptions: list[SubscriptionWatchRecord],
    *,
    database_url: str,
) -> list[dict[str, object]]:
    checkpoints: list[dict[str, object]] = []
    for subscription in subscriptions:
        for checkpoint in list_repository_checkpoints(
            subscription.subscription_id,
            subscription.repository.repository_id,
            database_url=database_url,
        ):
            checkpoints.append(
                {
                    "subscriptionId": subscription.subscription_id,
                    "repositoryId": subscription.repository.repository_id,
                    "source": subscription.repository.source,
                    "fullName": subscription.repository.full_name,
                    "checkpointKey": checkpoint.checkpoint_key,
                    "checkpointValue": checkpoint.checkpoint_value,
                    "updatedAt": checkpoint.updated_at.isoformat(timespec="seconds"),
                }
            )
    return checkpoints
