"""Persistence operations for stateless monitoring job coordination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError

from app.database.records import (
    MonitoringJobLeaseRecordModel,
    MonitoringRunRecordModel,
    RepositoryMonitoringCheckRecordModel,
    RepositoryMonitoringCursorRecordModel,
)
from app.models.monitoring import RepositoryMonitoringCheck
from app.database.session import session_scope
from app.models.monitoring import MonitoringRun


def acquire_monitoring_job_lease(
    job_name: str,
    holder_id: str,
    *,
    database_url: str,
    lease_seconds: int = 1800,
) -> bool:
    """Acquire one expired-or-free job lease atomically."""

    now = datetime.now(UTC)
    lease_expires_at = now + timedelta(seconds=lease_seconds)
    with session_scope(database_url) as session:
        updated = session.execute(
            update(MonitoringJobLeaseRecordModel)
            .where(MonitoringJobLeaseRecordModel.job_name == job_name)
            .where(
                or_(
                    MonitoringJobLeaseRecordModel.lease_expires_at <= now,
                    MonitoringJobLeaseRecordModel.holder_id == holder_id,
                )
            )
            .values(holder_id=holder_id, lease_expires_at=lease_expires_at)
        )
        if updated.rowcount:
            return True

        try:
            with session.begin_nested():
                session.add(
                    MonitoringJobLeaseRecordModel(
                        job_name=job_name,
                        holder_id=holder_id,
                        lease_expires_at=lease_expires_at,
                    )
                )
                session.flush()
        except IntegrityError:
            return False
    return True


def release_monitoring_job_lease(job_name: str, holder_id: str, *, database_url: str) -> None:
    """Release a lease only when held by this job run."""

    with session_scope(database_url) as session:
        lease = session.get(MonitoringJobLeaseRecordModel, job_name)
        if lease is not None and lease.holder_id == holder_id:
            session.delete(lease)


def create_monitoring_run(run: MonitoringRun, *, database_url: str) -> None:
    """Persist a monitoring run at its start."""

    with session_scope(database_url) as session:
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
    database_url: str,
) -> None:
    """Finalize one persisted monitoring run."""

    with session_scope(database_url) as session:
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

    with session_scope(database_url) as session:
        rows = session.query(RepositoryMonitoringCursorRecordModel).filter_by(
            repository_id=repository_id
        ).all()
    return {row.checkpoint_key: row.checkpoint_value for row in rows}


def upsert_repository_monitoring_cursors(
    repository_id: str,
    values: dict[str, str],
    *,
    database_url: str,
) -> None:
    """Advance named repository-level cursors after a successful scan."""

    now = datetime.now(UTC)
    with session_scope(database_url) as session:
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
    database_url: str,
) -> None:
    """Persist one repository's sanitized monitoring outcome."""

    with session_scope(database_url) as session:
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
