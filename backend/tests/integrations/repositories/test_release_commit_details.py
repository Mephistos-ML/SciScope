"""Release ranges use pinned ancestral Git comparisons, with bounded IO."""

from datetime import UTC, datetime, timedelta
from importlib import import_module
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.error import HTTPError, URLError

import pytest

from app.models.repository import Repository
from app.models.signal import Signal
from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.source_status import RepositorySourceError
from tests.fixtures.repository_clients import make_repository_monitor

BASE, HEAD = "b" * 40, "a" * 40
PUBLISHED = datetime(2026, 10, 9, tzinfo=UTC)


def provider(monkeypatch, source, *, mode="complete", size=125):
    adapter = make_repository_monitor(source)
    clock = import_module(f"app.integrations.repositories.{source}.monitor")
    monkeypatch.setattr(clock, "monotonic", lambda: 10)
    repository = Repository(f"{source}:repo:123", source, "science/tool", f"https://{source}.com/science/tool")
    release = Signal(source, "release", "science/tool:release:2", "v2", repository.url, PUBLISHED,
                     "Release notes", payload={"repo": "science/tool", "tag_name": "v/2"})
    calls = []
    shas = [f"{index + 1:040x}" for index in range(size - 1)] + [HEAD]
    items = [{"sha": sha, "id": sha, "commit": {"message": f"Change {index}", "committer": {"date": "2010-01-01T00:00:00Z"}},
              "message": f"Change {index}", "committed_date": "2010-01-01T00:00:00Z"}
             for index, sha in enumerate(shas)]
    def fetch(url, *, deadline_monotonic=None, max_response_bytes=None):
        assert deadline_monotonic == 100
        assert max_response_bytes == 8 * 1024 * 1024
        calls.append(url)
        path = unquote(urlsplit(url).path)
        params = parse_qs(urlsplit(url).query)
        if path.endswith("/releases"):
            catalogue = [{"tag_name": "v/2", "published_at": PUBLISHED.isoformat(), "released_at": PUBLISHED.isoformat()}]
            if mode != "missing_previous":
                catalogue += [{"tag_name": "v1", "published_at": (PUBLISHED - timedelta(days=1)).isoformat(),
                               "released_at": (PUBLISHED - timedelta(days=1)).isoformat()}]
            if mode == "catalog_budget":
                catalogue = catalogue * 50
            payload = catalogue
        elif path.endswith("/commits/v1") or path.endswith("/tags/v1"):
            payload = {"sha": BASE, "commit": {"id": BASE}}
        elif path.endswith("/commits/v/2") or path.endswith("/tags/v/2"):
            value = BASE if mode == "same_sha" else HEAD
            payload = {"sha": value, "commit": {"id": value}}
        elif source == "github" and "/compare/" in path:
            assert f"{BASE}...{HEAD}" in path  # Never a mutable tag or main branch.
            page = int(params["page"][0])
            if mode == "partial" and page == 2:
                raise RepositorySourceError(source=source, status="timed_out", public_message="Page timed out")
            payload = {"status": "ahead", "base_commit": {"sha": BASE},
                       "merge_base_commit": {"sha": HEAD if mode == "divergent" else BASE},
                       "total_commits": size, "commits": items[(page - 1) * 100:page * 100]}
        elif source == "gitlab" and path.endswith("/compare"):
            assert params["straight"] == ["true"]
            if params["from"] == [HEAD]:
                assert params["to"] == [BASE]
                payload = {"commit": {"id": BASE}, "commits": items[:1] if mode == "divergent" else []}
            else:
                assert params["from"] == [BASE] and params["to"] == [HEAD]
                # Diff timeouts do not truncate the documented GitLab commit list.
                payload = {"commit": {"id": HEAD}, "commits": items, "compare_timeout": True}
        else:
            raise AssertionError(f"Unexpected provider request: {url}")
        return JsonResponse(payload, url)
    monkeypatch.setattr(adapter.client, "fetch_json", fetch)
    return adapter, repository, release, calls


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_release_comparison_keeps_backdated_commits_and_pins_tag_endpoints(monkeypatch, source):
    adapter, repository, release, calls = provider(monkeypatch, source)
    result = adapter.load_release_commit_details(repository, release, deadline_monotonic=100)
    assert result.status == "complete"
    assert result.total_count == len(result.commits) == 125
    assert (result.base_sha, result.head_sha) == (BASE, HEAD)
    assert all(commit.published_at.year == 2010 and commit.payload["branch"] == "" for commit in result.commits)
    assert len(calls) <= 10


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_partial_comparison_retains_only_confirmed_commits(monkeypatch, source):
    size = 125 if source == "github" else 501
    adapter, repository, release, calls = provider(monkeypatch, source, mode="partial", size=size)
    result = adapter.load_release_commit_details(repository, release, deadline_monotonic=100)
    assert result.status == "partial"
    assert len(result.commits) == (100 if source == "github" else 500)
    assert result.total_count == size
    assert len(calls) <= 10


