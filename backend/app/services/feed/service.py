"""Application services for durable user feeds."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.feed import FeedEvent
from app.models.signal import Signal
from app.storage.feed import get_feed_event_for_user, list_feed_events_for_user
from app.storage.subscriptions import SubscriptionWatchRecord


def build_feed_event(
    signal: Signal,
    subscription: SubscriptionWatchRecord,
) -> FeedEvent:
    """Build one durable feed event from a monitored repository signal."""

    return FeedEvent(
        event_id=f"{subscription.subscription_id}:{signal.source}:{signal.item_id}",
        user_id=subscription.user_id,
        subscription_id=subscription.subscription_id,
        repository_id=subscription.repository.repository_id,
        repository_full_name=subscription.repository.full_name,
        repository_source=subscription.repository.source,
        repository_url=subscription.repository.url,
        selected_query=subscription.selected_query,
        source=signal.source,
        kind=signal.kind,
        item_id=signal.item_id,
        title=signal.title,
        url=signal.url,
        published_at=signal.published_at,
        raw_text=signal.raw_text,
        normalized_text=signal.normalized_text,
        metadata=dict(signal.payload),
        created_at=datetime.now(UTC),
    )


def get_feed_list_payload(
    user_id: str,
    *,
    database_url: str,
) -> dict[str, object]:
    """Return one user's feed list payload."""

    return {
        "items": [
            _to_feed_item_payload(event)
            for event in list_feed_events_for_user(user_id, database_url=database_url)
        ]
    }


def get_feed_event_payload(
    user_id: str,
    event_id: str,
    *,
    database_url: str,
) -> dict[str, object] | None:
    """Return one user's feed detail payload."""

    event = get_feed_event_for_user(
        user_id,
        event_id,
        database_url=database_url,
    )
    if event is None:
        return None

    payload = _to_feed_item_payload(event)
    payload["rawText"] = event.raw_text
    payload["normalizedText"] = event.normalized_text
    payload["metadata"] = dict(event.metadata)
    return payload


def _to_feed_item_payload(event: FeedEvent) -> dict[str, object]:
    return {
        "eventId": event.event_id,
        "subscriptionId": event.subscription_id,
        "repositoryId": event.repository_id,
        "repositoryFullName": event.repository_full_name,
        "repositorySource": event.repository_source,
        "repositoryUrl": event.repository_url,
        "selectedQuery": event.selected_query,
        "title": event.title,
        "summary": _read_feed_summary(event.raw_text),
        "source": event.source,
        "signalKind": event.kind,
        "url": event.url,
        "publishedAt": (
            event.published_at.isoformat(timespec="seconds")
            if event.published_at is not None
            else None
        ),
        "createdAt": (
            event.created_at.isoformat(timespec="seconds")
            if event.created_at is not None
            else None
        ),
    }


def _read_feed_summary(raw_text: str) -> str:
    parts = [part.strip() for part in raw_text.splitlines() if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    if parts:
        return parts[0]
    return ""
