"""Tests for GitHub README-aware repository search."""

from __future__ import annotations

import base64

from app.sources.github.search import readme as github_readme_search


def test_discover_repository_candidates_from_readme_builds_repository_signal(
    monkeypatch,
) -> None:
    def fake_fetch_json(url: str) -> object:
        if "/search/code" in url:
            assert "filename%3AREADME.md" in url
            return {
                "items": [
                    {
                        "repository": {
                            "full_name": "kragskow-group/orto",
                            "html_url": "https://github.com/kragskow-group/orto",
                            "description": "",
                            "owner": {"login": "kragskow-group"},
                        }
                    }
                ]
            }

        assert "/repos/kragskow-group%2Forto/readme" in url
        return {
            "content": base64.b64encode(
                b"# ORTO\nA python package for working with ORCA outputs.\n"
            ).decode("ascii")
        }

    monkeypatch.setattr(github_readme_search, "fetch_json", fake_fetch_json)

    signals = github_readme_search.discover_repository_candidates_from_readme(
        ["orca python package"],
        per_query_limit=5,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.kind == "repository"
    assert signal.item_id == "github:repo:kragskow-group/orto"
    assert signal.payload["query"] == "orca python package"
    assert "A python package for working with ORCA outputs." in signal.raw_text
