"""Tests for GitLab code-aware repository search."""

from __future__ import annotations

from app.sources.common import RepositorySourceError
from app.sources.gitlab.search import code as gitlab_code_search


def test_discover_repository_candidates_from_code_builds_repository_signal(
    monkeypatch,
) -> None:
    def fake_fetch_json(url: str) -> object:
        if "scope=blobs" in url:
            assert "orca+python+package" in url
            return [
                {
                    "project_id": 42,
                    "data": "A python package for working with ORCA outputs.",
                    "path": "src/orto/io/orca_output.py",
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

    monkeypatch.setattr(gitlab_code_search, "fetch_json", fake_fetch_json)

    signals = gitlab_code_search.discover_repository_candidates_from_code(
        ["orca python package"],
        per_query_limit=5,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.kind == "repository"
    assert signal.item_id == "gitlab:repo:42"
    assert signal.payload["provider_repository_id"] == "42"
    assert signal.payload["query"] == "orca python package"
    assert signal.payload["stars"] == 19
    assert "Matched code path: src/orto/io/orca_output.py" in signal.raw_text


def test_discover_repository_candidates_from_code_skips_project_when_metadata_fails(
    monkeypatch,
) -> None:
    def fake_fetch_json(url: str) -> object:
        if "scope=blobs" in url:
            return [
                {
                    "project_id": 42,
                    "data": "Feynman-Hibbs corrected Mie pair potential.",
                    "path": "src/bad/path.cpp",
                },
                {
                    "project_id": 43,
                    "data": "LAMMPS package for Mie-FH simulations.",
                    "path": "src/pair_mie_fh.cpp",
                },
            ]

        if url.endswith("/projects/42"):
            raise RepositorySourceError(
                source="gitlab",
                status="unauthorized",
                public_message="GitLab repository access is unauthorized right now.",
            )

        assert url.endswith("/projects/43")
        return {
            "path_with_namespace": "thermotools/lammps_mie_fh",
            "web_url": "https://gitlab.com/thermotools/lammps_mie_fh",
            "description": "",
            "topics": ["lammps", "molecular-simulation"],
            "star_count": 7,
        }

    monkeypatch.setattr(gitlab_code_search, "fetch_json", fake_fetch_json)

    signals = gitlab_code_search.discover_repository_candidates_from_code(
        ["feynman hibbs lammps"],
        per_query_limit=5,
    )

    assert len(signals) == 1
    signal = signals[0]
    assert signal.item_id == "gitlab:repo:43"
    assert signal.payload["query"] == "feynman hibbs lammps"
