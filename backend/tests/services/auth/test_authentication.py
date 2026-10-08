"""Authentication invariants through explicit credentials and callback facts."""

from datetime import UTC, datetime, timedelta
import hashlib
from types import SimpleNamespace

import pytest

from app.models.auth import GoogleAuthError
from app.services.auth.service import (
    complete_google_auth, create_authenticated_session, get_authenticated_user,
    revoke_authenticated_session, delete_authenticated_user_account,
)
from app.storage.auth.users import create_user, get_user_by_id
from app.storage.auth.user_sessions import create_user_session, get_authenticated_session_by_token_hash
from tests.fixtures.database import build_test_database_url, migrate_test_database


@pytest.mark.parametrize("facts,code", [
    ({"provider_error": "access_denied"}, "google_access_denied"),
    ({"expected_state": None}, "google_session_expired"),
    ({"expected_nonce": None}, "google_session_expired"),
    ({"returned_state": "wrong"}, "google_state_mismatch"),
    ({"returned_state": "неправильний"}, "google_state_mismatch"),
    ({"authorization_code": ""}, "google_missing_code"),
])
def test_invalid_callback_cannot_call_provider_or_create_session(facts, code):
    def authenticate(*args, **kwargs):
        pytest.fail("Invalid callback must stop before external IO")
    values = dict(provider=SimpleNamespace(authenticate=authenticate), expected_state="state",
                  expected_nonce="nonce", returned_state="state", authorization_code="code",
                  provider_error="", session_ttl_seconds=3600, database_url="unused")
    values.update(facts)
    with pytest.raises(GoogleAuthError) as failure:
        complete_google_auth(**values)
    assert failure.value.code == code


def test_session_credentials_are_hashed_expire_and_can_be_revoked(tmp_path):
    url = build_test_database_url(tmp_path / "sessions.sqlite3")
    migrate_test_database(url)
    user = create_user(email="scientist@example.test", display_name="Scientist", database_url=url)
    token = create_authenticated_session(user.user_id, ttl_seconds=3600, database_url=url)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = get_authenticated_session_by_token_hash(token_hash, database_url=url)
    assert stored.session.session_token_hash == token_hash != token
    assert get_authenticated_user(token, database_url=url).user_id == user.user_id
    assert get_authenticated_user(None, database_url=url) is None
    assert get_authenticated_user("unknown-token", database_url=url) is None
    expired = "expired-token"
    create_user_session(user_id=user.user_id, session_token_hash=hashlib.sha256(expired.encode()).hexdigest(),
                        expires_at=datetime.now(UTC) - timedelta(seconds=60), database_url=url)
    assert get_authenticated_user(expired, database_url=url) is None
    revoke_authenticated_session(token, database_url=url)
    assert get_authenticated_user(token, database_url=url) is None


def test_account_deletion_uses_authenticated_owner_and_revokes_sessions(tmp_path):
    url = build_test_database_url(tmp_path / "deletion.sqlite3")
    migrate_test_database(url)
    owner = create_user(email="owner@example.test", display_name="Owner", database_url=url)
    other = create_user(email="other@example.test", display_name="Other", database_url=url)
    token = create_authenticated_session(owner.user_id, ttl_seconds=3600, database_url=url)
    second = create_authenticated_session(owner.user_id, ttl_seconds=3600, database_url=url)
    assert not delete_authenticated_user_account("untrusted-token", database_url=url)
    assert delete_authenticated_user_account(token, database_url=url)
    assert get_user_by_id(owner.user_id, database_url=url) is None
    assert get_user_by_id(other.user_id, database_url=url) is not None
    assert get_authenticated_user(second, database_url=url) is None


def test_oauth_flow_credentials_are_unique_and_hidden_from_repr():
    from app.services.auth.service import begin_google_auth
    provider = SimpleNamespace(authorization_url=lambda *, state, nonce: f"https://example.test?state={state}&nonce={nonce}")
    first, second = begin_google_auth(provider=provider), begin_google_auth(provider=provider)
    assert len({first.state, first.nonce, second.state, second.nonce}) == 4
    assert first.state in first.redirect_url and first.nonce in first.redirect_url
    assert first.state not in repr(first) and first.nonce not in repr(first)
