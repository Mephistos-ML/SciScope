"""Tests for GitHub query building and repository discovery."""

from __future__ import annotations

from app.seeds.topics import PNMR_PROFILE
from app.sources.github import discovery as github_discovery
from app.sources.github.query_builder import build_repository_search_queries


def test_build_repository_search_queries_uses_profile_terms() -> None:
    queries = build_repository_search_queries(PNMR_PROFILE)

    assert queries
    assert "paramagnetic nmr" in queries
    assert "pseudocontact shift" in queries
    assert "susceptibility tensor" in queries
    assert "paramagnetic relaxation enhancement" in queries
    assert "paranmr" not in queries
    assert len(queries) <= 5


def test_discover_repository_candidates_builds_raw_signals(monkeypatch) -> None:
    def fake_fetch_json(url: str) -> object:
        assert "/search/repositories" in url
        return {
            "items": [
                {
                    "full_name": "Mephistos-ML/paranmr",
                    "html_url": "https://github.com/Mephistos-ML/paranmr",
                    "description": "Paramagnetic NMR tooling for PCS fitting.",
                    "topics": ["paramagnetic-nmr", "pcs"],
                    "language": "Python",
                    "stargazers_count": 14,
                    "owner": {"login": "Mephistos-ML"},
                }
            ]
        }

    monkeypatch.setattr(github_discovery, "fetch_json", fake_fetch_json)

    signals = github_discovery.discover_repository_candidates(
        ["paramagnetic NMR software"],
        per_query_limit=3,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.source_type == "github_repository"
    assert signal.item_id == "github:repo:Mephistos-ML/paranmr"
    assert signal.payload["repo"] == "Mephistos-ML/paranmr"
    assert signal.payload["stars"] == 14
    assert "Paramagnetic NMR tooling" in signal.raw_text
