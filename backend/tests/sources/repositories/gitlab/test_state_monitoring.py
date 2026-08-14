"""Tests for GitLab subscription-memory monitoring and checkpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.repository import (
    Repository,
    RepositoryCheckpoint,
    SubscriptionRepositoryMatch,
)
from app.models.signal import RawSignal
from app.models.subscription import SubscriptionQueryProfile
from app.sources.gitlab import monitor as gitlab_monitor
from app.sources.gitlab import state as gitlab_state


def test_load_watched_gitlab_repositories_uses_subscription_memory(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        gitlab_state,
        "list_subscription_repository_matches",
        lambda subscription_id: [
            SubscriptionRepositoryMatch(
                subscription_id=subscription_id,
                repository_id="gitlab:repo:Mephistos-ML/paranmr",
                source="gitlab",
                score=5.0,
                matched_terms=("paramagnetic nmr",),
                reason="Matched subscription terms.",
            )
        ],
    )
    monkeypatch.setattr(
        gitlab_state,
        "list_repositories_by_ids",
        lambda repository_ids: [
            Repository(
                repository_id="gitlab:repo:Mephistos-ML/paranmr",
                source="gitlab",
                full_name="Mephistos-ML/paranmr",
                url="https://gitlab.com/Mephistos-ML/paranmr",
                metadata={"repo": "Mephistos-ML/paranmr"},
            )
        ],
    )

    repos = gitlab_state.load_watched_gitlab_repository_entities("pnmr")

    assert len(repos) == 1
    assert repos[0].full_name == "Mephistos-ML/paranmr"


def test_load_live_gitlab_signals_reads_repositories_from_watch_memory(
    monkeypatch,
) -> None:
    repository = Repository(
        repository_id="gitlab:repo:Mephistos-ML/paranmr",
        source="gitlab",
        full_name="Mephistos-ML/paranmr",
        url="https://gitlab.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "load_watched_gitlab_repositories",
        lambda subscription_id: (repository,),
    )
    monkeypatch.setattr(
        gitlab_monitor.STATE,
        "monitoring_started_at",
        datetime(2026, 7, 18, 10, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "resolve_release_checkpoint",
        lambda subscription_id, repository, baseline_started_after: baseline_started_after,
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "upsert_repository_checkpoints",
        lambda checkpoints: None,
    )
    called: list[tuple[str, datetime | None]] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append((repo_full_name, started_after))
        return [
            RawSignal(
                source="gitlab",
                kind="release",
                item_id="Mephistos-ML/paranmr:release:v0.3.0",
                title="Mephistos-ML/paranmr release v0.3.0",
                url="https://gitlab.com/Mephistos-ML/paranmr/-/releases/v0.3.0",
                published_at=datetime(2026, 7, 18, 10, 15, tzinfo=UTC),
                raw_text="PCS fitting improvements.",
                payload={
                    "repo": "Mephistos-ML/paranmr",
                    "tag_name": "v0.3.0",
                },
            )
        ]

    monkeypatch.setattr(gitlab_monitor, "load_repo_activity", fake_load_repo_activity)

    signals = gitlab_monitor.load_gitlab_signals_for_profile(
        SubscriptionQueryProfile(
            subscription_id="sub_pnmr",
            topic_description="Paramagnetic NMR",
            query_terms=("paramagnetic nmr",),
        ),
    )

    assert len(signals) == 1
    assert called == [("Mephistos-ML/paranmr", datetime(2026, 7, 18, 10, 0, tzinfo=UTC))]


def test_load_live_gitlab_signals_uses_repository_checkpoint_when_present(
    monkeypatch,
) -> None:
    repository = Repository(
        repository_id="gitlab:repo:Mephistos-ML/paranmr",
        source="gitlab",
        full_name="Mephistos-ML/paranmr",
        url="https://gitlab.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "load_watched_gitlab_repositories",
        lambda subscription_id: (repository,),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "resolve_release_checkpoint",
        lambda subscription_id, repository, baseline_started_after: datetime(
            2026, 7, 18, 9, 30, tzinfo=UTC
        ),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "build_release_checkpoint",
        lambda subscription_id, repository, latest_published_at, fallback_started_after: RepositoryCheckpoint(
            subscription_id=subscription_id,
            repository_id=repository.repository_id,
            source="gitlab",
            checkpoint_key=gitlab_state.REPOSITORY_RELEASE_CHECKPOINT_KEY,
            checkpoint_value="2026-07-18T09:30:00+00:00",
            updated_at=datetime(2026, 7, 18, 9, 31, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(
        gitlab_monitor,
        "upsert_repository_checkpoints",
        lambda checkpoints: None,
    )
    called: list[datetime | None] = []

    def fake_load_repo_activity(repo_full_name: str, *, started_after):
        called.append(started_after)
        return []

    monkeypatch.setattr(gitlab_monitor, "load_repo_activity", fake_load_repo_activity)

    gitlab_monitor.load_gitlab_signals_for_profile(
        SubscriptionQueryProfile(
            subscription_id="sub_pnmr",
            topic_description="Paramagnetic NMR",
            query_terms=("paramagnetic nmr",),
        ),
    )

    assert called == [datetime(2026, 7, 18, 9, 30, tzinfo=UTC)]
