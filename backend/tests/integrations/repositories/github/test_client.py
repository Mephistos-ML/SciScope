# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Tests for GitHub source auth and low-level HTTP configuration."""

from __future__ import annotations

from urllib.error import HTTPError, URLError

import pytest
from io import BytesIO
from time import monotonic

from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github import auth as github_auth
from app.integrations.repositories.github import client as github_client


@pytest.mark.parametrize("bounded", [False, True])
@pytest.mark.parametrize("failures", [1, 2, 3])
@pytest.mark.parametrize("body", [b'{"items": ["unfinished', b"\xff"])
def test_malformed_json_has_one_bounded_retry_budget(
    monkeypatch, bounded, failures, body
):
    calls, sleeps, reservations = [], [], []

    def fetch(request, timeout):
        calls.append(request.full_url)
        return BytesIO(body if len(calls) <= failures else b'{"items": []}')

    monkeypatch.setattr(github_client, "urlopen", fetch)
    monkeypatch.setattr(github_client.time, "sleep", sleeps.append)
    monkeypatch.setattr(github_client.random, "uniform", lambda low, high: 0.25)
    client = github_client.GitHubClient(lambda: {}, before_attempt=reservations.append)
    kwargs = {"max_response_bytes": 4096} if bounded else {}
    if failures == 3:
        with pytest.raises(RepositorySourceError, match="invalid JSON") as error:
            client.fetch_json("https://api.github.com/search/code?q=science", **kwargs)
        assert error.value.__cause__ is not None
    else:
        assert client.fetch_json(
            "https://api.github.com/search/code?q=science", **kwargs
        ).payload == {"items": []}
    assert len(calls) == min(failures + 1, 3)
    assert reservations == calls
    assert sleeps == [1.75, 3.25][: min(failures, 2)]


def test_malformed_json_cannot_retry_past_deadline(monkeypatch):
    calls, sleeps = [], []
    now = monotonic()

    def fetch(request, timeout):
        calls.append(request.full_url)
        return BytesIO(b'{"broken')

    monkeypatch.setattr(github_client, "urlopen", fetch)
    monkeypatch.setattr(
        github_client, "read_response_body", lambda response, **kwargs: response.read()
    )
    monkeypatch.setattr(github_client.time, "sleep", sleeps.append)
    monkeypatch.setattr(github_client.random, "uniform", lambda low, high: 0.25)
    with pytest.raises(RepositorySourceError, match="invalid JSON"):
        github_client.GitHubClient(lambda: {}).fetch_json(
            "https://api.github.com/search/code?q=science",
            deadline_monotonic=now + 1,
        )
    assert len(calls) == 1
    assert sleeps == []


def test_decoder_resource_failure_is_not_retried(monkeypatch):
    calls = []

    def fetch(request, timeout):
        calls.append(request.full_url)
        return BytesIO(b"[]")

    def decode(*args, **kwargs):
        # Decoder nesting limits differ across Python implementations.
        raise RecursionError("decoder resource limit")

    monkeypatch.setattr(github_client, "urlopen", fetch)
    monkeypatch.setattr(github_client.json, "loads", decode)
    with pytest.raises(RepositorySourceError, match="invalid JSON"):
        github_client.GitHubClient(lambda: {}).fetch_json("https://api.github.com/test")
    assert len(calls) == 1


@pytest.mark.parametrize("failures", [1, 2, 3])
def test_http_408_has_bounded_retries_with_backoff(monkeypatch, failures):
    calls = []
    sleeps = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, *args):
            return b'{"items": []}'

    def fetch(request, timeout):
        calls.append(request.full_url)
        if len(calls) <= failures:
            raise HTTPError(
                request.full_url,
                408,
                "Request Timeout",
                {},
                BytesIO(b'{"message":"Request timed out"}'),
            )
        return Response()

    monkeypatch.setattr(github_client, "urlopen", fetch)
    monkeypatch.setattr(github_client.time, "sleep", sleeps.append)
    monkeypatch.setattr(github_client.random, "uniform", lambda low, high: 0.25)
    client = github_client.GitHubClient(lambda: {})
    url = "https://api.github.com/search/code?q=science"
    if failures == 3:
        with pytest.raises(RepositorySourceError) as error:
            client.fetch_json(url)
        assert error.value.status == "timed_out"
        assert "repository search" not in error.value.public_message
    else:
        assert client.fetch_json(url).payload == {"items": []}
    assert calls == [url] * min(failures + 1, 3)
    assert sleeps == [1.75, 3.25][: min(failures, 2)]


