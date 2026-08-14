"""Tests for GitLab query building and repository discovery."""

from __future__ import annotations

from app.sources.gitlab import discovery as gitlab_discovery


def test_discover_repository_candidates_builds_raw_signals(monkeypatch) -> None:
    def fake_fetch_json(url: str) -> object:
        assert "/search" in url
        assert "scope=projects" in url
        return [
            {
                "path_with_namespace": "Mephistos-ML/paranmr",
                "web_url": "https://gitlab.com/Mephistos-ML/paranmr",
                "description": "Paramagnetic NMR tooling for PCS fitting.",
                "topics": ["paramagnetic-nmr", "pcs"],
                "star_count": 14,
            }
        ]

    monkeypatch.setattr(gitlab_discovery, "fetch_json", fake_fetch_json)

    signals = gitlab_discovery.discover_repository_candidates(
        ["paramagnetic NMR software"],
        per_query_limit=3,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.kind == "repository"
    assert signal.item_id == "gitlab:repo:Mephistos-ML/paranmr"
    assert signal.payload["repo"] == "Mephistos-ML/paranmr"
    assert signal.payload["stars"] == 14
    assert "Paramagnetic NMR tooling" in signal.raw_text
