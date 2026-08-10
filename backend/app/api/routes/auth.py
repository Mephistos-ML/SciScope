"""Development auth routes."""

from __future__ import annotations

from app.services.auth import get_current_user, sign_in_dev_user, sign_out_current_user


def get_me_response() -> dict[str, object]:
    """Return the current user if signed in."""

    user = get_current_user()
    return {"user": _serialize_user(user) if user else None}


def dev_login_response() -> dict[str, object]:
    """Sign in the local development user."""

    user = sign_in_dev_user()
    return {"user": _serialize_user(user)}


def logout_response() -> dict[str, object]:
    """Clear the current user."""

    sign_out_current_user()
    return {"user": None}


def _serialize_user(user) -> dict[str, object]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "displayName": user.display_name,
    }
