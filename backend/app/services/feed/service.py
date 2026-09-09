"""Application services for durable user feeds."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import json

from app.models.feed import FeedCursor, FeedEvent
from app.models.signal import Signal
from app.storage.feed import (
    count_unread_feed_events_for_user,
    get_feed_event_for_user,
    list_feed_events_for_user,
    mark_all_feed_events_read_for_user,
    mark_feed_event_read_for_user,
)
from app.storage.subscriptions import SubscriptionWatchRecord


FEED_SUMMARY_MAX_LENGTH = 320
DEFAULT_FEED_PAGE_SIZE = 20
MAX_FEED_PAGE_SIZE = 50


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
    limit: int = DEFAULT_FEED_PAGE_SIZE,
    cursor: str | None = None,
    state: str = "all",
    subscription_id: str | None = None,
) -> dict[str, object]:
    """Return one user's feed list payload."""

    if not 1 <= limit <= MAX_FEED_PAGE_SIZE:
        raise ValueError("Feed limit must be between 1 and 50.")
    if state not in {"all", "unread"}:
        raise ValueError("Feed state must be 'all' or 'unread'.")

    events = list_feed_events_for_user(
        user_id,
        database_url=database_url,
        cursor=_decode_feed_cursor(cursor) if cursor else None,
        limit=limit + 1,
        unread_only=state == "unread",
        subscription_id=subscription_id,
    )
    visible_events = events[:limit]
    next_cursor = _encode_feed_cursor(visible_events[-1]) if len(events) > limit else None
    return {
        "items": [
            _to_feed_item_payload(event)
            for event in visible_events
        ],
        "nextCursor": next_cursor,
        "hasMore": next_cursor is not None,
        "unreadCount": count_unread_feed_events_for_user(
            user_id,
            database_url=database_url,
        ),
    }


def _encode_feed_cursor(event: FeedEvent) -> str:
    payload = {
        "publishedAt": event.published_at.isoformat() if event.published_at else None,
        "createdAt": event.created_at.isoformat() if event.created_at else None,
        "eventId": event.event_id,
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_feed_cursor(value: str) -> FeedCursor:
    try:
        padded = f"{value}{'=' * (-len(value) % 4)}"
        payload = json.loads(base64.urlsafe_b64decode(padded))
        created_at = datetime.fromisoformat(str(payload["createdAt"]))
        published_value = payload.get("publishedAt")
        published_at = datetime.fromisoformat(str(published_value)) if published_value else None
        event_id = str(payload["eventId"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Invalid Feed cursor.") from error
    if not event_id:
        raise ValueError("Invalid Feed cursor.")
    return FeedCursor(published_at=published_at, created_at=created_at, event_id=event_id)


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


def mark_feed_event_read_payload(
    user_id: str,
    event_id: str,
    *,
    database_url: str,
) -> dict[str, object] | None:
    """Mark one Feed event as read and return its detail payload."""

    event = mark_feed_event_read_for_user(
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


def mark_all_feed_events_read_payload(
    user_id: str,
    *,
    database_url: str,
) -> dict[str, int]:
    """Mark every unread Feed event as read and return the changed count."""

    return {
        "updatedCount": mark_all_feed_events_read_for_user(
            user_id,
            database_url=database_url,
        )
    }


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
        "readAt": (
            event.read_at.isoformat(timespec="seconds")
            if event.read_at is not None
            else None
        ),
    }


def _read_feed_summary(raw_text: str) -> str:
    parts = [part.strip() for part in raw_text.splitlines() if part.strip()]
    if len(parts) >= 2:
        return _truncate_feed_summary(parts[1])
    if parts:
        return _truncate_feed_summary(parts[0])
    return ""


def _truncate_feed_summary(value: str) -> str:
    """Build a compact, single-paragraph Feed preview."""

    summary = " ".join(value.split())
    if len(summary) <= FEED_SUMMARY_MAX_LENGTH:
        return summary

    prefix = summary[: FEED_SUMMARY_MAX_LENGTH - 1]
    word_boundary = prefix.rfind(" ")
    if word_boundary > 0:
        prefix = prefix[:word_boundary]
    return f"{prefix}…"
