# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Tests for GitHub code-aware repository search."""

from __future__ import annotations

import pytest
from urllib.parse import parse_qs, urlsplit
from tests.fixtures.repository_clients import make_repository_client

from app.integrations.repositories.github.search import code as github_code_search
from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.github.search.file_policy import CODE_SEARCH_EXTENSION_SUFFIX


def test_discover_repository_candidates_from_code_builds_repository_signal(
    monkeypatch, repository_client,
) -> None:
    def fake_fetch_json(url: str) -> JsonResponse:
        if "/search/code" in url:
            assert "orca+python+package" in url
            assert "page=1" in url
            return JsonResponse(payload={
                "items": [
                    {
                        "repository": {
                            "id": 101,
                            "full_name": "kragskow-group/orto",
                            "html_url": "https://github.com/kragskow-group/orto",
                            "description": "",
                            "updated_at": "2026-09-03T12:30:00Z",
                            "owner": {"login": "kragskow-group"},
                        },
                        "path": "src/orto/io/orca_output.py",
                    }
                ]
            }, url=url)

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(repository_client, "fetch_json", fake_fetch_json)

    signals = github_code_search.discover_repository_candidates_from_code(client=repository_client, queries=
        ["orca python package"],
        per_query_limit=5,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.kind == "repository"
    assert signal.item_id == "github:repo:101"
    assert signal.payload["query"] == "orca python package"
    assert signal.payload["provider_updated_at"] == "2026-09-03T12:30:00+00:00"
    assert "Matched code path: src/orto/io/orca_output.py" in signal.raw_text


def test_discover_repository_candidates_from_code_reads_second_page(
    monkeypatch, repository_client,
) -> None:
    requested_urls: list[str] = []

    def fake_fetch_json(url: str) -> JsonResponse:
        requested_urls.append(url)
        if "page=1" in url:
            return JsonResponse(payload={
                "items": [
                    {
                        "repository": {
                            "id": 101,
                            "full_name": "kragskow-group/orto",
                            "html_url": "https://github.com/kragskow-group/orto",
                            "description": "",
                            "owner": {"login": "kragskow-group"},
                        },
                        "path": "src/orto/io/orca_output.py",
                    }
                ]
            }, url=url)
        if "page=2" in url:
            return JsonResponse(payload={
                "items": [
                    {
                        "repository": {
                            "id": 202,
                            "full_name": "thermotools/lammps_mie_fh",
                            "html_url": "https://github.com/thermotools/lammps_mie_fh",
                            "description": "",
                            "owner": {"login": "thermotools"},
                        },
                        "path": "src/pair_mie_fh.cpp",
                    }
                ]
            }, url=url)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(repository_client, "fetch_json", fake_fetch_json)

    signals = github_code_search.discover_repository_candidates_from_code(client=repository_client, queries=
        ["orca python package"],
        per_query_limit=1,
        max_pages=2,
    )

    assert len(signals) == 2
    assert any("page=2" in url for url in requested_urls)


@pytest.fixture
def repository_client():
    return make_repository_client("github")


@pytest.mark.parametrize("query", ["paramagnetic nmr", "x" * 185, 'method "quoted"', r"method\file"])
def test_code_search_sends_one_filtered_request_with_a_literal_phrase(
    monkeypatch, repository_client, query,
):
    requests = []

    def fetch(url):
        requests.append(url)
        return JsonResponse({"items": []}, url)

    monkeypatch.setattr(repository_client, "fetch_json", fetch)
    assert github_code_search.discover_repository_candidates_from_code(
        [query], client=repository_client,
    ) == []
    assert len(requests) == 1
    params = parse_qs(urlsplit(requests[0]).query)
    escaped = query.replace("\\", "\\\\").replace('"', '\\"')
    assert params["q"] == [f'"{escaped}" {CODE_SEARCH_EXTENSION_SUFFIX}']
    assert len(params["q"][0]) <= 1000


@pytest.mark.parametrize("query", ["x" * 186, "x" * 184 + '"', "x" * 184 + "\\"])
def test_code_search_rejects_overflow_before_network_io(
    monkeypatch, repository_client, query,
):
    def fetch(url):
        pytest.fail("An overlength request must not reach GitHub")

    monkeypatch.setattr(repository_client, "fetch_json", fetch)
    with pytest.raises(ValueError, match="1000-character limit"):
        github_code_search.discover_repository_candidates_from_code(
            [query], client=repository_client,
        )
