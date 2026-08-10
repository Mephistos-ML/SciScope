"""Tests for low-level GitLab client configuration."""

from __future__ import annotations

from app.sources.repositories.gitlab import auth as gitlab_auth
from app.sources.repositories.gitlab import client as gitlab_client


def test_build_auth_headers_returns_empty_mapping_without_token(monkeypatch) -> None:
    monkeypatch.setattr(gitlab_auth, "GITLAB_TOKEN", "")

    assert gitlab_auth.build_auth_headers() == {}


def test_build_auth_headers_uses_private_token_header(monkeypatch) -> None:
    monkeypatch.setattr(gitlab_auth, "GITLAB_TOKEN", "test-token")

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
    monkeypatch.setattr(gitlab_client, "build_auth_headers", lambda: {"PRIVATE-TOKEN": "test-token"})

    payload = gitlab_client.fetch_json("https://gitlab.com/api/v4/test")

    assert payload == {"ok": True}
    assert captured_headers["Private-token"] == "test-token"
    assert captured_headers["Accept"] == "application/json"
