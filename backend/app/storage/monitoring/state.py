"""Persistence operations for stateless monitoring job coordination."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.records import MonitoringJobLeaseRecordModel, MonitoringRunRecordModel
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
    with session_scope(database_url) as session:
        lease = session.get(MonitoringJobLeaseRecordModel, job_name)
        if lease is not None and lease.lease_expires_at > now and lease.holder_id != holder_id:
            return False
        if lease is None:
            session.add(
                MonitoringJobLeaseRecordModel(
                    job_name=job_name,
                    holder_id=holder_id,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                )
            )
        else:
            lease.holder_id = holder_id
            lease.lease_expires_at = now + timedelta(seconds=lease_seconds)
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
