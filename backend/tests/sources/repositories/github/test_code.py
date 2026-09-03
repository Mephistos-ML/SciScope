"""Tests for GitHub code-aware repository search."""

from __future__ import annotations

from app.sources.github.search import code as github_code_search


def test_discover_repository_candidates_from_code_builds_repository_signal(
    monkeypatch,
) -> None:
    def fake_fetch_json(url: str) -> object:
        if "/search/code" in url:
            assert "orca+python+package" in url
            assert "page=1" in url
            return {
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
            }

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(github_code_search, "fetch_json", fake_fetch_json)

    signals = github_code_search.discover_repository_candidates_from_code(
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
    monkeypatch,
) -> None:
    requested_urls: list[str] = []

    def fake_fetch_json(url: str) -> object:
        requested_urls.append(url)
        if "page=1" in url:
            return {
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
            }
        if "page=2" in url:
            return {
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
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(github_code_search, "fetch_json", fake_fetch_json)

    signals = github_code_search.discover_repository_candidates_from_code(
        ["orca python package"],
        per_query_limit=1,
        max_pages=2,
    )

    assert len(signals) == 2
    assert any("page=2" in url for url in requested_urls)
