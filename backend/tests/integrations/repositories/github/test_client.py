"""Tests for GitHub source auth and low-level HTTP configuration."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

import pytest

from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github import auth as github_auth
from app.integrations.repositories.github import client as github_client


def test_build_auth_headers_fails_when_github_source_is_disabled(monkeypatch) -> None:
    auth = github_auth.GitHubAppAuth("disabled", "", "", "")

    with pytest.raises(RepositorySourceError) as exc_info:
        auth.build_auth_headers()

    assert exc_info.value.status == "disabled"


def test_build_auth_headers_fails_when_github_app_settings_are_missing(
    monkeypatch,
) -> None:
    auth = github_auth.GitHubAppAuth("app", "", "", "")

    with pytest.raises(RepositorySourceError) as exc_info:
        auth.build_auth_headers()

    assert exc_info.value.status == "misconfigured"
    assert "GITHUB_APP_ID" in exc_info.value.public_message


def test_build_auth_headers_uses_github_app_installation_token(monkeypatch) -> None:
    auth = github_auth.GitHubAppAuth("app", "123456", "789012", "private-key")
    monkeypatch.setattr(github_auth.GitHubAppAuth, "_get_installation_access_token", lambda self: "installation-token")

    assert auth.build_auth_headers() == {
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
    client = github_client.GitHubClient(lambda: {"Authorization": "Bearer installation-token"})

    response = client.fetch_json("https://api.github.com/test")

    assert response.payload == {"ok": True}
    assert response.url == "https://api.github.com/test"
    assert captured_headers["Authorization"] == "Bearer installation-token"
    assert captured_headers["Accept"] == "application/vnd.github+json"
    assert captured_headers["X-github-api-version"] == "2022-11-28"


def test_fetch_json_classifies_rate_limits(monkeypatch) -> None:
    client = github_client.GitHubClient(lambda: {"Authorization": "Bearer token"})

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
        client.fetch_json("https://api.github.com/test")

    assert exc_info.value.status == "rate_limited"


def test_fetch_json_reads_rate_limit_retry_after(monkeypatch) -> None:
    client = github_client.GitHubClient(lambda: {"Authorization": "Bearer token"})

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
        client.fetch_json("https://api.github.com/test")

    assert exc_info.value.status == "rate_limited"
    assert exc_info.value.retry_after_seconds == 134


def test_fetch_json_classifies_transport_timeouts(monkeypatch) -> None:
    sleeps = []
    monkeypatch.setattr(github_client.time, "sleep", sleeps.append)
    attempts = []
    client = github_client.GitHubClient(lambda: {"Authorization": "Bearer token"})

    def fake_urlopen(_request, timeout):  # type: ignore[no-untyped-def]
        attempts.append(timeout)
        raise URLError(TimeoutError("The read operation timed out"))

    monkeypatch.setattr(github_client, "urlopen", fake_urlopen)

    with pytest.raises(RepositorySourceError) as exc_info:
        client.fetch_json("https://api.github.com/test")

    assert exc_info.value.status == "timed_out"

    assert len(attempts) == github_client.GITHUB_REQUEST_RETRIES
    assert sleeps == [
        github_client.GITHUB_RETRY_BACKOFF_SECONDS * attempt
        for attempt in range(1, github_client.GITHUB_REQUEST_RETRIES)
    ]
