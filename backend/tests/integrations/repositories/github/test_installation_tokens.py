"""Installation credentials and synchronized token reuse stay instance-scoped."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from io import BytesIO
import json
from threading import Barrier

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.integrations.repositories.github import auth
from app.integrations.repositories.common.source_status import RepositorySourceError


@pytest.fixture(scope="module")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return key, pem


def test_concurrent_requests_share_exchange_only_within_their_installation(monkeypatch, signing_key):
    key, pem = signing_key
    owners = [auth.GitHubAppAuth("app", "111", "123", pem),
              auth.GitHubAppAuth("app", "222", "456", pem)]
    exchanges = []
    def exchange(request, timeout):
        assert timeout == 30
        signed = request.get_header("Authorization").removeprefix("Bearer ")
        claims = jwt.decode(signed, key.public_key(), algorithms=["RS256"])
        installation = request.full_url.split("/")[-2]
        assert claims["iss"] == ("111" if installation == "123" else "222")
        exchanges.append(installation)
        return BytesIO(json.dumps({"token": f"secret-{installation}",
                                   "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}).encode())
    monkeypatch.setattr(auth, "urlopen", exchange)
    barrier = Barrier(12)
    def headers(index):
        barrier.wait(timeout=10)
        return owners[index % 2].build_auth_headers()
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(headers, range(12)))
    assert results == [{"Authorization": f"Bearer secret-{'123' if n % 2 == 0 else '456'}"} for n in range(12)]
    assert sorted(exchanges) == ["123", "456"]
    assert "secret-" not in repr(owners) and pem not in repr(owners)
    with pytest.raises(FrozenInstanceError):
        owners[0].installation_id = "456"


def test_refresh_buffer_and_failed_exchange_allow_a_later_retry(monkeypatch, signing_key):
    _, pem = signing_key
    current = datetime.now(UTC)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current
    monkeypatch.setattr(auth, "datetime", Clock)
    owner = auth.GitHubAppAuth("app", "111", "123", pem)
    calls = []
    def exchange(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 2:
            raise TimeoutError("private transport details")
        return BytesIO(json.dumps({"token": f"secret-{len(calls)}",
                                   "expires_at": (current + timedelta(seconds=120)).isoformat()}).encode())
    monkeypatch.setattr(auth, "urlopen", exchange)
    assert owner.build_auth_headers() == {"Authorization": "Bearer secret-1"}
    current += timedelta(seconds=59)
    assert owner.build_auth_headers() == {"Authorization": "Bearer secret-1"}
    current += timedelta(seconds=2)
    with pytest.raises(RepositorySourceError) as failure:
        owner.build_auth_headers()
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert "private transport details" not in str(failure.value)
    assert owner.build_auth_headers() == {"Authorization": "Bearer secret-3"}
    assert owner.build_auth_headers() == {"Authorization": "Bearer secret-3"}
    assert len(calls) == 3


@pytest.mark.parametrize("payload", [[], {}, {"token": 123},
                                    {"token": "secret", "expires_at": "invalid"},
                                    {"token": "secret", "expires_at": "2020-01-01T00:00:00Z"},
                                    {"token": "secret", "expires_at": "2099-01-01T00:00:00"}])
def test_invalid_exchange_cannot_poison_the_cache(monkeypatch, signing_key, payload):
    _, pem = signing_key
    owner = auth.GitHubAppAuth("app", "111", "123", pem)
    calls = []
    def exchange(request, timeout):
        calls.append(request.full_url)
        value = payload if len(calls) == 1 else {"token": "valid-secret",
                        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}
        return BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(auth, "urlopen", exchange)
    with pytest.raises(RepositorySourceError, match="invalid payload"):
        owner.build_auth_headers()
    assert owner.build_auth_headers() == {"Authorization": "Bearer valid-secret"}
    assert owner.build_auth_headers() == {"Authorization": "Bearer valid-secret"}
    assert len(calls) == 2


@pytest.mark.parametrize("body", [b"invalid-json", b" " * 65537])
def test_invalid_or_oversized_response_is_a_safe_provider_failure(monkeypatch, signing_key, body):
    _, pem = signing_key
    owner = auth.GitHubAppAuth("app", "111", "123", pem)
    monkeypatch.setattr(auth, "urlopen", lambda request, timeout: BytesIO(body))
    with pytest.raises(RepositorySourceError, match="invalid payload") as failure:
        owner.build_auth_headers()
    assert failure.value.__cause__ is not None
    assert pem not in str(failure.value)


@pytest.mark.parametrize("body,expected_status", [
    (b'{"message":"API rate limit exceeded"}', "rate_limited"),
    (b'invalid-json', "unauthorized"),
])
def test_exchange_classifies_http_error_body_and_remains_retryable(monkeypatch, signing_key, body, expected_status):
    from urllib.error import HTTPError

    _, pem = signing_key
    owner = auth.GitHubAppAuth("app", "111", "123", pem)
    exchanges = []

    def exchange(request, timeout):
        exchanges.append(request.full_url)
        if len(exchanges) == 1:
            raise HTTPError(request.full_url, 403, "Forbidden", {}, BytesIO(body))
        return BytesIO(json.dumps({"token": "recovered-secret",
                                  "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}).encode())

    monkeypatch.setattr(auth, "urlopen", exchange)
    with pytest.raises(RepositorySourceError) as failure:
        owner.build_auth_headers()
    assert failure.value.status == expected_status
    assert isinstance(failure.value.__cause__, HTTPError)
    assert owner.build_auth_headers() == {"Authorization": "Bearer recovered-secret"}
    assert len(exchanges) == 2
