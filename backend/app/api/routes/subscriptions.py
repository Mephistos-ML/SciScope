"""Subscription routes for the current user."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.auth import get_current_user
from app.services.subscriptions.service import (
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

    repository_payload = payload.get("repository")
    repository = repository_payload if isinstance(repository_payload, dict) else {}
    repository_item_id = str(repository.get("itemId") or "").strip()
    repository_source = str(repository.get("source") or "").strip()
    repository_full_name = str(repository.get("fullName") or "").strip()
    repository_url = str(repository.get("url") or "").strip()
    selected_query = str(payload.get("selectedQuery") or "").strip() or None

    if (
        not repository_item_id
        or not repository_source
        or not repository_full_name
        or not repository_url
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository subscription payload is incomplete.",
        )

    return create_subscription_payload(
        user,
        repository_item_id=repository_item_id,
        repository_source=repository_source,
        repository_full_name=repository_full_name,
        repository_url=repository_url,
        selected_query=selected_query,
    )


def delete_subscription_response(request: Request, subscription_id: str) -> bool | None:
    """Delete one saved subscription for the signed-in user."""

    user = get_current_user(request)
    if user is None:
        return None

    return delete_subscription_payload(user, subscription_id)
