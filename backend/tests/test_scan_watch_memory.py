"""Tests for loading watched repositories from persistent topic memory."""

from __future__ import annotations

from app.models.entity import Entity, TopicEntityMatch
from app.services import scan_service


def test_load_watched_github_repositories_uses_topic_memory(monkeypatch) -> None:
    monkeypatch.setattr(
        scan_service,
        "list_topic_entity_matches",
        lambda topic_slug: [
            TopicEntityMatch(
                topic_slug=topic_slug,
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                score=5.0,
                matched_terms=("paramagnetic nmr",),
                reason="Matched seeded topic.",
            )
        ],
    )
    monkeypatch.setattr(
        scan_service,
        "list_entities_by_ids",
        lambda entity_ids: [
            Entity(
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                entity_type="repository",
                canonical_name="Mephistos-ML/paranmr",
                url="https://github.com/Mephistos-ML/paranmr",
                metadata={"repo": "Mephistos-ML/paranmr"},
            )
        ],
    )

    repos = scan_service._load_watched_github_repositories()

    assert repos == ("Mephistos-ML/paranmr",)


def test_load_live_github_signals_reads_repositories_from_watch_memory(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        scan_service,
        "_load_watched_github_repositories",
        lambda: ("Mephistos-ML/paranmr", "example/other"),
    )
    called_repos: list[str] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called_repos.append(repo_full_name)
        return []

    monkeypatch.setattr(scan_service, "load_repo_activity", fake_load_repo_activity)

    scan_service._load_live_github_signals()

    assert called_repos == ["Mephistos-ML/paranmr", "example/other"]
