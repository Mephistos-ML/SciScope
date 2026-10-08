"""Persistence operations for stateless monitoring job coordination."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from uuid import uuid4
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.records.monitoring import (
    MonitoringJobLeaseRecordModel,
    MonitoringRunRecordModel,
    RepositoryMonitoringCheckRecordModel,
    RepositoryMonitoringCursorRecordModel,
)
from app.storage.transaction import persistence_session
from app.models.feed import FeedEvent
from app.models.monitoring import (
    MonitoringRun,
    RepositoryMonitoringCheck,
    MonitoringLease,
    MonitoringLeaseLostError,
)
from app.models.repository import Repository
from app.database.session import database_now
from app.storage.repositories.repositories import write_repositories
from app.storage.feed.events import write_feed_events


def acquire_monitoring_job_lease(
    job_name: str,
    holder_id: str,
    *,
    database_url: str,
    lease_seconds: int = 1800,
) -> MonitoringLease | None:
    """Claim a free or expired lease with a fresh fencing credential."""
    if lease_seconds <= 0:
        raise ValueError("Lease duration must be positive.")
    lease = MonitoringLease(job_name, holder_id, uuid4().hex)
    with persistence_session(database_url) as session:
        locked = session.execute(
            update(MonitoringJobLeaseRecordModel)
            .where(
                MonitoringJobLeaseRecordModel.job_name == job_name,
            )
            .values(holder_id=MonitoringJobLeaseRecordModel.holder_id)
        )
        now = database_now(session)
        if locked.rowcount:
            record = session.get(MonitoringJobLeaseRecordModel, job_name)
            if record.lease_token is not None and _utc(record.lease_expires_at) > now:
                return None
            record.holder_id = holder_id
            record.lease_token = lease.token
            record.lease_expires_at = now + timedelta(seconds=lease_seconds)
        else:
            try:
                with session.begin_nested():
                    session.add(
                        MonitoringJobLeaseRecordModel(
                            job_name=job_name,
                            holder_id=holder_id,
                            lease_token=lease.token,
                            lease_expires_at=now + timedelta(seconds=lease_seconds),
                        )
                    )
                    session.flush()
            except IntegrityError:
                return None
    return lease


def _ownership(lease: MonitoringLease):
    return (
        MonitoringJobLeaseRecordModel.job_name == lease.job_name,
        MonitoringJobLeaseRecordModel.holder_id == lease.holder_id,
        MonitoringJobLeaseRecordModel.lease_token == lease.token,
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _require_live(record: MonitoringJobLeaseRecordModel, now: datetime) -> None:
    if _utc(record.lease_expires_at) <= now:
        raise MonitoringLeaseLostError("Monitoring lease expired.")


@contextmanager
def _owned_monitoring_session(
    lease: MonitoringLease, *, database_url: str
) -> Iterator[Session]:
    with persistence_session(database_url) as session:
        locked = session.execute(
            update(MonitoringJobLeaseRecordModel)
            .where(
                *_ownership(lease),
            )
            .values(lease_token=MonitoringJobLeaseRecordModel.lease_token)
        )
        if locked.rowcount != 1:
            raise MonitoringLeaseLostError("Monitoring lease was replaced or released.")
        record = session.get(MonitoringJobLeaseRecordModel, lease.job_name)
        _require_live(record, database_now(session))
        yield session
        session.flush()
        _require_live(record, database_now(session))


def renew_monitoring_job_lease(
    lease: MonitoringLease, *, database_url: str, lease_seconds: int = 1800
) -> bool:
    if lease_seconds <= 0:
        raise ValueError("Lease duration must be positive.")
    try:
        with _owned_monitoring_session(lease, database_url=database_url) as session:
            record = session.get(MonitoringJobLeaseRecordModel, lease.job_name)
            now = database_now(session)
            _require_live(record, now)
            record.lease_expires_at = now + timedelta(seconds=lease_seconds)
    except MonitoringLeaseLostError:
        return False
    return True


def release_monitoring_job_lease(lease: MonitoringLease, *, database_url: str) -> None:
    """Delete only the matching claim, in one conditional statement."""
    with persistence_session(database_url) as session:
        session.execute(delete(MonitoringJobLeaseRecordModel).where(*_ownership(lease)))


def create_monitoring_run(
    run: MonitoringRun, *, lease: MonitoringLease, database_url: str
) -> None:
    """Persist a monitoring run at its start."""

    if run.run_id != lease.holder_id:
        raise ValueError("Monitoring run does not match its lease.")
    with _owned_monitoring_session(lease, database_url=database_url) as session:
        session.add(
            MonitoringRunRecordModel(
                run_id=run.run_id,
                started_at=run.started_at,
                finished_at=run.finished_at,
                status=run.status,
                scanned_repository_count=run.scanned_repository_count,
                failed_repository_count=run.failed_repository_count,
                error_summary=run.error_summary,
            )
        )


def finish_monitoring_run(
    run_id: str,
    *,
    status: str,
    scanned_repository_count: int,
    failed_repository_count: int,
    error_summary: str | None,
    lease: MonitoringLease,
    database_url: str,
) -> None:
    """Finalize one persisted monitoring run."""

    if run_id != lease.holder_id:
        raise ValueError("Monitoring run does not match its lease.")
    with _owned_monitoring_session(lease, database_url=database_url) as session:
        run = session.get(MonitoringRunRecordModel, run_id)
        if run is None:
            return
        run.finished_at = datetime.now(UTC)
        run.status = status
        run.scanned_repository_count = scanned_repository_count
        run.failed_repository_count = failed_repository_count
        run.error_summary = error_summary


def get_repository_monitoring_cursors(
    repository_id: str,
    *,
    database_url: str,
) -> dict[str, str]:
    """Return all durable monitoring cursors for one repository."""

    with persistence_session(database_url) as session:
        rows = (
            session.query(RepositoryMonitoringCursorRecordModel)
            .filter_by(repository_id=repository_id)
            .all()
        )
    return {row.checkpoint_key: row.checkpoint_value for row in rows}


def persist_repository_monitoring_result(
    repository_id: str,
    events: Sequence[FeedEvent],
    checkpoint_updates: dict[str, str],
    *,
    refreshed_repository: Repository | None = None,
    lease: MonitoringLease,
    database_url: str,
) -> None:
    """Commit Feed events and completed-stream checkpoints atomically."""

    with _owned_monitoring_session(lease, database_url=database_url) as session:
        if refreshed_repository is not None:
            write_repositories(session, (refreshed_repository,))
        write_feed_events(session, events)
        _write_repository_monitoring_cursors(session, repository_id, checkpoint_updates)


def _write_repository_monitoring_cursors(
    session: Session,
    repository_id: str,
    values: dict[str, str],
) -> None:
    now = datetime.now(UTC)
    for checkpoint_key, checkpoint_value in values.items():
        row = session.get(
            RepositoryMonitoringCursorRecordModel,
            (repository_id, checkpoint_key),
        )
        if row is None:
            session.add(
                RepositoryMonitoringCursorRecordModel(
                    repository_id=repository_id,
                    checkpoint_key=checkpoint_key,
                    checkpoint_value=checkpoint_value,
                    updated_at=now,
                )
            )
        else:
            row.checkpoint_value = checkpoint_value
            row.updated_at = now


def record_repository_monitoring_check(
    check: RepositoryMonitoringCheck,
    *,
    run_id: str,
    lease: MonitoringLease,
    database_url: str,
) -> None:
    """Persist one repository's sanitized monitoring outcome."""

    if run_id != lease.holder_id:
        raise ValueError("Monitoring run does not match its lease.")
    with _owned_monitoring_session(lease, database_url=database_url) as session:
        session.add(
            RepositoryMonitoringCheckRecordModel(
                repository_id=check.repository_id,
                run_id=run_id,
                checked_at=check.checked_at,
                status=check.status,
                error_code=check.error_code,
                error_message=check.error_message,
            )
        )
