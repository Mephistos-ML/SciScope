"""Tests for manual labels on immutable ranking snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.search_run import SearchRun
from app.services.search.ranking_labels import save_search_run_ranking_labels


def test_save_search_run_ranking_labels_targets_latest_snapshot(monkeypatch) -> None:
    now = datetime(2026, 9, 28, tzinfo=UTC)
    stored: list[object] = []
    monkeypatch.setattr(
        "app.services.search.ranking_labels.get_search_run",
        lambda *_args, **_kwargs: SearchRun(
            run_id="run_1",
            owner_user_id="user_1",
            topic_description="topic",
            topic_hash="hash",
            status="completed",
            planner_mode="heuristic",
            planner_model=None,
            planner_reasoning_effort=None,
            ranking_policy_version="heuristic-v1",
            backend_revision="unknown",
            created_at=now,
        ),
    )
    monkeypatch.setattr(
        "app.services.search.ranking_labels.count_search_run_stages",
        lambda *_args, **_kwargs: 2,
    )
    monkeypatch.setattr(
        "app.services.search.ranking_labels.list_search_run_ranking_repository_ids",
        lambda *_args, **_kwargs: {"github:repo:science/example"},
    )
    monkeypatch.setattr(
        "app.services.search.ranking_labels.upsert_search_run_ranking_labels",
        lambda labels, **_kwargs: stored.extend(labels),
    )

    result = save_search_run_ranking_labels(
        user_id="user_1",
        run_id="run_1",
        labels={"github:repo:science/example": 2},
        database_url="sqlite://",
    )

    assert result == {"runId": "run_1", "stageNumber": 2, "labelledCount": 1}
    assert stored[0].stage_number == 2
    assert stored[0].label == 2
