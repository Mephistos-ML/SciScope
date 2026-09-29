"""Tests for durable Explore search run persistence."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.search_run import (
    SearchRun,
    SearchRunOperation,
    SearchRunProviderOutcome,
    SearchRankingCandidateReport,
    SearchRunStage,
)
from app.storage.search_runs import (
    create_search_run,
    create_search_run_operation,
    count_search_run_provider_outcomes,
    count_search_run_ranking_candidates,
    count_search_run_stages,
    get_search_run,
    get_search_run_report,
    record_search_run_provider_outcomes,
    record_search_run_ranking_candidates,
    record_search_run_stage,
)
from tests.conftest import build_test_database_url, migrate_test_database


def test_search_run_storage_persists_execution_facts(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "search-runs.sqlite3")
    migrate_test_database(database_url)
    started_at = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    run = SearchRun(
        run_id="run_1",
        owner_user_id=None,
        topic_description="Paramagnetic NMR fitting",
        topic_hash="topic_hash",
        status="running",
        planner_mode="openai",
        planner_model="gpt-5",
        ranking_policy_version="heuristic-v1",
        backend_revision="abc123",
        created_at=started_at,
        started_at=started_at,
    )
    operation = SearchRunOperation(
        operation_id="operation_1",
        run_id=run.run_id,
        kind="initial",
        status="running",
        queued_at=started_at,
        started_at=started_at,
    )
    stage = SearchRunStage(
        run_id=run.run_id,
        operation_id=operation.operation_id,
        stage_number=1,
        status="completed",
        executed_query_ids=("q1",),
        retrieved_candidate_count=7,
        admitted_candidate_count=4,
        visible_candidate_count=3,
        timings={"stage_wall_time": 820},
        started_at=started_at,
        completed_at=started_at,
    )
    outcome = SearchRunProviderOutcome(
        outcome_id="outcome_1",
        run_id=run.run_id,
        operation_id=operation.operation_id,
        stage_number=stage.stage_number,
        source="github",
        channel="repository_search",
        query_id="q1",
        attempt=1,
        status="ok",
        candidate_count=7,
        duration_ms=420,
    )

    create_search_run(run, database_url=database_url)
    create_search_run_operation(operation, database_url=database_url)
    record_search_run_stage(stage, database_url=database_url)
    record_search_run_provider_outcomes((outcome,), database_url=database_url)
    record_search_run_ranking_candidates(
        run.run_id,
        stage.stage_number,
        (
            SearchRankingCandidateReport(
                repository_id="github:repo:science/example",
                repository_source="github",
                rank_position=1,
                final_score=87.5,
                candidate_facts={"full_name": "science/example"},
                retrieval_facts={"origins": ["provider"]},
                admission_facts={"decision": "keep"},
                ranking_features={"hit_count": 2},
                score_breakdown={"corroboration_points": 10.0},
            ),
        ),
        database_url=database_url,
    )

    stored = get_search_run(run.run_id, database_url=database_url)

    assert stored is not None
    assert stored.run_id == run.run_id
    assert stored.owner_user_id == run.owner_user_id
    assert stored.topic_description == run.topic_description
    assert stored.topic_hash == run.topic_hash
    assert stored.status == run.status
    assert stored.planner_mode == run.planner_mode
    assert stored.planner_model == run.planner_model
    assert stored.ranking_policy_version == run.ranking_policy_version
    assert stored.backend_revision == run.backend_revision
    assert count_search_run_stages(run.run_id, database_url=database_url) == 1
    assert count_search_run_provider_outcomes(run.run_id, database_url=database_url) == 1
    assert count_search_run_ranking_candidates(run.run_id, database_url=database_url) == 1
    report = get_search_run_report(run.run_id, database_url=database_url)
    assert report is not None
    assert report["run"]["runId"] == run.run_id
    assert report["stages"][0]["timings"]["stage_wall_time"] == 820
    assert report["providerOutcomes"][0]["source"] == "github"
    assert report["rankingSnapshots"][0]["repositoryId"] == "github:repo:science/example"
