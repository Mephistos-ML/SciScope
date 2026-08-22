"""Persistence helpers for auth-owned records."""

from app.storage.auth.oauth_accounts import (
    OAuthAccountRecord,
    create_oauth_account,
    get_oauth_account_by_provider_subject,
    update_oauth_account,
)
from app.storage.auth.user_sessions import (
    AuthenticatedSessionRecord,
    UserSessionRecord,
    create_user_session,
    get_authenticated_session_by_token_hash,
    revoke_user_session_by_token_hash,
    touch_user_session,
)
from app.storage.auth.users import (
    UserRecord,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
)

__all__ = [
    "AuthenticatedSessionRecord",
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