def test_http_408_does_not_retry_beyond_deadline(monkeypatch):
    calls = []
    sleeps = []
    now = monotonic()

    def fetch(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(
            request.full_url,
            408,
            "Request Timeout",
            {},
            BytesIO(b'{"message":"Request timed out"}'),
        )

    monkeypatch.setattr(github_client, "urlopen", fetch)
    monkeypatch.setattr(github_client.time, "sleep", sleeps.append)
    monkeypatch.setattr(github_client.random, "uniform", lambda low, high: 0.25)
    with pytest.raises(RepositorySourceError) as error:
        github_client.GitHubClient(lambda: {}).fetch_json(
            "https://api.github.com/search/code?q=science",
            deadline_monotonic=now + 1,
        )
    assert error.value.status == "timed_out"
    assert len(calls) == 1
    assert sleeps == []


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
    monkeypatch.setattr(
        github_auth.GitHubAppAuth,
        "_get_installation_access_token",
        lambda self: "installation-token",
    )

    assert auth.build_auth_headers() == {"Authorization": "Bearer installation-token"}


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
    client = github_client.GitHubClient(
        lambda: {"Authorization": "Bearer installation-token"}
    )

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


@pytest.mark.parametrize(
    "body,expected_status",
    [
        (b'{"message":"API rate limit exceeded"}', "rate_limited"),
        (b'{"message":"Resource not accessible by integration"}', "unauthorized"),
        (b"invalid-json", "unauthorized"),
        (b"[]", "unauthorized"),
    ],
)
def test_error_body_classifies_failure_without_rate_limit_headers(
    monkeypatch, body, expected_status
):
    from io import BytesIO

    def fail(request, timeout):
        raise HTTPError(request.full_url, 403, "Forbidden", {}, BytesIO(body))

    monkeypatch.setattr(github_client, "urlopen", fail)
    client = github_client.GitHubClient(lambda: {})
    with pytest.raises(RepositorySourceError) as failure:
        client.fetch_json("https://api.github.com/test")
    assert failure.value.status == expected_status
    assert isinstance(failure.value.__cause__, HTTPError)


def test_attempt_hook_runs_before_every_transport_retry(monkeypatch):
    events = []
    calls = 0

    def fetch(request, timeout):
        nonlocal calls
        events.append("network")
        calls += 1
        if calls == 1:
            raise HTTPError(
                request.full_url,
                503,
                "Unavailable",
                {},
                BytesIO(b'{"message":"retry"}'),
            )
        return BytesIO(b'{"items": []}')

    monkeypatch.setattr(github_client, "urlopen", fetch)
    monkeypatch.setattr(github_client.time, "sleep", lambda _: None)
    client = github_client.GitHubClient(
        lambda: {}, before_attempt=lambda url: events.append("reserved")
    )
    assert client.fetch_json(
        "https://api.github.com/search/code?q=science"
    ).payload == {"items": []}
    assert events == ["reserved", "network", "reserved", "network"]


def test_attempt_budget_rejection_cannot_issue_or_retry_transport(monkeypatch):
    calls = []
    monkeypatch.setattr(
        github_client, "urlopen", lambda *args, **kwargs: calls.append(args)
    )

    def reject(url):
        raise ValueError("attempt budget exhausted")

    with pytest.raises(ValueError, match="budget exhausted"):
        github_client.GitHubClient(lambda: {}, before_attempt=reject).fetch_json(
            "https://api.github.com/search/code?q=science"
        )
    assert calls == []
