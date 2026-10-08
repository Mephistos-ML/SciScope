"""HTTP authentication routes, cookies, and redirects."""

import logging

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.api.auth import (
    get_current_user, read_session_token, read_flow_cookie, set_session_cookie,
    clear_session_cookie, set_flow_cookie, build_frontend_auth_redirect, frontend_auth_destination,
    GOOGLE_OAUTH_STATE_COOKIE_NAME, GOOGLE_OAUTH_NONCE_COOKIE_NAME,
)
from app.config import AUTH_SESSION_TTL_SECONDS
from app.models.auth import User, GoogleAuthError, AuthConfigurationError
from app.services.auth.service import (
    begin_google_auth, complete_google_auth, delete_authenticated_user_account,
    revoke_authenticated_session,
)
from app.services.features.access import get_enabled_features


def get_me_response(request: Request) -> dict[str, object]:
    user = get_current_user(request, database_url=request.app.state.database_url)
    return {"user": _serialize_user(user) if user else None}


def logout_response(request: Request, response: Response) -> dict[str, object]:
    revoke_authenticated_session(read_session_token(request), database_url=request.app.state.database_url)
    clear_session_cookie(response)
    return {"user": None}


def delete_account_response(request: Request, response: Response) -> dict[str, bool]:
    deleted = delete_authenticated_user_account(read_session_token(request), database_url=request.app.state.database_url)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    clear_session_cookie(response)
    return {"deleted": True}


def start_google_auth_response(request: Request) -> RedirectResponse:
    # Validate the return destination before issuing flow credentials.
    frontend_auth_destination()
    flow = begin_google_auth(provider=request.app.state.google_oauth)
    response = RedirectResponse(flow.redirect_url, status_code=status.HTTP_302_FOUND)
    set_flow_cookie(response, GOOGLE_OAUTH_STATE_COOKIE_NAME, flow.state)
    set_flow_cookie(response, GOOGLE_OAUTH_NONCE_COOKIE_NAME, flow.nonce)
    return response


def finish_google_auth_response(request: Request) -> RedirectResponse:
    # Callback is an intentional isolation boundary: always clear flow cookies.
    response = build_frontend_auth_redirect()
    try:
        token = complete_google_auth(
            provider=request.app.state.google_oauth,
            expected_state=read_flow_cookie(request, GOOGLE_OAUTH_STATE_COOKIE_NAME),
            expected_nonce=read_flow_cookie(request, GOOGLE_OAUTH_NONCE_COOKIE_NAME),
            returned_state=request.query_params.get("state", "").strip(),
            authorization_code=request.query_params.get("code", "").strip(),
            provider_error=request.query_params.get("error", "").strip(),
            session_ttl_seconds=AUTH_SESSION_TTL_SECONDS,
            database_url=request.app.state.database_url,
        )
    except GoogleAuthError as exc:
        logging.getLogger(__name__).warning("OAuth callback rejected: %s", exc.code)
        return build_frontend_auth_redirect(error=exc.code)
    except AuthConfigurationError:
        raise
    except Exception:
        logging.getLogger(__name__).exception("OAuth callback could not establish a session.")
        return build_frontend_auth_redirect(error="google_auth_failed")
    set_session_cookie(response, token)
    return response


def _serialize_user(user: User) -> dict[str, object]:
    return {
        "userId": user.user_id, "email": user.email, "displayName": user.display_name,
        "avatarUrl": user.avatar_url, "features": list(get_enabled_features(user.email)),
    }
