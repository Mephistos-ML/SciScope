"""Auth routes backed by first-party user sessions."""

from __future__ import annotations

from fastapi import Request, Response

from app.services.auth import get_current_user, sign_out_current_user


def get_me_response(request: Request) -> dict[str, object]:
    """Return the current user if signed in."""

    user = get_current_user(request)
    return {"user": _serialize_user(user) if user else None}

def logout_response(request: Request, response: Response) -> dict[str, object]:
    """Clear the current user."""

    sign_out_current_user(request, response)
    return {"user": None}


def _serialize_user(user) -> dict[str, object]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "displayName": user.display_name,
    }
