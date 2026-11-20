"""Code-search coverage and validated prefixes survive provider failures."""

from urllib.parse import parse_qs, urlsplit

import pytest

from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github.client import GitHubClient
from app.integrations.repositories.github.search import code


def page(size=1, total=1, incomplete=False):
    return {"total_count": total, "incomplete_results": incomplete, "items": [
        {"path": f"src/module_{index}.py", "repository": {"id": 1, "full_name": "science/tool"}}
        for index in range(size)
    ]}


def install_pages(monkeypatch, responses):
    pending = iter(responses)
    requests = []

    def fetch(self, url, *, deadline_monotonic=None, max_response_bytes=None):
        assert max_response_bytes == 2 * 1024 * 1024
        requests.append(url)
        value = next(pending)
        if isinstance(value, Exception):
            raise value
        return JsonResponse(value, url)

    monkeypatch.setattr(GitHubClient, "fetch_json", fetch)
    return GitHubClient(lambda: {}), requests


@pytest.mark.parametrize("status", ["timed_out", "rate_limited", "unauthorized", "error"])
def test_later_failure_returns_earlier_signals_and_classified_error(monkeypatch, status):
    error = RepositorySourceError(source="github", status=status, public_message="Unavailable", retry_after_seconds=60)
    client, requests = install_pages(monkeypatch, [page(100, 300), error])
    batch = code.search_code(["scientific phrase"], client=client, max_pages=3)
    assert len(batch.signals) == 100
    assert batch.error is error
    assert batch.error.retry_after_seconds == 60
    assert batch.reported_result_counts == (300,)
    assert [parse_qs(urlsplit(url).query)["page"] for url in requests] == [["1"], ["2"]]


def test_expired_deadline_preserves_the_completed_page_without_another_request(monkeypatch):
    clock = [0]
    monkeypatch.setattr(code, "monotonic", lambda: clock[0])
    requests = []

    def fetch(self, url, **kwargs):
        requests.append(url)
        clock[0] = 2
        return JsonResponse(page(100, 300), url)

    monkeypatch.setattr(GitHubClient, "fetch_json", fetch)
    batch = code.search_code(["science"], client=GitHubClient(lambda: {}), deadline_monotonic=1)
    assert len(requests) == 1
    assert len(batch.signals) == 100
    assert batch.error.status == "timed_out"


@pytest.mark.parametrize("payload,reason", [
    (page(0, 0, True), "provider_incomplete"),
    (page(2, 40), "provider_truncated"),
    ({"items": []}, "coverage_unknown"),
])
def test_empty_or_short_results_are_not_assumed_complete(monkeypatch, payload, reason):
    client, requests = install_pages(monkeypatch, [payload])
    batch = code.search_code(["science"], client=client)
    assert batch.error is None
    assert batch.coverage_reasons == (reason,)
    assert len(requests) == 1


def test_budget_truncation_and_provider_incompleteness_are_independent(monkeypatch):
    client, _ = install_pages(monkeypatch, [page(100, 900, True)] * 3)
    batch = code.search_code(["science"], client=client, max_pages=3)
    assert len(batch.signals) == 300
    assert batch.coverage_reasons == ("provider_incomplete", "page_budget")


@pytest.mark.parametrize("size", [0, 17, 100])
def test_complete_known_result_stops_without_an_extra_page(monkeypatch, size):
    client, requests = install_pages(monkeypatch, [page(size, size)])
    batch = code.search_code(["science"], client=client, max_pages=3)
    assert len(batch.signals) == size
    assert batch.error is None
    assert not batch.coverage_reasons
    assert len(requests) == 1


@pytest.mark.parametrize("invalid", [[], {}, {"items": None}, {"items": [], "total_count": True},
                                    {"items": [], "incomplete_results": "false"}])
def test_invalid_page_is_an_error_without_discarding_prior_observations(monkeypatch, invalid):
    client, _ = install_pages(monkeypatch, [page(100, 300), invalid])
    batch = code.search_code(["science"], client=client)
    assert len(batch.signals) == 100
    assert batch.error.status == "error"


def test_invalid_optional_sha_is_ignored_but_unmappable_items_mark_partial(monkeypatch):
    payload = page()
    payload["items"][0]["sha"] = "invalid optional SHA"
    payload["items"] += [None, {"path": "src/x.py", "repository": {"id": 0, "full_name": "science/tool"}}]
    payload["total_count"] = 3
    client, _ = install_pages(monkeypatch, [payload])
    batch = code.search_code(["science"], client=client)
    assert len(batch.signals) == 1
    assert batch.error is None
    assert batch.coverage_reasons == ("unmapped_items",)


@pytest.mark.parametrize("kwargs", [{"max_pages": 0}, {"max_pages": 11}, {"max_pages": True},
                                    {"per_query_limit": 0}, {"per_query_limit": 101}])
def test_invalid_page_budget_cannot_issue_network_requests(monkeypatch, kwargs):
    client, requests = install_pages(monkeypatch, [])
    with pytest.raises(ValueError):
        code.search_code(["science"], client=client, **kwargs)
    assert not requests


def test_strict_offline_collector_still_raises_terminal_errors(monkeypatch):
    error = RepositorySourceError(source="github", status="error", public_message="Unavailable")
    client, _ = install_pages(monkeypatch, [page(100, 300), error])
    with pytest.raises(RepositorySourceError) as caught:
        code.discover_repository_candidates_from_code(["science"], client=client)
    assert caught.value is error
