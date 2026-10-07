"""Commit monitoring follows pinned graph identity rather than commit dates."""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from app.models.repository import Repository
from app.sources.common import JsonResponse, RepositorySourceError
from app.sources.github import monitor as github
from app.sources.gitlab import monitor as gitlab

CUTOFF = datetime(2026, 10, 7, tzinfo=UTC)
OLD_DATE = "2010-01-01T00:00:00Z"


def commit(sha, date=OLD_DATE):
    return {"sha": sha, "id": sha, "title": "Scientific change", "message": "Scientific change",
            "committed_date": date, "created_at": date,
            "commit": {"author": {"date": OLD_DATE}, "committer": {"date": date}, "message": "Scientific change"}}


@pytest.fixture(params=[github, gitlab], ids=["github", "gitlab"])
def adapter(request):
    return request.param


def load(adapter, after_sha="old-head"):
    return adapter.load_repository_activity(
        Repository(repository_id="repo", source="github" if adapter is github else "gitlab",
                   full_name="science/example", url="https://example.com", provider_repository_id="123"),
        release_started_after=None, commit_started_after=CUTOFF, commit_after_sha=after_sha,
    )


def fake_provider(adapter, monkeypatch, items, *, head="new-head", fail_page=None, diverged=False):
    calls = []
    def fetch(url):
        calls.append(url)
        query = parse_qs(urlsplit(url).query)
        if "/branches/" in url:
            return JsonResponse(payload={"commit": {"sha": head, "id": head}}, url=url)
        if "?" not in url:
            return JsonResponse(payload={"default_branch": "main"}, url=url)
        page = int(query.get("page", ["1"])[0])
        if page == fail_page:
            raise RepositorySourceError(source="github" if adapter is github else "gitlab",
                                        status="timed_out", public_message="Timed out")
        if "/compare/" in url:
            payload = {"status": "diverged" if diverged else "ahead", "merge_base_commit": {"sha": "old-head"},
                       "total_commits": len(items), "commits": items[(page-1)*100:page*100]}
        elif "/repository/compare?" in url:
            assert query["straight"] == ["true"]
            reverse = query["from"] == [head]
            payload = {"commit": {"id": "old-head" if reverse else head},
                       "commits": ([commit("old-head")] if diverged else []) if reverse else items,
                       "compare_timeout": True}
        else:
            assert query.get("sha", query.get("ref_name")) == [head]
            assert "since" in query
            payload = items[(page-1)*100:page*100]
        return JsonResponse(payload=payload, url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    return calls


def test_incremental_scan_retains_backdated_merged_commits_across_pages(adapter, monkeypatch):
    items = [commit("new-head"), *[commit(f"side-{n}") for n in range(124)]]
    calls = fake_provider(adapter, monkeypatch, items)
    activity = load(adapter)
    assert len(activity.signals) == 125
    assert activity.commits_complete is True
    assert activity.commit_head_sha == "new-head"
    assert {signal.published_at.year for signal in activity.signals} == {2010}
    assert len([url for url in calls if "/branches/" in url]) == 1
    if adapter is github:
        assert all("old-head...new-head" in url for url in calls if "/compare/" in url)
        assert len([url for url in calls if "/compare/" in url]) == 2


def test_bootstrap_uses_committer_date_and_pinned_pagination(adapter, monkeypatch):
    items = [commit(f"commit-{n}", "2026-10-07T12:00:00Z") for n in range(125)]
    calls = fake_provider(adapter, monkeypatch, items)
    activity = load(adapter, after_sha=None)
    assert activity.commits_complete is True
    assert activity.commit_head_sha == "new-head"
    assert len(activity.signals) == 125
    assert {signal.published_at.year for signal in activity.signals} == {2026}
    assert len([url for url in calls if "/commits?" in url]) == 2


def test_unchanged_head_needs_no_history_requests(adapter, monkeypatch):
    calls = fake_provider(adapter, monkeypatch, [], head="old-head")
    activity = load(adapter)
    assert activity.commits_complete is True
    assert activity.commit_head_sha == "old-head"
    assert activity.signals == ()
    assert len(calls) == 2


def test_rewritten_history_does_not_reset_checkpoint(adapter, monkeypatch):
    fake_provider(adapter, monkeypatch, [commit("new-head")], diverged=True)
    activity = load(adapter)
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None


def test_budget_exhaustion_returns_partial_without_new_head(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "MAX_COMMIT_PAGES", 1)
    fake_provider(adapter, monkeypatch, [commit("new-head"), *[commit(f"side-{n}") for n in range(124)]])
    activity = load(adapter)
    assert len(activity.signals) == 100
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None


def test_github_second_compare_page_timeout_keeps_first_page(monkeypatch):
    fake_provider(github, monkeypatch, [commit("new-head"), *[commit(f"side-{n}") for n in range(124)]], fail_page=2)
    activity = load(github)
    assert len(activity.signals) == 100
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None


def test_invalid_commit_blocks_advance(adapter, monkeypatch):
    fake_provider(adapter, monkeypatch, [commit("new-head"), {"id": "broken", "sha": "broken"}])
    activity = load(adapter)
    assert len(activity.signals) == 1
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None


def test_bootstrap_budget_does_not_establish_sha(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "MAX_COMMIT_PAGES", 1)
    fake_provider(adapter, monkeypatch, [commit(f"c-{n}", "2026-10-07T12:00:00Z") for n in range(125)])
    activity = load(adapter, after_sha=None)
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None
    assert len(activity.signals) == 100


def test_missing_previous_sha_is_partial_without_rebaselining(adapter, monkeypatch):
    fake_provider(adapter, monkeypatch, [commit("new-head")])
    fetch = adapter.fetch_json
    def missing(url):
        if "/compare/" in url or "/repository/compare?" in url:
            raise RepositorySourceError(source="github" if adapter is github else "gitlab",
                                        status="error", public_message="Previous commit is no longer available")
        return fetch(url)
    monkeypatch.setattr(adapter, "fetch_json", missing)
    activity = load(adapter)
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None
    assert activity.signals == ()


def test_malformed_head_does_not_create_checkpoint(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "fetch_json", lambda url: JsonResponse(
        payload={"default_branch": "main"} if "/branches/" not in url else {"commit": {}}, url=url))
    activity = load(adapter, after_sha=None)
    assert activity.commits_complete is False
    assert activity.commit_head_sha is None
