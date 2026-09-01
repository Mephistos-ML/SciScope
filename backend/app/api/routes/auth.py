"""Auth routes backed by first-party user sessions and Google OAuth."""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from app.services.auth import (
    build_google_auth_redirect_response,
    complete_google_auth_callback,
    get_current_user,
    sign_out_current_user,
)
from app.services.features import get_enabled_features


def get_me_response(request: Request) -> dict[str, object]:
    """Return the current user if signed in."""

    user = get_current_user(request, database_url=request.app.state.database_url)
    return {"user": _serialize_user(user) if user else None}

def logout_response(request: Request, response: Response) -> dict[str, object]:
    """Clear the current user."""

    sign_out_current_user(
        request,
        response,
        database_url=request.app.state.database_url,
    )
    return {"user": None}


def start_google_auth_response() -> RedirectResponse:
    """Start one Google OAuth redirect flow."""

    return build_google_auth_redirect_response()


def finish_google_auth_response(request: Request) -> RedirectResponse:
    """Finish one Google OAuth redirect flow."""

    return complete_google_auth_callback(
        request,
        database_url=request.app.state.database_url,
    )


def _serialize_user(user) -> dict[str, object]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "displayName": user.display_name,
        "avatarUrl": user.avatar_url,
        "features": list(get_enabled_features(user.email)),
    }
