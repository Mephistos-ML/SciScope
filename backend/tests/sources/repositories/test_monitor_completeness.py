"""Provider monitoring must distinguish complete and truncated activity reads."""

from datetime import UTC, datetime

import pytest

from app.models.repository import Repository
from app.sources.common import JsonResponse
from app.sources.github import monitor as github
from app.sources.gitlab import monitor as gitlab


@pytest.mark.parametrize("provider", ["github", "gitlab"])
@pytest.mark.parametrize("stream", ["releases", "commits"])
@pytest.mark.parametrize("response_kind", ["empty", "short", "full", "non-list", "bad-date", "bad-id", "bad-item"])
def test_provider_reports_stream_completeness(monkeypatch, provider, stream, response_kind):
    adapter = github if provider == "github" else gitlab
    item = {
        "id": "abc", "sha": "abc", "tag_name": "v1", "name": "v1", "title": "Commit",
        "published_at": "2026-10-07T12:00:00Z", "released_at": "2026-10-07T12:00:00Z",
        "committed_date": "2026-10-07T12:00:00Z",
        "commit": {"author": {"date": "2026-10-07T12:00:00Z"}, "message": "Commit"},
    }
    if response_kind == "bad-date":
        item.update(published_at="invalid", released_at="invalid", committed_date="invalid")
        item["commit"]["author"]["date"] = "invalid"
    if response_kind == "bad-id":
        for key in ("id", "sha", "tag_name"):
            item.pop(key)
    payload = [] if response_kind == "empty" else (
        [dict(item) for _ in range(10)] if response_kind == "full" else
        {"error": "invalid response"} if response_kind == "non-list" else
        [None] if response_kind == "bad-item" else [item]
    )
    def fetch(url):
        return JsonResponse(payload=payload if f"/{stream}?" in url else [], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    repository = Repository(repository_id=f"{provider}:repo:123", source=provider,
                            full_name="science/example", url=f"https://{provider}.com/science/example",
                            provider_repository_id="123")
    activity = adapter.load_repository_activity(
        repository, release_started_after=datetime(2026, 10, 7, 10, tzinfo=UTC),
        commit_started_after=datetime(2026, 10, 7, 10, tzinfo=UTC),
    )
    complete = response_kind in {"empty", "short"}
    assert activity.releases_complete is (complete if stream == "releases" else True)
    assert activity.commits_complete is (complete if stream == "commits" else True)
    assert len(activity.signals) == (10 if response_kind == "full" else 1 if response_kind == "short" else 0)


@pytest.mark.parametrize("adapter", [github, gitlab])
def test_full_page_with_old_events_does_not_assume_timestamp_order(monkeypatch, adapter):
    payload = [{"id": n, "tag_name": f"v{n}", "published_at": "2026-10-06T12:00:00Z",
                "released_at": "2026-10-06T12:00:00Z"} for n in range(10)]
    monkeypatch.setattr(adapter, "fetch_json", lambda url: JsonResponse(payload=payload, url=url))
    repository = Repository(repository_id="repo", source="github", full_name="science/example",
                            url="https://example.com", provider_repository_id="123")
    activity = adapter.load_repository_activity(
        repository, release_started_after=datetime(2026, 10, 7, tzinfo=UTC), commit_started_after=None,
    )
    assert activity.signals == ()
    assert activity.releases_complete is False