@pytest.mark.parametrize("source", ["github", "gitlab"])
@pytest.mark.parametrize("mode", ["missing_previous", "divergent", "catalog_budget"])
def test_unconfirmed_ranges_are_unavailable_rather_than_empty_complete(monkeypatch, source, mode):
    adapter, repository, release, calls = provider(monkeypatch, source, mode=mode)
    result = adapter.load_release_commit_details(repository, release, deadline_monotonic=100)
    assert result.status == "unavailable"
    assert result.commits == ()
    assert result.total_count is None
    if mode == "catalog_budget":
        assert len(calls) == 3


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_verified_equal_tag_endpoints_are_a_genuinely_empty_range(monkeypatch, source):
    adapter, repository, release, calls = provider(monkeypatch, source, mode="same_sha")
    result = adapter.load_release_commit_details(repository, release, deadline_monotonic=100)
    assert result.status == "complete"
    assert result.commits == () and result.total_count == 0
    assert not any("/compare" in url for url in calls)


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_expired_comparison_budget_performs_no_provider_io(monkeypatch, source):
    adapter, repository, release, calls = provider(monkeypatch, source)
    result = adapter.load_release_commit_details(repository, release, deadline_monotonic=9)
    assert result.status == "unavailable"
    assert calls == []


@pytest.mark.parametrize("source", ["github", "gitlab"])
@pytest.mark.parametrize("failure", ["http", "transport"])
def test_provider_retry_backoff_cannot_exceed_the_remaining_budget(monkeypatch, source, failure):
    module = import_module(f"app.integrations.repositories.{source}.client")
    from app.integrations.repositories.common import deadlines
    monkeypatch.setattr(module, "monotonic", lambda: 10)
    monkeypatch.setattr(deadlines, "monotonic", lambda: 10)
    sleeps, requests = [], []
    monkeypatch.setattr(module.time, "sleep", sleeps.append)
    def fail(request, timeout):
        requests.append(timeout)
        if failure == "http":
            raise HTTPError(request.full_url, 503, "Unavailable", {}, None)
        raise URLError(TimeoutError("Timed out"))
    monkeypatch.setattr(module, "urlopen", fail)
    client = module.GitHubClient(lambda: {}) if source == "github" else module.GitLabClient("https://gitlab.com", lambda: {})
    with pytest.raises(RepositorySourceError):
        client.fetch_json("https://example.com/test", deadline_monotonic=10.2)
    assert len(requests) == 1 and 0 < requests[0] <= .2
    assert sleeps == []


@pytest.mark.parametrize("source", ["github", "gitlab"])
def test_comparison_response_byte_budget_rejects_oversized_json_before_parsing(monkeypatch, source):
    from io import BytesIO
    module = import_module(f"app.integrations.repositories.{source}.client")
    response = BytesIO(b'{"large":"' + b'x' * 40 + b'"}')
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: response)
    client = module.GitHubClient(lambda: {}) if source == "github" else module.GitLabClient("https://gitlab.com", lambda: {})
    with pytest.raises(RepositorySourceError) as error:
        client.fetch_json("https://example.com/test", max_response_bytes=16)
    assert error.value.status == "error"
