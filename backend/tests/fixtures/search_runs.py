"""Seed durable run state without executing a new-search use case."""

from datetime import UTC, datetime
import hashlib
import secrets
from typing import Any
from uuid import uuid4

from app.database.records.search_runs import SearchRunRecordModel
from app.database.session import session_scope
from app.models.search_run import SearchRun, SearchRunOperation
from app.storage.search_runs import write_search_run, write_search_run_operation


def seed_search_run(
    *, topic_description: str, database_url: str, owner_user_id: str | None = None,
) -> dict[str, str]:
    """Return client credentials for a queued fixture with no admission history."""
    now = datetime.now(UTC)
    token = secrets.token_urlsafe(32) if owner_user_id is None else None
    run = SearchRun(
        run_id=uuid4().hex,
        owner_user_id=owner_user_id,
        topic_description=topic_description,
        topic_hash=hashlib.sha256(topic_description.encode()).hexdigest(),
        status="queued",
        planner_mode="bootstrap",
        planner_model=None,
        planner_reasoning_effort=None,
        ranking_policy_version="heuristic-v1",
        backend_revision="fixture",
        created_at=now,
        guest_access_token_hash=hashlib.sha256(token.encode()).hexdigest() if token else None,
    )
    with session_scope(database_url) as session:
        write_search_run(session, run)
        session.flush()
        write_search_run_operation(session, SearchRunOperation(
            uuid4().hex, run.run_id, "initial", "queued", now,
        ))
    credentials = {"runId": run.run_id}
    if token is not None:
        credentials["guestAccessToken"] = token
    return credentials


def set_search_run_state(
    run_id: str,
    *,
    status: str,
    partial: bool = False,
    error_code: str | None = None,
    error_message: str | None = None,
    response_payload: dict[str, Any] | None = None,
    execution_state: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    database_url: str,
) -> None:
    """Arrange a synthetic lifecycle state without executing a worker."""

    with session_scope(database_url) as session:
        record = session.get(SearchRunRecordModel, run_id)
        if record is None:
            return
        record.status = status
        record.partial = partial
        record.error_code = error_code
        record.error_message = error_message
        if response_payload is not None:
            record.response_payload_json = response_payload
        if execution_state is not None:
            record.execution_state_json = execution_state
        if started_at is not None:
            record.started_at = started_at
        if completed_at is not None:
            record.completed_at = completed_at
