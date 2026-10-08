"""Google identity verification with real signatures and mocked external IO."""

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from types import SimpleNamespace
from urllib.parse import parse_qs

from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from app.integrations.identity import google
from app.models.auth import GoogleAuthError


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def client(signing_key):
    key_lookup = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=signing_key.public_key()))
    return google.GoogleOAuthClient("client-id", "client-secret", "https://example.test/callback", key_lookup)


def token(signing_key, **changes):
    claims = {"iss": "https://accounts.google.com", "aud": "client-id",
              "exp": int(datetime.now(UTC).timestamp()) + 3600, "sub": "provider-subject",
              "nonce": "expected-nonce", "email": "Scientist@Example.test", "email_verified": True,
              "name": "Scientist"}
    claims.update(changes)
    claims = {key: value for key, value in claims.items() if value is not None}
    return jwt.encode(claims, signing_key, algorithm="RS256")


def respond(monkeypatch, body, captured=None):
    @contextmanager
    def open_response(request, *, timeout):
        if captured is not None:
            captured.update(url=request.full_url, form=parse_qs(request.data.decode()), timeout=timeout)
        class Response:
            def read(self, limit):
                return body[:limit]
        yield Response()
    monkeypatch.setattr(google, "urlopen", open_response)


def test_google_exchange_maps_verified_identity(monkeypatch, signing_key):
    captured = {}
    respond(monkeypatch, json.dumps({"id_token": token(signing_key)}).encode(), captured)
    provider = client(signing_key)
    identity = provider.authenticate("authorization-code", expected_nonce="expected-nonce")
    assert identity.subject == "provider-subject"
    assert identity.email == "scientist@example.test"
    assert captured["url"] == google.GOOGLE_TOKEN_URL
    assert captured["form"]["code"] == ["authorization-code"]
    assert captured["form"]["client_secret"] == ["client-secret"]
    assert captured["form"]["redirect_uri"] == ["https://example.test/callback"]
    assert captured["timeout"] == 15
    assert "client-secret" not in repr(provider)


@pytest.mark.parametrize("changes", [
    {"nonce": "wrong"}, {"aud": "other-client"}, {"iss": "https://attacker.test"},
    {"exp": 1}, {"exp": None}, {"email_verified": False}, {"email_verified": "true"},
    {"email": ["scientist@example.test"]}, {"sub": None},
])
def test_invalid_signed_identity_cannot_become_application_user(monkeypatch, signing_key, changes):
    respond(monkeypatch, json.dumps({"id_token": token(signing_key, **changes)}).encode())
    with pytest.raises(GoogleAuthError) as failure:
        client(signing_key).authenticate("code", expected_nonce="expected-nonce")
    assert failure.value.code == "google_auth_failed"


def test_invalid_signature_is_rejected(monkeypatch, signing_key):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    respond(monkeypatch, json.dumps({"id_token": token(other_key)}).encode())
    with pytest.raises(GoogleAuthError):
        client(signing_key).authenticate("code", expected_nonce="expected-nonce")


@pytest.mark.parametrize("body", [b"[]", b"{}", b'{"id_token":1}', b"not json", b"x" * 65537])
def test_unusable_token_response_is_controlled_failure(monkeypatch, signing_key, body):
    respond(monkeypatch, body)
    with pytest.raises(GoogleAuthError):
        client(signing_key).authenticate("code", expected_nonce="expected-nonce")


def test_provider_timeout_is_stable_auth_failure(monkeypatch, signing_key):
    def unavailable(*args, **kwargs):
        raise TimeoutError("private provider diagnostics")
    monkeypatch.setattr(google, "urlopen", unavailable)
    with pytest.raises(GoogleAuthError) as failure:
        client(signing_key).authenticate("code", expected_nonce="expected-nonce")
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert "private" not in str(failure.value)
