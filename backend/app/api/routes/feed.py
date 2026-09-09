"""Feed routes for the current user."""

from __future__ import annotations

from fastapi import Request

from app.services.auth import get_current_user
from app.services.feed import (
    get_feed_event_payload,
    get_feed_list_payload,
    mark_all_feed_events_read_payload,
    mark_feed_event_read_payload,
)


def get_feed_list_response(
    request: Request,
    *,
    limit: int,
    cursor: str | None,
    state: str,
) -> dict[str, object] | None:
    """Return durable feed events for the signed-in user."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    if user is None:
        return None
    return get_feed_list_payload(
        user.user_id,
        database_url=database_url,
        limit=limit,
        cursor=cursor,
        state=state,
    )


def get_feed_event_response(
    request: Request,
    event_id: str,
) -> dict[str, object] | None:
    """Return one feed event for the signed-in user."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    if user is None:
        return None
    return get_feed_event_payload(
        user.user_id,
        event_id,
        database_url=database_url,
    )


def mark_feed_event_read_response(
    request: Request,
    event_id: str,
) -> dict[str, object] | None:
    """Mark one Feed event as read for the signed-in user."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    if user is None:
        return None
    return mark_feed_event_read_payload(user.user_id, event_id, database_url=database_url)


def mark_all_feed_events_read_response(request: Request) -> dict[str, int] | None:
    """Mark every Feed event as read for the signed-in user."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    if user is None:
        return None
    return mark_all_feed_events_read_payload(user.user_id, database_url=database_url)
