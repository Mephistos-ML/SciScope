"""Persistence helpers for auth-owned records."""

from datetime import datetime

from app.config import DATABASE_URL
from app.storage.auth import oauth_accounts as oauth_account_storage
from app.storage.auth import user_sessions as user_session_storage
from app.storage.auth import users as user_storage
from app.storage.auth.oauth_accounts import (
    OAuthAccountRecord,
)
from app.storage.auth.user_sessions import (
    AuthenticatedSessionRecord,
    UserSessionRecord,
)
from app.storage.auth.users import (
    UserRecord,
)


def create_user(
    *,
    email: str,
    display_name: str,
    avatar_url: str | None = None,
    user_id: str | None = None,
    database_url: str | None = None,
) -> UserRecord:
    return user_storage.create_user(
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
        user_id=user_id,
        database_url=database_url or DATABASE_URL,
    )


def get_user_by_id(
    user_id: str,
    *,
    database_url: str | None = None,
) -> UserRecord | None:
    return user_storage.get_user_by_id(
        user_id,
        database_url=database_url or DATABASE_URL,
    )


def get_user_by_email(
    email: str,
    *,
    database_url: str | None = None,
) -> UserRecord | None:
    return user_storage.get_user_by_email(
        email,
        database_url=database_url or DATABASE_URL,
    )


def update_user(
    user_id: str,
    *,
    email: str,
    display_name: str,
    avatar_url: str | None,
    database_url: str | None = None,
) -> UserRecord:
    return user_storage.update_user(
        user_id,
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
        database_url=database_url or DATABASE_URL,
    )


def create_oauth_account(
    *,
    user_id: str,
    provider: str,
    provider_subject: str,
    provider_email: str | None,
    oauth_account_id: str | None = None,
    database_url: str | None = None,
) -> OAuthAccountRecord:
    return oauth_account_storage.create_oauth_account(
        user_id=user_id,
        provider=provider,
        provider_subject=provider_subject,
        provider_email=provider_email,
        oauth_account_id=oauth_account_id,
        database_url=database_url or DATABASE_URL,
    )


def get_oauth_account_by_provider_subject(
    provider: str,
    provider_subject: str,
    *,
    database_url: str | None = None,
) -> OAuthAccountRecord | None:
    return oauth_account_storage.get_oauth_account_by_provider_subject(
        provider,
        provider_subject,
        database_url=database_url or DATABASE_URL,
    )


def update_oauth_account(
    oauth_account_id: str,
    *,
    provider_email: str | None,
    database_url: str | None = None,
) -> OAuthAccountRecord:
    return oauth_account_storage.update_oauth_account(
        oauth_account_id,
        provider_email=provider_email,
        database_url=database_url or DATABASE_URL,
    )


def create_user_session(
    *,
    user_id: str,
    session_token_hash: str,
    expires_at: datetime,
    session_id: str | None = None,
    database_url: str | None = None,
) -> UserSessionRecord:
    return user_session_storage.create_user_session(
        user_id=user_id,
        session_token_hash=session_token_hash,
        expires_at=expires_at,
        session_id=session_id,
        database_url=database_url or DATABASE_URL,
    )


def get_authenticated_session_by_token_hash(
    session_token_hash: str,
    *,
    now: datetime | None = None,
    database_url: str | None = None,
) -> AuthenticatedSessionRecord | None:
    return user_session_storage.get_authenticated_session_by_token_hash(
        session_token_hash,
        now=now,
        database_url=database_url or DATABASE_URL,
    )


def touch_user_session(
    session_id: str,
    *,
    seen_at: datetime | None = None,
    database_url: str | None = None,
) -> None:
    user_session_storage.touch_user_session(
        session_id,
        seen_at=seen_at,
        database_url=database_url or DATABASE_URL,
    )


def revoke_user_session_by_token_hash(
    session_token_hash: str,
    *,
    revoked_at: datetime | None = None,
    database_url: str | None = None,
) -> bool:
    return user_session_storage.revoke_user_session_by_token_hash(
        session_token_hash,
        revoked_at=revoked_at,
        database_url=database_url or DATABASE_URL,
    )

__all__ = [
    "AuthenticatedSessionRecord",
    "DATABASE_URL",
    "OAuthAccountRecord",
    "UserRecord",
    "UserSessionRecord",
    "create_oauth_account",
    "create_user",
    "create_user_session",
    "get_authenticated_session_by_token_hash",
    "get_oauth_account_by_provider_subject",
    "get_user_by_email",
    "get_user_by_id",
    "revoke_user_session_by_token_hash",
    "touch_user_session",
    "update_oauth_account",
    "update_user",
]
