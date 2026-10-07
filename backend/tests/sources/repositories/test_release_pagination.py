"""Release monitoring pagination, partial reads, and timestamp boundaries."""

from datetime import UTC, datetime
from json import JSONDecodeError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.models.repository import Repository
from app.sources.common import JsonResponse, RepositorySourceError
from app.sources.github import monitor as github
from app.sources.gitlab import monitor as gitlab

CUTOFF = datetime(2026, 10, 7, 10, tzinfo=UTC)


def _release(number, published_at="2026-10-07T12:00:00Z"):
    return {"id": number, "tag_name": f"v{number}", "name": f"Release {number}",
            "published_at": published_at, "released_at": published_at}


def _load(adapter):
    return adapter.load_repository_activity(
        Repository(repository_id="repo:123", source="github" if adapter is github else "gitlab",
                   full_name="science/example", url="https://example.com/science/example",
                   provider_repository_id="123"),
        release_started_after=CUTOFF, commit_started_after=None,
    )


@pytest.fixture(params=[github, gitlab], ids=["github", "gitlab"])
def adapter(request):
    return request.param


def test_reads_releases_across_pages_and_deduplicates_overlap(adapter, monkeypatch):
    pages = {1: [_release(n) for n in range(1, 101)],
             2: [_release(n) for n in range(100, 126)]}
    calls = []
    def fetch(url):
        query = parse_qs(urlsplit(url).query)
        page = int(query["page"][0])
        calls.append(page)
        assert query["per_page"] == ["100"]
        if adapter is gitlab:
            assert query["order_by"] == ["released_at"]
            assert query["sort"] == ["desc"]
        return JsonResponse(payload=pages[page], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    activity = _load(adapter)
    assert calls == [1, 2]
    assert len(activity.signals) == 125
    assert len({signal.item_id for signal in activity.signals}) == 125
    assert activity.releases_complete is True


@pytest.mark.parametrize("failure", ["timeout", "rate-limit", "json", "non-list", "bad-item"])
def test_next_page_failure_retains_first_page_and_blocks_checkpoint(adapter, monkeypatch, failure):
    def fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        if page == 1:
            return JsonResponse(payload=[_release(n) for n in range(1, 101)], url=url)
        if failure in {"timeout", "rate-limit"}:
            raise RepositorySourceError(source="github" if adapter is github else "gitlab",
                                        status="timed_out" if failure == "timeout" else "rate_limited",
                                        public_message="Provider unavailable")
        if failure == "json":
            raise JSONDecodeError("Malformed JSON", "broken", 0)
        return JsonResponse(payload={} if failure == "non-list" else [None], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    activity = _load(adapter)
    assert len(activity.signals) == 100
    assert activity.releases_complete is False


def test_page_limit_keeps_partial_results(adapter, monkeypatch):
    monkeypatch.setattr(adapter, "MAX_RELEASE_PAGES", 2)
    calls = []
    def fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        calls.append(page)
        return JsonResponse(payload=[_release(n) for n in range(page * 100, (page + 1) * 100)], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    activity = _load(adapter)
    assert calls == [1, 2]
    assert len(activity.signals) == 200
    assert activity.releases_complete is False


def test_full_final_page_requires_reading_empty_next_page(adapter, monkeypatch):
    calls = []
    def fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        calls.append(page)
        return JsonResponse(payload=[_release(n) for n in range(1, 101)] if page == 1 else [], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    assert _load(adapter).releases_complete is True
    assert calls == [1, 2]


def test_equal_checkpoint_timestamps_are_read_across_pages(adapter, monkeypatch):
    pages = {1: [_release(n, CUTOFF.isoformat()) for n in range(1, 101)],
             2: [_release(101, CUTOFF.isoformat()), _release(102, "2026-10-07T09:00:00Z")]}
    calls = []
    def fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        calls.append(page)
        return JsonResponse(payload=pages[page], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    activity = _load(adapter)
    assert calls == [1, 2]
    assert len(activity.signals) == 101
    assert activity.releases_complete is True


def test_github_reads_past_old_publication_dates(monkeypatch):
    pages = {1: [_release(n, "2026-10-07T09:00:00Z") for n in range(1, 101)],
             2: [_release(101)]}
    monkeypatch.setattr(github, "fetch_json", lambda url: JsonResponse(
        payload=pages[int(parse_qs(urlsplit(url).query)["page"][0])], url=url))
    activity = _load(github)
    assert [signal.item_id for signal in activity.signals] == ["science/example:release:101"]
    assert activity.releases_complete is True


def test_gitlab_stops_only_after_strictly_older_release(monkeypatch):
    calls = []
    def fetch(url):
        calls.append(url)
        return JsonResponse(payload=[_release(n, "2026-10-07T09:00:00Z") for n in range(1, 101)], url=url)
    monkeypatch.setattr(gitlab, "fetch_json", fetch)
    activity = _load(gitlab)
    assert activity.signals == ()
    assert activity.releases_complete is True
    assert len(calls) == 1


def test_invalid_gitlab_release_date_does_not_use_created_date_as_boundary(monkeypatch):
    item = _release(1)
    item.update(released_at=None, created_at="2026-10-07T09:00:00Z")
    monkeypatch.setattr(gitlab, "fetch_json", lambda url: JsonResponse(payload=[item], url=url))
    assert _load(gitlab).releases_complete is False


def test_redirect_on_later_page_is_retained(adapter, monkeypatch):
    def fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        return JsonResponse(payload=[_release(n) for n in range(1, 101)] if page == 1 else [],
                            url=url if page == 1 else url.replace("example", "renamed"))
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    activity = _load(adapter)
    assert activity.releases_complete is True
    assert activity.redirected is True


@pytest.mark.parametrize("failed_stream", ["releases", "commits"])
def test_one_stream_failure_preserves_other_stream(adapter, monkeypatch, failed_stream):
    def fetch(url):
        if "?" not in url:
            return JsonResponse(payload={"commit": {"sha": "head", "id": "head"}} if "/branches/" in url else {"default_branch": "main"}, url=url)
        if f"/{failed_stream}?" in url:
            raise RepositorySourceError(source="github" if adapter is github else "gitlab",
                                        status="timed_out", public_message="Timed out")
        return JsonResponse(payload=[_release(1)] if "/releases?" in url else [], url=url)
    monkeypatch.setattr(adapter, "fetch_json", fetch)
    repository = Repository(repository_id="repo", source="github" if adapter is github else "gitlab",
                            full_name="science/example", url="https://example.com", provider_repository_id="123")
    activity = adapter.load_repository_activity(repository, release_started_after=CUTOFF, commit_started_after=CUTOFF)
    assert activity.releases_complete is (failed_stream != "releases")
    assert activity.commits_complete is (failed_stream != "commits")
    assert len(activity.signals) == (1 if failed_stream == "commits" else 0)
