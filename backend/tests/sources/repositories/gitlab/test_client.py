"""Tests for GitLab source auth and low-level HTTP configuration."""

from __future__ import annotations

from urllib.error import HTTPError

import pytest

from app.sources.common import RepositorySourceError
from app.sources.gitlab import auth as gitlab_auth
from app.sources.gitlab import client as gitlab_client


def test_build_auth_headers_fails_when_gitlab_source_is_disabled(monkeypatch) -> None:
    monkeypatch.setattr(gitlab_auth, "GITLAB_AUTH_MODE", "disabled")

    with pytest.raises(RepositorySourceError) as exc_info:
        gitlab_auth.build_auth_headers()

    assert exc_info.value.status == "disabled"


def test_build_auth_headers_fails_when_gitlab_service_token_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(gitlab_auth, "GITLAB_AUTH_MODE", "service_account")
    monkeypatch.setattr(gitlab_auth, "GITLAB_SERVICE_ACCOUNT_TOKEN", "")

    with pytest.raises(RepositorySourceError) as exc_info:
        gitlab_auth.build_auth_headers()

    assert exc_info.value.status == "misconfigured"
    assert "GITLAB_SERVICE_ACCOUNT_TOKEN" in exc_info.value.public_message


def test_build_auth_headers_uses_private_token_header(monkeypatch) -> None:
    monkeypatch.setattr(gitlab_auth, "GITLAB_AUTH_MODE", "service_account")
    monkeypatch.setattr(gitlab_auth, "GITLAB_SERVICE_ACCOUNT_TOKEN", "test-token")

    assert gitlab_auth.build_auth_headers() == {
        "PRIVATE-TOKEN": "test-token"
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

    monkeypatch.setattr(gitlab_client, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        gitlab_client,
        "build_auth_headers",
        lambda: {"PRIVATE-TOKEN": "test-token"},
    )

    payload = gitlab_client.fetch_json("https://gitlab.com/api/v4/test")

    assert payload == {"ok": True}
    assert captured_headers["Private-token"] == "test-token"
    assert captured_headers["Accept"] == "application/json"


def test_fetch_json_classifies_unauthorized_gitlab_requests(monkeypatch) -> None:
    monkeypatch.setattr(gitlab_client, "build_auth_headers", lambda: {"PRIVATE-TOKEN": "test-token"})

    def fake_urlopen(_request, timeout):  # type: ignore[no-untyped-def]
        del timeout
        raise HTTPError(
            url="https://gitlab.com/api/v4/test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

    monkeypatch.setattr(gitlab_client, "urlopen", fake_urlopen)

    with pytest.raises(RepositorySourceError) as exc_info:
        gitlab_client.fetch_json("https://gitlab.com/api/v4/test")

    assert exc_info.value.status == "unauthorized"
