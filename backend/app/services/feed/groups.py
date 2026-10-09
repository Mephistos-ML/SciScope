"""Grouped Feed payloads and scoped keyset pagination contracts."""

import base64
import binascii
from datetime import datetime
import json
from typing import cast

from app.models.feed import FeedCursor, FeedGroupCursor, FeedGroupSummary, FeedEvent
from app.services.feed.service import to_feed_item_payload
from app.storage.feed.group_queries import (
    count_unread_feed_groups_for_user, list_feed_group_commits_for_user,
    list_feed_group_summaries_for_user, mark_feed_group_read_for_user,
)


DEFAULT_GROUP_PAGE_SIZE = 20
DEFAULT_COMMIT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError("Feed limit must be between 1 and 50.")


def _encode_cursor(payload: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps({"v": 1, **payload}, separators=(",", ":")).encode()).decode().rstrip("=")


def _decode_cursor(value: str, *, kind: str, group_id: str | None = None) -> dict[str, object]:
    try:
        if len(value) > 2048:
            raise ValueError
        payload = json.loads(base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True))
        if not isinstance(payload, dict) or type(payload.get("v")) is not int or payload["v"] != 1:
            raise ValueError
        if payload.get("type") != kind or group_id is not None and payload.get("groupId") != group_id:
            raise ValueError
        for key in ("createdAt", "publishedAt"):
            raw = payload[key]
            if raw is None and key == "publishedAt":
                continue
            if not isinstance(raw, str):
                raise ValueError
            timestamp = datetime.fromisoformat(raw)
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError
        identity = payload["groupId" if kind == "groups" else "eventId"]
        if not isinstance(identity, str) or not identity or len(identity) > 200:
            raise ValueError
        return payload
    except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error) as error:
        raise ValueError("Invalid grouped Feed cursor.") from error


def _group_payload(group: FeedGroupSummary) -> dict[str, object]:
    event = to_feed_item_payload(group.representative)
    return {
        "groupId": group.group_id, "subscriptionId": group.subscription_id,
        "repositoryId": group.repository_id,
        **{key: event[key] for key in ("repositoryFullName", "repositorySource", "repositoryUrl", "selectedQuery")},
        "kind": group.kind,
        "title": event["title"] if group.kind == "release" else "Repository updates",
        "summary": event["summary"] if group.kind == "release" else "",
        "url": event["url"] if group.kind == "release" else event["repositoryUrl"],
        "publishedAt": group.published_at.isoformat() if group.published_at else None,
        "createdAt": group.created_at.isoformat(),
        "eventCount": group.event_count, "commitCount": group.commit_count,
        "unreadEventCount": group.unread_event_count, "isRead": group.unread_event_count == 0,
    }


def get_feed_groups_payload(
    user_id: str, *, database_url: str, limit: int = DEFAULT_GROUP_PAGE_SIZE,
    cursor: str | None = None, state: str = "all", subscription_id: str | None = None,
) -> dict[str, object]:
    _validate_limit(limit)
    if state not in {"all", "unread"}:
        raise ValueError("Feed state must be 'all' or 'unread'.")
    decoded = _decode_cursor(cursor, kind="groups") if cursor is not None else None
    position = FeedGroupCursor(
        datetime.fromisoformat(cast(str, decoded["publishedAt"])) if decoded["publishedAt"] else None,
        datetime.fromisoformat(cast(str, decoded["createdAt"])), cast(str, decoded["groupId"]),
    ) if decoded else None
    groups = list_feed_group_summaries_for_user(
        user_id, database_url=database_url, limit=limit + 1, cursor=position,
        unread_only=state == "unread", subscription_id=subscription_id,
    )
    visible = groups[:limit]
    next_cursor = None
    if len(groups) > limit:
        last = visible[-1]
        next_cursor = _encode_cursor({"type": "groups", "groupId": last.group_id,
                                      "publishedAt": last.published_at.isoformat() if last.published_at else None,
                                      "createdAt": last.created_at.isoformat()})
    return {"items": [_group_payload(group) for group in visible], "nextCursor": next_cursor,
            "hasMore": next_cursor is not None,
            "unreadCount": count_unread_feed_groups_for_user(user_id, database_url=database_url)}


def _event_detail(event: FeedEvent) -> dict[str, object]:
    return {**to_feed_item_payload(event), "rawText": event.raw_text,
            "normalizedText": event.normalized_text, "metadata": dict(event.metadata)}


def get_feed_group_detail_payload(
    user_id: str, group_id: str, *, database_url: str,
    limit: int = DEFAULT_COMMIT_PAGE_SIZE, cursor: str | None = None,
) -> dict[str, object] | None:
    _validate_limit(limit)
    decoded = _decode_cursor(cursor, kind="commits", group_id=group_id) if cursor is not None else None
    position = FeedCursor(
        datetime.fromisoformat(cast(str, decoded["publishedAt"])) if decoded["publishedAt"] else None,
        datetime.fromisoformat(cast(str, decoded["createdAt"])), cast(str, decoded["eventId"]),
    ) if decoded else None
    groups = list_feed_group_summaries_for_user(user_id, database_url=database_url, limit=1, group_id=group_id)
    if not groups:
        return None
    group = groups[0]
    commits = list_feed_group_commits_for_user(user_id, group_id, database_url=database_url,
                                             limit=limit + 1, cursor=position)
    visible = commits[:limit]
    next_cursor = None
    if len(commits) > limit:
        last = visible[-1]
        if last.created_at is None:
            raise RuntimeError("A persisted Feed event requires creation time.")
        next_cursor = _encode_cursor({"type": "commits", "groupId": group_id, "eventId": last.event_id,
                                      "publishedAt": last.published_at.isoformat() if last.published_at else None,
                                      "createdAt": last.created_at.isoformat()})
    return {**_group_payload(group),
            "release": _event_detail(group.representative) if group.kind == "release" else None,
            "commits": [to_feed_item_payload(event) for event in visible],
            "nextCursor": next_cursor, "hasMore": next_cursor is not None}


def mark_feed_group_read_payload(user_id: str, group_id: str, *, database_url: str) -> dict[str, object] | None:
    if not mark_feed_group_read_for_user(user_id, group_id, database_url=database_url):
        return None
    groups = list_feed_group_summaries_for_user(user_id, database_url=database_url, limit=1, group_id=group_id)
    return _group_payload(groups[0]) if groups else None
