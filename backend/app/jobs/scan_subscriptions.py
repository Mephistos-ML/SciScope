"""Own one monitoring invocation and its renewable database lease."""

import logging
from collections.abc import Callable
from threading import Event, Thread
from uuid import uuid4

from app.config import DATABASE_URL
from app.composition.repositories import build_repository_adapters
from app.models.monitoring import MonitoringLease, MonitoringLeaseLostError
from app.services.monitoring.capabilities import RepositoryMonitor
from app.services.monitoring.scan import scan_repository_subscriptions
from app.storage.monitoring.state import (
    acquire_monitoring_job_lease,
    release_monitoring_job_lease,
    renew_monitoring_job_lease,
)

JOB_NAME = "repository-monitoring-scan"
logger = logging.getLogger(__name__)


def run_repository_monitoring_scan(
    *,
    resolve_monitor: Callable[[str], RepositoryMonitor | None],
    database_url: str,
    lease_seconds: int = 1800,
) -> None:
    lease = acquire_monitoring_job_lease(
        JOB_NAME,
        str(uuid4()),
        database_url=database_url,
        lease_seconds=lease_seconds,
    )
    if lease is None:
        return
    stop = Event()
    lost = Event()
    heartbeat = Thread(
        target=_renew_until_finished,
        kwargs={
            "lease": lease,
            "stop": stop,
            "lost": lost,
            "database_url": database_url,
            "lease_seconds": lease_seconds,
        },
        daemon=True,
    )

    def ensure_lease():
        if lost.is_set():
            raise MonitoringLeaseLostError(
                "Heartbeat could not confirm monitoring ownership."
            )

    try:
        heartbeat.start()
        scan_repository_subscriptions(
            resolve_monitor=resolve_monitor,
            lease=lease,
            ensure_lease=ensure_lease,
            database_url=database_url,
        )
    except MonitoringLeaseLostError:
        logger.warning(
            "Discarded monitoring attempt after lease loss: %s", lease.holder_id
        )
    finally:
        stop.set()
        if heartbeat.ident is not None:
            heartbeat.join(timeout=1)
        release_monitoring_job_lease(lease, database_url=database_url)


def _renew_until_finished(
    *,
    lease: MonitoringLease,
    stop: Event,
    lost: Event,
    database_url: str,
    lease_seconds: int,
) -> None:
    while not stop.wait(lease_seconds / 3):
        try:
            if renew_monitoring_job_lease(
                lease, database_url=database_url, lease_seconds=lease_seconds
            ):
                continue
        except Exception:
            logger.exception("Could not renew monitoring lease: %s", lease.holder_id)
        lost.set()
        return


def main() -> None:
    run_repository_monitoring_scan(
        resolve_monitor=build_repository_adapters().monitors.get,
        database_url=DATABASE_URL,
    )


if __name__ == "__main__":
    main()
