"""Tests for loading watched repositories from persistent topic memory."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entity import Entity, TopicEntityMatch
from app.models.signal import RawSignal
from app.services import monitoring


def test_load_watched_github_repositories_uses_topic_memory(monkeypatch) -> None:
    monkeypatch.setattr(
        monitoring,
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
        monitoring,
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

    repos = monitoring.load_watched_github_repository_entities("pnmr")

    assert len(repos) == 1
    assert repos[0].canonical_name == "Mephistos-ML/paranmr"


def test_load_live_github_signals_reads_repositories_from_watch_memory(
    monkeypatch,
) -> None:
    repo_entity = Entity(
        entity_id="github:repo:Mephistos-ML/paranmr",
        source="github",
        entity_type="repository",
        canonical_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
    monkeypatch.setattr(
        monitoring,
        "load_watched_github_repository_entities",
        lambda topic_slug: (repo_entity,),
    )
    monkeypatch.setattr(
        monitoring,
        "get_entity_checkpoint",
        lambda entity_id, checkpoint_key: None,
    )
    monkeypatch.setattr(
        monitoring.STATE,
        "monitoring_started_at",
        datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(monitoring, "upsert_entity_checkpoints", lambda checkpoints: None)
    called: list[tuple[str, datetime | None]] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append((repo_full_name, started_after))
        return [
            RawSignal(
                source="github",
                source_type="github_release",
                item_id="Mephistos-ML/paranmr:release:12",
                title="Mephistos-ML/paranmr release v0.3.0",
                url="https://github.com/Mephistos-ML/paranmr/releases/tag/v0.3.0",
                published_at=datetime(2026, 7, 18, 10, 15, tzinfo=UTC),
                raw_text="PCS fitting improvements.",
                payload={
                    "signal_kind": "github_release",
                    "repo": "Mephistos-ML/paranmr",
                    "tag_name": "v0.3.0",
                    "source_type": "github_release",
                },
            )
        ]

    monkeypatch.setattr(monitoring, "load_repo_activity", fake_load_repo_activity)

    signals = monitoring.load_github_signals_for_profile(
        type("Profile", (), {"topic_slug": "pnmr"})(),
    )

    assert len(signals) == 1
    assert called == [("Mephistos-ML/paranmr", datetime(2026, 7, 18, 10, 0, tzinfo=UTC))]


def test_load_live_github_signals_uses_entity_checkpoint_when_present(monkeypatch) -> None:
    repo_entity = Entity(
        entity_id="github:repo:Mephistos-ML/paranmr",
        source="github",
        entity_type="repository",
        canonical_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
    monkeypatch.setattr(
        monitoring,
        "load_watched_github_repository_entities",
        lambda topic_slug: (repo_entity,),
    )
    monkeypatch.setattr(
        monitoring,
        "get_entity_checkpoint",
        lambda entity_id, checkpoint_key: monitoring.EntityCheckpoint(
            entity_id=entity_id,
            source="github",
            checkpoint_key=checkpoint_key,
            checkpoint_value="2026-07-18T09:30:00+00:00",
            updated_at=datetime(2026, 7, 18, 9, 31, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(monitoring, "upsert_entity_checkpoints", lambda checkpoints: None)
    called: list[datetime | None] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append(started_after)
        return []

    monkeypatch.setattr(monitoring, "load_repo_activity", fake_load_repo_activity)

    monitoring.load_github_signals_for_profile(
        type("Profile", (), {"topic_slug": "pnmr"})(),
    )

    assert called == [datetime(2026, 7, 18, 9, 30, tzinfo=UTC)]
