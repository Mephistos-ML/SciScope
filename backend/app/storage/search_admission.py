"""Persistence for atomic search admission and expansion scheduling."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.records.explore import (
    ExploreAccessLockRecordModel,
    ExploreSearchEventRecordModel,
)
from app.database.records.search_runs import SearchRunRecordModel, SearchRunOperationRecordModel
from app.database.session import session_scope
from app.models.explore_access import ExploreUsage
from app.models.search_run import SearchRun
from app.storage.search_runs import map_search_run_record


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ExploreAdmissionStore:
    """Usage, run state, and scheduling within one locked admission transaction."""

    def __init__(self, session: Session):
        self._session = session

    def read_usage(self, *, subject_type: str, subject_key: str, since: datetime) -> ExploreUsage:
        events = ExploreSearchEventRecordModel
        allowed = events.outcome == "allowed"
        actor = (events.subject_type == subject_type) & (events.subject_key == subject_key)
        window = events.created_at >= _ensure_utc(since)
        global_count = self._session.scalar(select(func.count()).select_from(events).where(allowed, window))
        actor_count = self._session.scalar(select(func.count()).select_from(events).where(allowed, window, actor))
        last = self._session.scalar(select(func.max(events.created_at)).where(allowed, actor))
        first = self._session.scalar(select(func.min(events.created_at)).where(allowed, window, actor))
        return ExploreUsage(
            global_count=int(global_count or 0),
            actor_count=int(actor_count or 0),
            last_allowed_at=_ensure_utc(last) if last else None,
            first_allowed_at=_ensure_utc(first) if first else None,
        )

    def record_event(
        self, *, user_id: str | None, subject_type: str, subject_key: str,
        ip_hash: str | None, topic_hash: str, outcome: str, created_at: datetime,
        retry_after_seconds: int | None = None,
    ) -> None:
        self._session.add(ExploreSearchEventRecordModel(
            event_id=f"exp_{uuid4().hex[:20]}", user_id=user_id,
            subject_type=subject_type, subject_key=subject_key, ip_hash=ip_hash,
            topic_hash=topic_hash, outcome=outcome, created_at=created_at,
            retry_after_seconds=retry_after_seconds,
        ))

    def get_run(self, run_id: str) -> SearchRun | None:
        """Read and lock the run until admission commits or rolls back."""
        record = self._session.get(SearchRunRecordModel, run_id, with_for_update=True)
        return map_search_run_record(record) if record is not None else None

    def schedule_expansion(self, *, run_id: str, operation_id: str, queued_at: datetime) -> None:
        """Persist an expansion and its running state in this transaction."""
        self._session.add(SearchRunOperationRecordModel(
            operation_id=operation_id, run_id=run_id, kind="expansion",
            status="queued", queued_at=queued_at,
        ))
        self._session.execute(update(SearchRunRecordModel).where(
            SearchRunRecordModel.run_id == run_id,
        ).values(status="running", partial=False, error_code=None, error_message=None))


@contextmanager
def explore_admission_transaction(*, database_url: str) -> Iterator[ExploreAdmissionStore]:
    """Serialize admission reads and writes with a database row lock."""
    with session_scope(database_url) as session:
        result = session.execute(update(ExploreAccessLockRecordModel).where(
            ExploreAccessLockRecordModel.lock_id == 1,
        ).values(lock_id=1))
        if result.rowcount != 1:
            raise RuntimeError("Search admission lock is missing; apply database migrations.")
        yield ExploreAdmissionStore(session)
