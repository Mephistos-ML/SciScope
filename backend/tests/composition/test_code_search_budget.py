"""Product pagination and parallel channels exercised through real adapters."""

from collections import defaultdict
from threading import Barrier, Lock
from time import monotonic
from urllib.parse import parse_qs, urlsplit

import pytest

from app import config
from app.composition.repositories import build_repository_adapters
from app.composition.search import build_explore_dependencies
from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.github.client import GitHubClient
from app.integrations.repositories.github.search.file_policy import build_code_search_query
from app.integrations.repositories.gitlab.client import GitLabClient
from app.services.search.retrieval.service import run_external_repository_retrieval


@pytest.mark.parametrize("page_sizes", [(100, 100, 100), (100, 17), (0,)])
def test_product_code_budget_preserves_parallel_repository_search(monkeypatch, page_sizes):
    monkeypatch.setattr(config, "GITLAB_BASE_URL", "https://gitlab.com")
    dependencies = build_explore_dependencies(repositories=build_repository_adapters())
    queries = ("paramagnetic NMR", "contact shifts", "pseudocontact shifts")
    calls = defaultdict(list)
    gate = Barrier(3)
    lock = Lock()
    deadline = monotonic() + 30

    def record(channel, url, received_deadline):
        assert received_deadline is not None
        assert monotonic() < received_deadline <= deadline
        with lock:
            first = not calls[channel]
            calls[channel].append(url)
        # Every real lane must reach IO before any of them can continue.
        if first:
            gate.wait(timeout=5)

    def github_fetch(client, url, *, deadline_monotonic=None, max_response_bytes=None):
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        if parsed.path == "/search/code":
            record("github_code", url, deadline_monotonic)
            assert params["q"][0] in [build_code_search_query(query) for query in queries]
            assert params["per_page"] == ["100"]
            page = int(params["page"][0])
            assert page <= len(page_sizes), "Code search exceeded its product page budget"
            items = [{
                "path": f"src/file_{page}_{index}.py",
                "repository": {"id": 1, "full_name": "science/code", "html_url": "https://github.com/science/code"},
            } for index in range(page_sizes[page - 1])]
            return JsonResponse(payload={"total_count": (900 if page_sizes[-1] == 100 else sum(page_sizes)), "incomplete_results": False, "items": items}, url=url)
        assert parsed.path == "/search/repositories"
        record("github_repo", url, deadline_monotonic)
        assert params["q"][0] in [f'"{query}"' for query in queries]
        assert params["per_page"] == ["50"]
        return JsonResponse(payload={"items": [{
            "id": 2, "full_name": "science/github-repo", "html_url": "https://github.com/science/github-repo",
        }]}, url=url)

    def gitlab_fetch(client, url, *, deadline_monotonic=None, max_response_bytes=None):
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        assert parsed.path == "/api/v4/search"
        record("gitlab_repo", url, deadline_monotonic)
        assert params["scope"] == ["projects"]
        assert params["search"][0] in [f'"{query}"' for query in queries]
        assert params["per_page"] == ["30"]
        return JsonResponse(payload=[{
            "id": 3, "path_with_namespace": "science/gitlab-repo", "web_url": "https://gitlab.com/science/gitlab-repo",
        }], url=url)

    monkeypatch.setattr(GitHubClient, "fetch_json", github_fetch)
    monkeypatch.setattr(GitLabClient, "fetch_json", gitlab_fetch)
    result = run_external_repository_retrieval(
        queries, lanes=dependencies.lanes, hard_deadline_monotonic=deadline,
    )
    assert len(calls["github_code"]) == len(queries) * len(page_sizes)
    assert len(calls["github_repo"]) == len(calls["gitlab_repo"]) == len(queries)
    for query in queries:
        pages = [int(parse_qs(urlsplit(url).query)["page"][0]) for url in calls["github_code"]
                 if parse_qs(urlsplit(url).query)["q"] == [build_code_search_query(query)]]
        assert pages == list(range(1, len(page_sizes) + 1))
    expected_ids = {"github:repo:2", "gitlab:repo:3"}
    if any(page_sizes):
        expected_ids.add("github:repo:1")
    assert {candidate.repository_id for candidate in result.candidates} == expected_ids
    assert result.successful_source_count == 2
    assert result.partial == (page_sizes[-1] == 100)
    outcome = next(item for item in result.lane_outcomes if item.channel == "code_search")
    assert outcome.status == ("partial" if page_sizes[-1] == 100 else "ok")
    assert outcome.error_code == ("page_budget" if page_sizes[-1] == 100 else None)


@pytest.mark.parametrize("failure", ["timed_out", "rate_limited", "unauthorized", "error"])
def test_code_page_failure_preserves_prefix_and_other_channels(monkeypatch, failure):
    from app.integrations.repositories.common.source_status import RepositorySourceError

    monkeypatch.setattr(config, "GITLAB_BASE_URL", "https://gitlab.com")
    dependencies = build_explore_dependencies(repositories=build_repository_adapters())
    pages = []

    def github_fetch(client, url, **kwargs):
        if urlsplit(url).path == "/search/repositories":
            return JsonResponse({"items": [{"id": 2, "full_name": "science/repo", "html_url": "https://github.com/science/repo"}]}, url)
        current = int(parse_qs(urlsplit(url).query)["page"][0])
        pages.append(current)
        if current == 2:
            raise RepositorySourceError(source="github", status=failure, public_message="Unavailable", retry_after_seconds=60)
        return JsonResponse({"total_count": 300, "incomplete_results": False, "items": [
            {"path": f"src/{index}.py", "repository": {"id": 1, "full_name": "science/code"}}
            for index in range(100)
        ]}, url)

    monkeypatch.setattr(GitHubClient, "fetch_json", github_fetch)
    monkeypatch.setattr(GitLabClient, "fetch_json", lambda client, url, **kwargs: JsonResponse(
        [{"id": 3, "path_with_namespace": "science/gitlab", "web_url": "https://gitlab.com/science/gitlab"}], url,
    ))
    result = run_external_repository_retrieval(["scientific phrase"], lanes=dependencies.lanes)
    assert pages == [1, 2]
    assert {candidate.repository_id for candidate in result.candidates} == {"github:repo:1", "github:repo:2", "gitlab:repo:3"}
    assert result.successful_source_count == 2
    assert result.partial is True
    outcome = next(item for item in result.lane_outcomes if item.channel == "code_search")
    assert outcome.status == "partial"
    assert outcome.candidate_count == 100
    assert outcome.error_code == failure
    assert outcome.retry_after_seconds == 60
