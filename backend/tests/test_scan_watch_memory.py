"""Tests for loading watched repositories from persistent subscription memory."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.entity import Entity, SubscriptionEntityMatch
from app.models.signal import RawSignal
from app.sources.repositories.github import monitor as github_monitor
from app.sources.repositories.github import state as github_state


def test_load_watched_github_repositories_uses_topic_memory(monkeypatch) -> None:
    monkeypatch.setattr(
        github_state,
        "list_subscription_entity_matches",
        lambda subscription_id: [
            SubscriptionEntityMatch(
                subscription_id=subscription_id,
                entity_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                score=5.0,
                matched_terms=("paramagnetic nmr",),
                reason="Matched seeded topic.",
            )
        ],
    )
    monkeypatch.setattr(
        github_state,
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

    repos = github_state.load_watched_github_repository_entities("pnmr")

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
        github_monitor,
        "load_watched_github_repository_entities",
        lambda subscription_id: (repo_entity,),
    )
    monkeypatch.setattr(
        github_monitor.STATE,
        "monitoring_started_at",
        datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(
        github_monitor,
        "resolve_release_checkpoint",
        lambda subscription_id, entity, baseline_started_after: baseline_started_after,
    )
    monkeypatch.setattr(
        github_monitor,
        "upsert_entity_checkpoints",
        lambda checkpoints: None,
    )
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

    monkeypatch.setattr(github_monitor, "load_repo_activity", fake_load_repo_activity)

    signals = github_monitor.load_github_signals_for_profile(
        type("Profile", (), {"topic_slug": "sub_pnmr"})(),
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
        github_monitor,
        "load_watched_github_repository_entities",
        lambda subscription_id: (repo_entity,),
    )
    monkeypatch.setattr(
        github_monitor,
        "resolve_release_checkpoint",
        lambda subscription_id, entity, baseline_started_after: datetime(
            2026, 7, 18, 9, 30, tzinfo=UTC
        ),
    )
    monkeypatch.setattr(
        github_monitor,
        "build_release_checkpoint",
        lambda subscription_id, entity, latest_published_at, fallback_started_after: github_state.EntityCheckpoint(
            subscription_id=subscription_id,
            entity_id=entity.entity_id,
            source="github",
            checkpoint_key=github_state.REPOSITORY_RELEASE_CHECKPOINT_KEY,
            checkpoint_value="2026-07-18T09:30:00+00:00",
            updated_at=datetime(2026, 7, 18, 9, 31, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        github_monitor,
        "upsert_entity_checkpoints",
        lambda checkpoints: None,
    )
    called: list[datetime | None] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append(started_after)
        return []

    monkeypatch.setattr(github_monitor, "load_repo_activity", fake_load_repo_activity)

    github_monitor.load_github_signals_for_profile(
        type("Profile", (), {"topic_slug": "sub_pnmr"})(),
    )

    assert called == [datetime(2026, 7, 18, 9, 30, tzinfo=UTC)]
