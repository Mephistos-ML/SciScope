"""Tests for low-level GitHub client configuration."""

from __future__ import annotations

from app.sources.repositories.github import auth as github_auth
from app.sources.repositories.github import client as github_client


def test_build_auth_headers_returns_empty_mapping_without_token(monkeypatch) -> None:
    monkeypatch.setattr(github_auth, "GITHUB_TOKEN", "")

    assert github_auth.build_auth_headers() == {}


def test_build_auth_headers_uses_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(github_auth, "GITHUB_TOKEN", "test-token")

    assert github_auth.build_auth_headers() == {
        "Authorization": "Bearer test-token"
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
    monkeypatch.setattr(github_client, "build_auth_headers", lambda: {"Authorization": "Bearer test-token"})

    payload = github_client.fetch_json("https://api.github.com/test")

    assert payload == {"ok": True}
    assert captured_headers["Authorization"] == "Bearer test-token"
    assert captured_headers["Accept"] == "application/vnd.github+json"
