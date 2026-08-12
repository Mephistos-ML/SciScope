"""Subscription routes for the current user."""

from __future__ import annotations

from fastapi import Request

from app.services.auth import get_current_user
from app.services.subscriptions import (
    create_subscription_payload,
    delete_subscription_payload,
    list_subscription_payloads,
)


def get_subscription_list_response(request: Request) -> dict[str, object] | None:
    """Return saved subscriptions for the signed-in user."""

    user = get_current_user(request)
    if user is None:
        return None
    return list_subscription_payloads(user)


def create_subscription_response(
    request: Request,
    payload: dict[str, object],
) -> dict[str, object] | None:
    """Create one subscription for the signed-in user."""

    user = get_current_user(request)
    if user is None:
        return None

    topic_description = str(payload.get("topicDescription") or "").strip()
    search_scope = str(payload.get("searchScope") or "repositories")
    if not topic_description:
        topic_description = "Untitled topic"

    return create_subscription_payload(
        user,
        topic_description=topic_description,
        search_scope=(
            search_scope if search_scope in ("repositories", "all") else "repositories"
        ),
    )


def delete_subscription_response(request: Request, subscription_id: str) -> bool | None:
    """Delete one saved subscription for the signed-in user."""

    user = get_current_user(request)
    if user is None:
        return None

    return delete_subscription_payload(user, subscription_id)
