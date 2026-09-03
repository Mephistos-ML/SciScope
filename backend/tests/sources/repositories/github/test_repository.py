"""Tests for GitHub repository search."""

from __future__ import annotations

from app.sources.github.search import repository as github_repository_search


def test_discover_repository_candidates_builds_raw_signals(monkeypatch) -> None:
    def fake_fetch_json(url: str) -> object:
        assert "/search/repositories" in url
        return {
            "items": [
                {
                    "id": 123,
                    "full_name": "Mephistos-ML/paranmr",
                    "html_url": "https://github.com/Mephistos-ML/paranmr",
                    "description": "Paramagnetic NMR tooling for PCS fitting.",
                    "topics": ["paramagnetic-nmr", "pcs"],
                    "language": "Python",
                    "stargazers_count": 14,
                    "updated_at": "2026-09-03T12:30:00Z",
                    "owner": {"login": "Mephistos-ML"},
                }
            ]
        }

    monkeypatch.setattr(github_repository_search, "fetch_json", fake_fetch_json)

    signals = github_repository_search.discover_repository_candidates(
        ["paramagnetic NMR software"],
        per_query_limit=3,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.kind == "repository"
    assert signal.item_id == "github:repo:123"
    assert signal.payload["repo"] == "Mephistos-ML/paranmr"
    assert signal.payload["stars"] == 14
    assert signal.payload["provider_updated_at"] == "2026-09-03T12:30:00+00:00"
    assert "Paramagnetic NMR tooling" in signal.raw_text
