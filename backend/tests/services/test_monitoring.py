"""Tests for repository monitoring orchestration."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.conftest import build_test_database_url, migrate_test_database
from app.models.repository import Repository, RepositoryCheckpoint
from app.models.signal import Signal
from app.services.monitoring import repositories as monitoring_service
from app.storage.repositories import (
    get_repository_checkpoint,
    upsert_repository_checkpoints,
)


def test_sync_repository_baseline_persists_missing_checkpoint(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "monitoring.sqlite3")
    migrate_test_database(database_url)
    baseline_started_at = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)

    monitoring_service.sync_repository_baseline(
        "sub_monitoring",
        _build_repository(),
        baseline_started_at=baseline_started_at,
        database_url=database_url,
    )

    checkpoint = get_repository_checkpoint(
        "sub_monitoring",
        "github:repo:Mephistos-ML/paranmr",
        "latest_release_published_at",
        database_url=database_url,
    )

    assert checkpoint is not None
    assert checkpoint.checkpoint_value == baseline_started_at.isoformat()


def test_load_repository_signals_advances_checkpoint_from_latest_release(
    tmp_path,
    monkeypatch,
) -> None:
    database_url = build_test_database_url(tmp_path / "monitoring.sqlite3")
    migrate_test_database(database_url)
    started_after = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)
    published_at = datetime(2026, 8, 21, 11, 15, tzinfo=UTC)

    upsert_repository_checkpoints(
        (
            RepositoryCheckpoint(
                subscription_id="sub_monitoring",
                repository_id="github:repo:Mephistos-ML/paranmr",
                source="github",
                checkpoint_key="latest_release_published_at",
                checkpoint_value=started_after.isoformat(),
                updated_at=started_after,
            ),
        ),
        database_url=database_url,
    )

    def fake_load_repo_activity(
        repo_full_name: str,
        *,
        started_after: datetime | None,
    ) -> list[Signal]:
        assert repo_full_name == "Mephistos-ML/paranmr"
        assert started_after == datetime(2026, 8, 20, 9, 30, tzinfo=UTC)
        return [
            Signal(
                source="github",
                kind="release",
                item_id="Mephistos-ML/paranmr:release:v0.3.0",
                title="Mephistos-ML/paranmr release v0.3.0",
                url="https://github.com/Mephistos-ML/paranmr/releases/tag/v0.3.0",
                published_at=published_at,
                raw_text="Adds PCS fitting improvements.",
                payload={"repo": "Mephistos-ML/paranmr"},
            )
        ]

    monkeypatch.setattr(
        monitoring_service.github_source,
        "load_repo_activity",
        fake_load_repo_activity,
    )

    signals = monitoring_service.load_repository_signals(
        "sub_monitoring",
        _build_repository(),
        database_url=database_url,
    )

    checkpoint = get_repository_checkpoint(
        "sub_monitoring",
        "github:repo:Mephistos-ML/paranmr",
        "latest_release_published_at",
        database_url=database_url,
    )

    assert len(signals) == 1
    assert checkpoint is not None
    assert checkpoint.checkpoint_value == published_at.isoformat()


def _build_repository() -> Repository:
    return Repository(
        repository_id="github:repo:Mephistos-ML/paranmr",
        source="github",
        full_name="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        metadata={"repo": "Mephistos-ML/paranmr"},
    )
