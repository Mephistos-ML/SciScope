"""Tests for GitLab README-aware repository search."""

from __future__ import annotations

from app.sources.gitlab.search import readme as gitlab_readme_search


def test_discover_repository_candidates_from_readme_builds_repository_signal(
    monkeypatch,
) -> None:
    def fake_fetch_json(url: str) -> object:
        if "scope=blobs" in url:
            assert "filename%3AREADME%2A" in url
            return [
                {
                    "project_id": 42,
                    "data": "A python package for working with ORCA outputs.",
                    "path": "README.md",
                }
            ]

        assert url.endswith("/projects/42")
        return {
            "path_with_namespace": "kragskow-group/orto",
            "web_url": "https://gitlab.com/kragskow-group/orto",
            "description": "",
            "topics": ["orca", "chemistry"],
            "star_count": 19,
        }

    monkeypatch.setattr(gitlab_readme_search, "fetch_json", fake_fetch_json)

    signals = gitlab_readme_search.discover_repository_candidates_from_readme(
        ["orca python package"],
        per_query_limit=5,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.kind == "repository"
    assert signal.item_id == "gitlab:repo:kragskow-group/orto"
    assert signal.payload["query"] == "orca python package"
    assert signal.payload["stars"] == 19
    assert "A python package for working with ORCA outputs." in signal.raw_text
