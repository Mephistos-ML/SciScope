"""Transport-independent authentication and session use cases."""

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from typing import Protocol

from app.models.auth import User, GoogleIdentity, GoogleAuthFlow, GoogleAuthError
from app.storage.auth.oauth_accounts import (
    create_oauth_account,
    get_oauth_account_by_provider_subject,
    update_oauth_account,
)
from app.storage.auth.user_sessions import (
    create_user_session,
    get_authenticated_session_by_token_hash,
    revoke_user_session_by_token_hash,
    touch_user_session,
)
from app.storage.auth.users import (
    UserRecord,
    create_user,
    delete_user_account,
    get_user_by_email,
    update_user,
)


GOOGLE_PROVIDER = "google"


class GoogleOAuth(Protocol):
    """Capability for Google authorization URLs and verified callback identities."""

    def authorization_url(self, *, state: str, nonce: str) -> str: ...
    def authenticate(self, code: str, *, expected_nonce: str) -> GoogleIdentity: ...


def get_authenticated_user(session_token: str | None, *, database_url: str) -> User | None:
    """Resolve an active, unexpired session from an explicit bearer token."""
    if not session_token:
        return None
    session_record = get_authenticated_session_by_token_hash(
        _hash_session_token(session_token), database_url=database_url,
    )
    if session_record is None:
        return None
    touch_user_session(session_record.session.session_id, database_url=database_url)
    return _to_user(session_record.user)


def create_authenticated_session(user_id: str, *, ttl_seconds: int, database_url: str) -> str:
    """Persist a hashed session credential; return the bearer token to the caller."""
    if ttl_seconds <= 0:
        raise ValueError("Session lifetime must be positive.")
    session_token = secrets.token_urlsafe(48)
    create_user_session(
        user_id=user_id, session_token_hash=_hash_session_token(session_token),
        expires_at=_utc_now() + timedelta(seconds=ttl_seconds), database_url=database_url,
    )
    return session_token


def begin_google_auth(*, provider: GoogleOAuth) -> GoogleAuthFlow:
    state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    return GoogleAuthFlow(provider.authorization_url(state=state, nonce=nonce), state, nonce)


def complete_google_auth(
    *, provider: GoogleOAuth, expected_state: str | None, expected_nonce: str | None,
    returned_state: str, authorization_code: str, provider_error: str,
    session_ttl_seconds: int, database_url: str,
) -> str:
    """Verify callback proof before provider IO or creating a first-party session."""
    if provider_error:
        raise GoogleAuthError("google_access_denied")
    if not expected_state or not expected_nonce:
        raise GoogleAuthError("google_session_expired")
    if not secrets.compare_digest(returned_state.encode("utf-8"), expected_state.encode("utf-8")):
        raise GoogleAuthError("google_state_mismatch")
    if not authorization_code:
        raise GoogleAuthError("google_missing_code")
    identity = provider.authenticate(authorization_code, expected_nonce=expected_nonce)
    user = upsert_google_user(identity, database_url=database_url)
    return create_authenticated_session(user.user_id, ttl_seconds=session_ttl_seconds, database_url=database_url)


def upsert_google_user(
    identity: GoogleIdentity,
    *,
    database_url: str,
) -> User:
    """Create or refresh one first-party user from a Google identity."""

    oauth_account = get_oauth_account_by_provider_subject(
        GOOGLE_PROVIDER,
        identity.subject,
        database_url=database_url,
    )

    if oauth_account is not None:
        user_record = update_user(
            oauth_account.user_id,
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
            database_url=database_url,
        )
        update_oauth_account(
            oauth_account.oauth_account_id,
            provider_email=identity.email,
            database_url=database_url,
        )
        return _to_user(user_record)

    existing_user = get_user_by_email(identity.email, database_url=database_url)
    if existing_user is not None:
        user_record = update_user(
            existing_user.user_id,
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
            database_url=database_url,
        )
    else:
        user_record = create_user(
            email=identity.email,
            display_name=identity.display_name,
            avatar_url=identity.avatar_url,
            database_url=database_url,
        )

    create_oauth_account(
        user_id=user_record.user_id,
        provider=GOOGLE_PROVIDER,
        provider_subject=identity.subject,
        provider_email=identity.email,
        database_url=database_url,
    )
    return _to_user(user_record)


def revoke_authenticated_session(session_token: str | None, *, database_url: str) -> None:
    if session_token:
        revoke_user_session_by_token_hash(_hash_session_token(session_token), database_url=database_url)


def delete_authenticated_user_account(session_token: str | None, *, database_url: str) -> bool:
    user = get_authenticated_user(session_token, database_url=database_url)
    return delete_user_account(user.user_id, database_url=database_url) if user else False


def _hash_session_token(session_token: str) -> str:
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


def _to_user(user_record: UserRecord) -> User:
    return User(
        user_id=user_record.user_id,
        email=user_record.email,
        display_name=user_record.display_name,
        avatar_url=user_record.avatar_url,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
