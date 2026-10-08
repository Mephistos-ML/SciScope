"""HTTP cookie extraction and response representation for authentication."""

from urllib.parse import urlencode, urlsplit, urlunsplit
from fastapi import Request, Response, status
from fastapi.responses import RedirectResponse

from app.config import (
    AUTH_SESSION_COOKIE_DOMAIN, AUTH_SESSION_COOKIE_NAME, AUTH_SESSION_SAMESITE,
    AUTH_SESSION_SECURE, AUTH_SESSION_TTL_SECONDS, FRONTEND_BASE_URL,
)
from app.models.auth import User, AuthConfigurationError
from app.services.auth.service import get_authenticated_user

GOOGLE_OAUTH_FLOW_TTL_SECONDS = 600
GOOGLE_OAUTH_STATE_COOKIE_NAME = f"{AUTH_SESSION_COOKIE_NAME}_google_state"
GOOGLE_OAUTH_NONCE_COOKIE_NAME = f"{AUTH_SESSION_COOKIE_NAME}_google_nonce"


def read_session_token(request: Request) -> str | None:
    return request.cookies.get(AUTH_SESSION_COOKIE_NAME, "").strip() or None


def get_current_user(request: Request, *, database_url: str) -> User | None:
    """Resolve the HTTP session credential through the authentication use case."""
    return get_authenticated_user(read_session_token(request), database_url=database_url)


def read_flow_cookie(request: Request, name: str) -> str | None:
    return request.cookies.get(name, "").strip() or None


def frontend_auth_destination() -> str:
    if not FRONTEND_BASE_URL:
        raise AuthConfigurationError("Google OAuth is not configured: missing FRONTEND_BASE_URL")
    return FRONTEND_BASE_URL.rstrip("/")


def set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        value=session_token,
        max_age=AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def set_flow_cookie(response: Response, cookie_name: str, value: str) -> None:
    response.set_cookie(
        key=cookie_name,
        value=value,
        max_age=GOOGLE_OAUTH_FLOW_TTL_SECONDS,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def _clear_short_lived_cookie(response: Response, cookie_name: str) -> None:
    response.delete_cookie(
        key=cookie_name,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def build_frontend_auth_redirect(*, error: str | None = None) -> RedirectResponse:
    frontend_base_url = frontend_auth_destination()
    redirect_url = frontend_base_url
    if error is not None:
        parts = urlsplit(frontend_base_url)
        redirect_url = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode({"authError": error}),
                "",
            )
        )

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    _clear_short_lived_cookie(response, GOOGLE_OAUTH_STATE_COOKIE_NAME)
    _clear_short_lived_cookie(response, GOOGLE_OAUTH_NONCE_COOKIE_NAME)
    return response
