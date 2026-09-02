"""Tests for GitHub source auth and low-level HTTP configuration."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

import pytest

from app.sources.common import RepositorySourceError
from app.sources.github import auth as github_auth
from app.sources.github import client as github_client


def test_build_auth_headers_fails_when_github_source_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(github_auth, "GITHUB_AUTH_MODE", "disabled")

    with pytest.raises(RepositorySourceError) as exc_info:
        github_auth.build_auth_headers()

    assert exc_info.value.status == "disabled"


def test_build_auth_headers_fails_when_github_app_settings_are_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(github_auth, "GITHUB_AUTH_MODE", "app")
    monkeypatch.setattr(github_auth, "GITHUB_APP_ID", "")
    monkeypatch.setattr(github_auth, "GITHUB_APP_INSTALLATION_ID", "")
    monkeypatch.setattr(github_auth, "GITHUB_APP_PRIVATE_KEY", "")

    with pytest.raises(RepositorySourceError) as exc_info:
        github_auth.build_auth_headers()

    assert exc_info.value.status == "misconfigured"
    assert "GITHUB_APP_ID" in exc_info.value.public_message


def test_build_auth_headers_uses_github_app_installation_token(monkeypatch) -> None:
    monkeypatch.setattr(github_auth, "GITHUB_AUTH_MODE", "app")
    monkeypatch.setattr(github_auth, "GITHUB_APP_ID", "123456")
    monkeypatch.setattr(github_auth, "GITHUB_APP_INSTALLATION_ID", "789012")
    monkeypatch.setattr(
        github_auth,
        "GITHUB_APP_PRIVATE_KEY",
        "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----",
    )
    monkeypatch.setattr(
        github_auth,
        "_get_installation_access_token",
        lambda: "installation-token",
    )

    assert github_auth.build_auth_headers() == {
        "Authorization": "Bearer installation-token"
    }


def test_fetch_json_includes_auth_headers(monkeypatch) -> None:
    captured_headers: dict[str, str] = {}

    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self, *_args, **_kwargs) -> bytes:
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):  # type: ignore[no-untyped-def]
        del timeout
        captured_headers.update(dict(request.header_items()))
        return _FakeResponse()

    monkeypatch.setattr(github_client, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        github_client,
        "build_auth_headers",
        lambda: {"Authorization": "Bearer installation-token"},
    )

    payload = github_client.fetch_json("https://api.github.com/test")

    assert payload == {"ok": True}
    assert captured_headers["Authorization"] == "Bearer installation-token"
    assert captured_headers["Accept"] == "application/vnd.github+json"
    assert captured_headers["X-github-api-version"] == "2022-11-28"


def test_fetch_json_classifies_rate_limits(monkeypatch) -> None:
    monkeypatch.setattr(github_client, "build_auth_headers", lambda: {"Authorization": "Bearer token"})

    def fake_urlopen(_request, timeout):  # type: ignore[no-untyped-def]
        del timeout
        raise HTTPError(
            url="https://api.github.com/test",
            code=403,
            msg="Forbidden",
            hdrs={"X-RateLimit-Remaining": "0"},
            fp=None,
        )

    monkeypatch.setattr(github_client, "urlopen", fake_urlopen)

    with pytest.raises(RepositorySourceError) as exc_info:
        github_client.fetch_json("https://api.github.com/test")

    assert exc_info.value.status == "rate_limited"


def test_fetch_json_reads_rate_limit_retry_after(monkeypatch) -> None:
    monkeypatch.setattr(github_client, "build_auth_headers", lambda: {"Authorization": "Bearer token"})

    def fake_urlopen(_request, timeout):  # type: ignore[no-untyped-def]
        del timeout
        raise HTTPError(
            url="https://api.github.com/test",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "134"},
            fp=None,
        )

    monkeypatch.setattr(github_client, "urlopen", fake_urlopen)

    with pytest.raises(RepositorySourceError) as exc_info:
        github_client.fetch_json("https://api.github.com/test")

    assert exc_info.value.status == "rate_limited"
    assert exc_info.value.retry_after_seconds == 134


def test_fetch_json_classifies_transport_timeouts(monkeypatch) -> None:
    monkeypatch.setattr(
        github_client,
        "build_auth_headers",
        lambda: {"Authorization": "Bearer token"},
    )

    def fake_urlopen(_request, timeout):  # type: ignore[no-untyped-def]
        del timeout
        raise URLError(TimeoutError("The read operation timed out"))

    monkeypatch.setattr(github_client, "urlopen", fake_urlopen)

    with pytest.raises(RepositorySourceError) as exc_info:
        github_client.fetch_json("https://api.github.com/test")

    assert exc_info.value.status == "timed_out"
