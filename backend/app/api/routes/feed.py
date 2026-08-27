"""Feed routes for the current user."""

from __future__ import annotations

from fastapi import Request

from app.services.auth import get_current_user
from app.services.feed import get_feed_event_payload, get_feed_list_payload


def get_feed_list_response(request: Request) -> dict[str, object] | None:
    """Return durable feed events for the signed-in user."""

    database_url = request.app.state.database_url
    user = get_current_user(request, database_url=database_url)
    if user is None:
        return None
    return get_feed_list_payload(user.user_id, database_url=database_url)


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
