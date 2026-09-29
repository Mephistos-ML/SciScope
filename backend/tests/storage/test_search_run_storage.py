"""Tests for durable Explore search run persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    claim_next_search_run_operation,
    count_search_run_provider_outcomes,
    count_search_run_ranking_candidates,
    count_search_run_stages,
    get_search_run,
    get_search_run_report,
    record_search_run_provider_outcomes,
    record_search_run_ranking_candidates,
    record_search_run_stage,
    release_search_run_operation_lease,
    renew_search_run_operation_lease,
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
        planner_reasoning_effort="low",
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
        status="rate_limited",
        candidate_count=7,
        duration_ms=420,
        retry_after_seconds=120,
        error_code="rate_limited",
        error_message="GitHub repository search is rate-limited right now.",
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
    assert stored.planner_reasoning_effort == run.planner_reasoning_effort
    assert stored.ranking_policy_version == run.ranking_policy_version
    assert stored.backend_revision == run.backend_revision
    assert count_search_run_stages(run.run_id, database_url=database_url) == 1
    assert count_search_run_provider_outcomes(run.run_id, database_url=database_url) == 1
    assert count_search_run_ranking_candidates(run.run_id, database_url=database_url) == 1
    report = get_search_run_report(run.run_id, database_url=database_url)
    assert report is not None
    assert report["run"]["runId"] == run.run_id
    assert report["run"]["plannerReasoningEffort"] == "low"
    assert report["stages"][0]["timings"]["stage_wall_time"] == 820
    assert report["providerOutcomes"][0]["source"] == "github"
    assert report["providerOutcomes"][0]["retryAfterSeconds"] == 120
    assert report["providerOutcomes"][0]["errorMessage"] == (
        "GitHub repository search is rate-limited right now."
    )
    assert report["rankingSnapshots"][0]["repositoryId"] == "github:repo:science/example"


def test_search_run_report_projects_run_failure_fields(tmp_path) -> None:
    database_url = build_test_database_url(tmp_path / "failed-search-run.sqlite3")
    migrate_test_database(database_url)
    failed_at = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    run = SearchRun(
        run_id="run_failed",
        owner_user_id=None,
        topic_description="Paramagnetic NMR fitting",
        topic_hash="topic_hash",
        status="failed",
        planner_mode="openai",
        planner_model="gpt-5",
        planner_reasoning_effort="low",
        ranking_policy_version="heuristic-v1",
        backend_revision="abc123",
        created_at=failed_at,
        completed_at=failed_at,
        error_code="search_failed",
        error_message="Repository search is temporarily unavailable across all providers.",
    )
    create_search_run(run, database_url=database_url)

    report = get_search_run_report(run.run_id, database_url=database_url)

    assert report is not None
    assert report["run"]["errorCode"] == "search_failed"
    assert report["run"]["errorMessage"] == (
        "Repository search is temporarily unavailable across all providers."
    )


def test_search_run_operation_lease_allows_one_worker_and_recovers_after_expiry(
    tmp_path,
) -> None:
    database_url = build_test_database_url(tmp_path / "search-run-lease.sqlite3")
    migrate_test_database(database_url)
    now = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    run = SearchRun(
        run_id="run_lease",
        owner_user_id=None,
        topic_description="topic",
        topic_hash="topic_hash",
        status="queued",
        planner_mode="bootstrap",
        planner_model=None,
        planner_reasoning_effort=None,
        ranking_policy_version="heuristic-v1",
        backend_revision="unknown",
        created_at=now,
    )
    operation = SearchRunOperation(
        operation_id="operation_lease",
        run_id=run.run_id,
        kind="initial",
        status="queued",
        queued_at=now,
    )
    create_search_run(run, database_url=database_url)
    create_search_run_operation(operation, database_url=database_url)

    first = claim_next_search_run_operation(
        holder_id="worker_one",
        now=now,
        lease_expires_at=now + timedelta(minutes=5),
        database_url=database_url,
    )
    second = claim_next_search_run_operation(
        holder_id="worker_two",
        now=now + timedelta(minutes=1),
        lease_expires_at=now + timedelta(minutes=6),
        database_url=database_url,
    )

    assert first is not None
    assert first.lease_holder_id == "worker_one"
    assert second is None
    assert renew_search_run_operation_lease(
        operation.operation_id,
        holder_id="worker_one",
        lease_expires_at=now + timedelta(minutes=10),
        database_url=database_url,
    )
    release_search_run_operation_lease(
        operation.operation_id,
        holder_id="worker_one",
        database_url=database_url,
    )
    reclaimed = claim_next_search_run_operation(
        holder_id="worker_two",
        now=now + timedelta(minutes=11),
        lease_expires_at=now + timedelta(minutes=16),
        database_url=database_url,
    )

    assert reclaimed is not None
    assert reclaimed.lease_holder_id == "worker_two"
