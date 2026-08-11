"""Cookie-backed authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import secrets

from fastapi import Request, Response

from app.config import (
    AUTH_SESSION_COOKIE_DOMAIN,
    AUTH_SESSION_COOKIE_NAME,
    AUTH_SESSION_SAMESITE,
    AUTH_SESSION_SECURE,
    AUTH_SESSION_TTL_SECONDS,
)
from app.storage.auth import (
    create_user_session,
    get_authenticated_session_by_token_hash,
    revoke_user_session_by_token_hash,
    touch_user_session,
)


@dataclass(frozen=True)
class User:
    """Minimal authenticated viewer projection."""

    user_id: str
    email: str
    display_name: str
    avatar_url: str | None = None


def get_current_user(request: Request) -> User | None:
    """Resolve the signed-in user from the current session cookie."""

    session_record = _get_authenticated_session(request)
    if session_record is None:
        return None

    touch_user_session(session_record.session.session_id)
    return User(
        user_id=session_record.user.user_id,
        email=session_record.user.email,
        display_name=session_record.user.display_name,
        avatar_url=session_record.user.avatar_url,
    )


def create_authenticated_session(user_id: str, response: Response) -> str:
    """Create one durable session and attach its cookie to the response."""

    session_token = secrets.token_urlsafe(48)
    create_user_session(
        user_id=user_id,
        session_token_hash=_hash_session_token(session_token),
        expires_at=_utc_now() + timedelta(seconds=AUTH_SESSION_TTL_SECONDS),
    )
    _set_session_cookie(response, session_token)
    return session_token


def sign_out_current_user(request: Request, response: Response) -> None:
    """Revoke the current session cookie if present and clear the browser cookie."""

    session_token = _read_session_token(request)
    if session_token:
        revoke_user_session_by_token_hash(_hash_session_token(session_token))
    _clear_session_cookie(response)


def _get_authenticated_session(request: Request):
    session_token = _read_session_token(request)
    if not session_token:
        return None
    return get_authenticated_session_by_token_hash(_hash_session_token(session_token))


def _read_session_token(request: Request) -> str | None:
    raw_value = request.cookies.get(AUTH_SESSION_COOKIE_NAME, "").strip()
    if not raw_value:
        return None
    return raw_value


def _hash_session_token(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def _set_session_cookie(response: Response, session_token: str) -> None:
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


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_SESSION_COOKIE_NAME,
        httponly=True,
        secure=AUTH_SESSION_SECURE,
        samesite=AUTH_SESSION_SAMESITE,
        path="/",
        domain=AUTH_SESSION_COOKIE_DOMAIN or None,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
