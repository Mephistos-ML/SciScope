"""Regression coverage for canonical subscription profiles and catalog repair."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app.api.app import app
from app.config import AUTH_SESSION_COOKIE_NAME
from app.models.repository import Repository
from app.services.auth.service import User, create_authenticated_session
from app.services.repositories import repair_repository_profiles
from app.services.subscriptions.service import (
    create_subscription_payload,
)
from app.sources.common.source_status import RepositorySourceError
from app.storage.auth.users import create_user
from app.storage.repositories.repositories import get_repository, upsert_repositories
from app.storage.subscriptions.subscriptions import list_subscriptions_for_user
from tests.conftest import build_test_database_url, migrate_test_database


@pytest.fixture
def database_url(tmp_path):
    url = build_test_database_url(tmp_path / "subscriptions.sqlite3")
    migrate_test_database(url)
    return url


@pytest.fixture
def user(database_url):
    record = create_user(email="subscriber@example.com", display_name="Subscriber", database_url=database_url)
    return User(record.user_id, record.email, record.display_name)


def _profile(source="github", provider_id="123"):
    return Repository(
        repository_id=f"{source}:repo:{provider_id}", source=source,
        provider_repository_id=provider_id, full_name="science/tool",
        url=f"https://{source}.com/science/tool", owner_login="science",
        description="Scientific simulation", language="Python", stars=500,
        topics=("simulation",), metadata={"repo": "science/tool"},
        provider_updated_at=datetime(2026, 10, 1, tzinfo=UTC),
    )


def _subscribe(user, database_url, loader, repository_id="github:repo:123"):
    return create_subscription_payload(
        user, repository_item_id=repository_id, selected_query="simulation",
        load_repository_profile=loader, database_url=database_url,
    )


def test_legacy_payload_cannot_overwrite_catalog_and_repeat_is_idempotent(database_url, user, monkeypatch):
    profile = _profile()
    upsert_repositories((profile,), database_url=database_url)
    original = get_repository(profile.repository_id, database_url=database_url)
    loader = Mock(side_effect=AssertionError("An existing profile must not be fetched."))
    monkeypatch.setattr(app.state, "database_url", database_url)
    monkeypatch.setattr(app.state, "load_repository_profile", loader)
    token = create_authenticated_session(user.user_id, Response(), database_url=database_url)
    with TestClient(app) as client:
        client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        first = client.post("/api/subscriptions", json={
            "repository": {
                "itemId": profile.repository_id, "source": "github",
                "fullName": "attacker/other", "url": "https://example.com",
            }, "selectedQuery": "simulation",
        })
        second = client.post("/api/subscriptions", json={
            "repository": {"itemId": profile.repository_id}, "selectedQuery": "simulation",
        })
    assert first.status_code == second.status_code == 201
    assert first.json()["subscriptionId"] == second.json()["subscriptionId"]
    assert first.json()["repository"]["fullName"] == profile.full_name
    assert first.json()["repository"]["url"] == profile.url
    assert get_repository(profile.repository_id, database_url=database_url) == original
    loader.assert_not_called()


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_missing_profile_is_fetched_by_id(database_url, user, source):
    profile = _profile(source)
    loader = Mock(return_value=profile)
    response = _subscribe(user, database_url, loader, profile.repository_id)
    loader.assert_called_once_with(profile.repository_id)
    persisted = get_repository(profile.repository_id, database_url=database_url)
    assert persisted.description == profile.description
    assert persisted.stars == profile.stars
    assert persisted.language == profile.language
    assert response["repository"]["repositoryId"] == profile.repository_id


def test_concurrent_catalog_discovery_wins_over_subscription_fetch(database_url, user):
    fetched = _profile()
    discovered = replace(fetched, description="Newer discovery", stars=501)
    def loader(repository_id):
        upsert_repositories((discovered,), database_url=database_url)
        return fetched
    _subscribe(user, database_url, loader)
    assert get_repository(fetched.repository_id, database_url=database_url).description == "Newer discovery"


@pytest.mark.parametrize("repository_id", [
    "gitee:repo:123", "github:repo:owner/tool", "github:repo:abc",
    "github:repo:0", "github:repo:-1", "github:repo:١٢٣", "github:repo:123?x=y",
])
def test_invalid_identity_is_rejected_before_provider_access(database_url, user, repository_id):
    loader = Mock()
    with pytest.raises(ValueError):
        _subscribe(user, database_url, loader, repository_id)
    loader.assert_not_called()
    assert not list_subscriptions_for_user(user.user_id, database_url=database_url)


def test_provider_failure_returns_503_and_leaves_no_subscription(database_url, user, monkeypatch):
    loader = Mock(side_effect=RepositorySourceError(
        source="github", status="timed_out", public_message="GitHub lookup timed out.",
    ))
    monkeypatch.setattr(app.state, "database_url", database_url)
    monkeypatch.setattr(app.state, "load_repository_profile", loader)
    token = create_authenticated_session(user.user_id, Response(), database_url=database_url)
    with TestClient(app) as client:
        client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        response = client.post("/api/subscriptions", json={"repository": {"itemId": "github:repo:123"}})
    assert response.status_code == 503
    assert response.json()["error"] == "GitHub lookup timed out."
    assert not list_subscriptions_for_user(user.user_id, database_url=database_url)
    assert get_repository("github:repo:123", database_url=database_url) is None


@pytest.mark.parametrize("payload", [
    {"itemId": "github:repo:123", "source": "gitlab"},
    {"itemId": "github:repo:owner/tool"},
    {"itemId": "unsupported:repo:123"},
])
def test_invalid_api_identity_returns_400_without_provider_access(database_url, user, monkeypatch, payload):
    loader = Mock()
    monkeypatch.setattr(app.state, "database_url", database_url)
    monkeypatch.setattr(app.state, "load_repository_profile", loader)
    token = create_authenticated_session(user.user_id, Response(), database_url=database_url)
    with TestClient(app) as client:
        client.cookies.set(AUTH_SESSION_COOKIE_NAME, token)
        response = client.post("/api/subscriptions", json={"repository": payload})
    assert response.status_code == 400
    loader.assert_not_called()
    assert not list_subscriptions_for_user(user.user_id, database_url=database_url)


def test_mismatched_provider_profile_is_not_persisted(database_url, user):
    with pytest.raises(ValueError, match="does not match"):
        _subscribe(user, database_url, Mock(return_value=_profile(provider_id="456")))
    assert get_repository("github:repo:456", database_url=database_url) is None
    assert not list_subscriptions_for_user(user.user_id, database_url=database_url)


def _damaged():
    return replace(_profile(), owner_login="", description="", language="", stars=0,
                   topics=(), provider_updated_at=None, metadata={"repo": "science/tool", "query": "simulation"})


def test_repair_defaults_to_preview_and_apply_is_repeatable(database_url):
    damaged = _damaged()
    upsert_repositories((damaged,), database_url=database_url)
    before = get_repository(damaged.repository_id, database_url=database_url)
    loader = Mock(return_value=_profile())
    preview = repair_repository_profiles(load_repository_profile=loader, database_url=database_url)
    assert preview[0].status == "would_update"
    assert preview[0].changes["stars"] == {"before": 0, "after": 500}
    assert get_repository(damaged.repository_id, database_url=database_url) == before
    applied = repair_repository_profiles(load_repository_profile=loader, database_url=database_url, apply=True)
    assert applied[0].status == "updated"
    repaired = get_repository(damaged.repository_id, database_url=database_url)
    assert repaired.stars == 500
    assert repaired.first_seen_at == before.first_seen_at
    repeated = repair_repository_profiles(load_repository_profile=loader, database_url=database_url, apply=True)
    assert repeated == []
    explicit = repair_repository_profiles(load_repository_profile=loader, database_url=database_url,
                                          apply=True, repository_ids=[damaged.repository_id])
    assert explicit[0].status == "unchanged"
    assert get_repository(damaged.repository_id, database_url=database_url) == repaired


def test_repair_skips_profiles_changed_during_provider_request(database_url):
    upsert_repositories((_damaged(),), database_url=database_url)
    concurrent = replace(_profile(), stars=999)
    def loader(repository_id):
        upsert_repositories((concurrent,), database_url=database_url)
        return _profile()
    reports = repair_repository_profiles(load_repository_profile=loader, database_url=database_url, apply=True)
    assert reports[0].status == "skipped_changed"
    assert get_repository(concurrent.repository_id, database_url=database_url).stars == 999


def test_repair_ignores_legitimately_sparse_profiles_and_isolates_provider_errors(database_url):
    sparse = replace(_damaged(), repository_id="github:repo:456", provider_repository_id="456", metadata={"repo": "science/tool"})
    upsert_repositories((_damaged(), sparse), database_url=database_url)
    loader = Mock(side_effect=RepositorySourceError(source="github", status="rate_limited", public_message="Try later."))
    reports = repair_repository_profiles(load_repository_profile=loader, database_url=database_url, apply=True)
    assert len(reports) == 1
    assert reports[0].status == "failed"
    loader.assert_called_once_with("github:repo:123")
    assert get_repository("github:repo:123", database_url=database_url).stars == 0


def test_repair_continues_after_one_provider_failure(database_url):
    second = replace(_damaged(), repository_id="github:repo:456", provider_repository_id="456")
    upsert_repositories((_damaged(), second), database_url=database_url)
    def loader(repository_id):
        if repository_id == "github:repo:123":
            raise RepositorySourceError(source="github", status="unauthorized", public_message="Unavailable.")
        return _profile(provider_id="456")
    reports = repair_repository_profiles(load_repository_profile=loader, database_url=database_url, apply=True)
    assert [report.status for report in reports] == ["failed", "updated"]
    assert get_repository("github:repo:456", database_url=database_url).stars == 500


def test_repair_preserves_subscriptions_and_feed_history(database_url, user):
    from app.models.feed import FeedEvent
    from app.storage.feed.events import get_feed_event_for_user, upsert_feed_events
    upsert_repositories((_damaged(),), database_url=database_url)
    subscription = _subscribe(user, database_url, Mock())
    event = FeedEvent(
        event_id="history", user_id=user.user_id, subscription_id=subscription["subscriptionId"],
        repository_id="github:repo:123", repository_full_name="science/tool",
        repository_source="github", repository_url="https://github.com/science/tool",
        selected_query="simulation", source="github", kind="release", item_id="release:1",
        title="Release", url="https://github.com/science/tool/releases/1", published_at=None,
        raw_text="Release", normalized_text="Release", metadata={},
    )
    upsert_feed_events((event,), database_url=database_url)
    before = get_feed_event_for_user(user.user_id, event.event_id, database_url=database_url)
    repair_repository_profiles(load_repository_profile=Mock(return_value=_profile()), database_url=database_url, apply=True)
    assert get_feed_event_for_user(user.user_id, event.event_id, database_url=database_url) == before
    assert list_subscriptions_for_user(user.user_id, database_url=database_url)[0].subscription_id == subscription["subscriptionId"]


def test_repair_command_previews_by_default_and_accepts_explicit_apply(database_url, monkeypatch, capsys):
    from scripts import repair_repository_profiles as command
    import json
    import sys
    upsert_repositories((_damaged(),), database_url=database_url)
    monkeypatch.setattr(command, "DATABASE_URL", database_url)
    monkeypatch.setattr(command, "load_repository_profile", Mock(return_value=_profile()))
    monkeypatch.setattr(sys, "argv", ["repair_repository_profiles", "--limit", "1"])
    assert command.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "dry-run"
    assert report["profiles"][0]["status"] == "would_update"
    assert get_repository("github:repo:123", database_url=database_url).stars == 0
    monkeypatch.setattr(sys, "argv", ["repair_repository_profiles", "--apply", "--repository-id", "github:repo:123"])
    assert command.main() == 0
    assert json.loads(capsys.readouterr().out)["profiles"][0]["status"] == "updated"
    assert get_repository("github:repo:123", database_url=database_url).stars == 500
