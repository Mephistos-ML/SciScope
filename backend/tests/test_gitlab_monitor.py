"""Tests for GitLab watch-memory monitoring and checkpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entity import Entity, TopicEntityMatch
from app.models.signal import RawSignal
from app.sources.repositories.gitlab import monitor as gitlab_monitor
from app.sources.repositories.gitlab import state as gitlab_state


def test_load_watched_gitlab_repositories_uses_topic_memory(monkeypatch) -> None:
    monkeypatch.setattr(
        gitlab_state,
        "list_topic_entity_matches",
        lambda topic_slug: [
            TopicEntityMatch(
                topic_slug=topic_slug,
                entity_id="gitlab:repo:Mephistos-ML/paranmr",
                source="gitlab",
                score=5.0,
                matched_terms=("paramagnetic nmr",),
                reason="Matched seeded topic.",
            )
        ],
    )
    monkeypatch.setattr(
        gitlab_state,
        "list_entities_by_ids",
        lambda entity_ids: [
            Entity(
                entity_id="gitlab:repo:Mephistos-ML/paranmr",
                source="gitlab",
                entity_type="repository",
                canonical_name="Mephistos-ML/paranmr",
                url="https://gitlab.com/Mephistos-ML/paranmr",
                metadata={"repo": "Mephistos-ML/paranmr"},
            )
        ],
    )

    repos = gitlab_state.load_watched_gitlab_repository_entities("pnmr")

    assert len(repos) == 1
    assert repos[0].canonical_name == "Mephistos-ML/paranmr"


def test_load_live_gitlab_signals_reads_repositories_from_watch_memory(
    monkeypatch,
) -> None:
    repo_entity = Entity(
        entity_id="gitlab:repo:Mephistos-ML/paranmr",
        source="gitlab",
        entity_type="repository",
        canonical_name="Mephistos-ML/paranmr",
        url="https://gitlab.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "load_watched_gitlab_repository_entities",
        lambda topic_slug: (repo_entity,),
    )
    monkeypatch.setattr(
        gitlab_monitor.STATE,
        "monitoring_started_at",
        datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "resolve_release_checkpoint",
        lambda entity, baseline_started_after: baseline_started_after,
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "upsert_entity_checkpoints",
        lambda checkpoints: None,
    )
    called: list[tuple[str, datetime | None]] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append((repo_full_name, started_after))
        return [
            RawSignal(
                source="gitlab",
                source_type="gitlab_release",
                item_id="Mephistos-ML/paranmr:release:v0.3.0",
                title="Mephistos-ML/paranmr release v0.3.0",
                url="https://gitlab.com/Mephistos-ML/paranmr/-/releases/v0.3.0",
                published_at=datetime(2026, 7, 18, 10, 15, tzinfo=UTC),
                raw_text="PCS fitting improvements.",
                payload={
                    "signal_kind": "gitlab_release",
                    "repo": "Mephistos-ML/paranmr",
                    "tag_name": "v0.3.0",
                    "source_type": "gitlab_release",
                },
            )
        ]

    monkeypatch.setattr(gitlab_monitor, "load_repo_activity", fake_load_repo_activity)

    signals = gitlab_monitor.load_gitlab_signals_for_profile(
        type("Profile", (), {"topic_slug": "pnmr"})(),
    )

    assert len(signals) == 1
    assert called == [("Mephistos-ML/paranmr", datetime(2026, 7, 18, 10, 0, tzinfo=UTC))]


def test_load_live_gitlab_signals_uses_entity_checkpoint_when_present(monkeypatch) -> None:
    repo_entity = Entity(
        entity_id="gitlab:repo:Mephistos-ML/paranmr",
        source="gitlab",
        entity_type="repository",
        canonical_name="Mephistos-ML/paranmr",
        url="https://gitlab.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "load_watched_gitlab_repository_entities",
        lambda topic_slug: (repo_entity,),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "resolve_release_checkpoint",
        lambda entity, baseline_started_after: datetime(2026, 7, 18, 9, 30, tzinfo=UTC),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "build_release_checkpoint",
        lambda entity, latest_published_at, fallback_started_after: gitlab_state.EntityCheckpoint(
            entity_id=entity.entity_id,
            source="gitlab",
            checkpoint_key=gitlab_state.REPOSITORY_RELEASE_CHECKPOINT_KEY,
            checkpoint_value="2026-07-18T09:30:00+00:00",
            updated_at=datetime(2026, 7, 18, 9, 31, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "upsert_entity_checkpoints",
        lambda checkpoints: None,
    )
    called: list[datetime | None] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append(started_after)
        return []

    monkeypatch.setattr(gitlab_monitor, "load_repo_activity", fake_load_repo_activity)

    gitlab_monitor.load_gitlab_signals_for_profile(
        type("Profile", (), {"topic_slug": "pnmr"})(),
    )

    assert called == [datetime(2026, 7, 18, 9, 30, tzinfo=UTC)]
