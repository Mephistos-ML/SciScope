"""Tests for discovery orchestration into persistent entity memory."""

from __future__ import annotations

from tests.fixtures.profiles import PNMR_PROFILE
from tests.conftest import build_test_database_url, migrate_test_database
from app.sources.repositories.runtime import discover_repository_entities_for_profile
from app.storage.entities import list_entities, list_subscription_entity_matches


def test_discover_repository_entities_for_profile_persists_matched_repositories(
    monkeypatch,
    tmp_path,
) -> None:
    from app.sources.repositories.github import discovery as github_discovery
    from app.sources.repositories.gitlab import discovery as gitlab_discovery
    from app.models.signal import RawSignal

    def fake_discover_repository_candidates(queries: tuple[str, ...]) -> list[RawSignal]:
        assert queries
        return [
            RawSignal(
                source="github",
                source_type="github_repository",
                item_id="github:repo:Mephistos-ML/paranmr",
                title="Mephistos-ML/paranmr",
                url="https://github.com/Mephistos-ML/paranmr",
                published_at=None,
                raw_text=(
                    "Paramagnetic NMR software for susceptibility tensor fitting "
                    "and PCS workflows."
                ),
                payload={
                    "signal_kind": "github_repository",
                    "repo": "Mephistos-ML/paranmr",
                    "query": "paramagnetic NMR software",
                    "topics": ["paramagnetic-nmr", "pcs"],
                    "language": "Python",
                    "stars": 14,
                },
            ),
            RawSignal(
                source="github",
                source_type="github_repository",
                item_id="github:repo:example/batteries",
                title="example/batteries",
                url="https://github.com/example/batteries",
                published_at=None,
                raw_text="Solid state battery polymer electrolyte workflows.",
                payload={
                    "signal_kind": "github_repository",
                    "repo": "example/batteries",
                    "query": "paramagnetic NMR software",
                    "topics": ["battery"],
                    "language": "Python",
                    "stars": 2,
                },
            ),
        ]

    monkeypatch.setattr(
        github_discovery,
        "discover_repository_candidates",
        fake_discover_repository_candidates,
    )
    monkeypatch.setattr(
        gitlab_discovery,
        "discover_repository_candidates",
        lambda queries: [],
    )

    database_url = build_test_database_url(tmp_path / "discovery.sqlite3")
    migrate_test_database(database_url)
    result = discover_repository_entities_for_profile(
        PNMR_PROFILE,
        database_url=database_url,
    )

    entities = list_entities(source="github", database_url=database_url)
    matches = list_subscription_entity_matches("pnmr", database_url=database_url)

    assert result.topic_slug == "pnmr"
    assert result.candidate_count == 2
    assert result.entity_count == 1
    assert result.matched_entity_count == 1
    assert len(entities) == 1
    assert entities[0].canonical_name == "Mephistos-ML/paranmr"
    assert len(matches) == 1
    assert matches[0].entity_id == "github:repo:Mephistos-ML/paranmr"
