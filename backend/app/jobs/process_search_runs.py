"""Database-backed worker for durable Explore search operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import os
import socket
from threading import Event, Thread
from time import sleep
from uuid import uuid4

from app.config import (
    DATABASE_URL,
    SEARCH_RUN_WORKER_LEASE_SECONDS,
    SEARCH_RUN_WORKER_POLL_SECONDS,
)
from app.logging import configure_logging
from app.services.search.explore.jobs import execute_search_run_operation
from app.storage.search_runs import (
    claim_next_search_run_operation,
    release_search_run_operation_lease,
    renew_search_run_operation_lease,
)

logger = logging.getLogger(__name__)


def process_next_search_run_operation(
    *,
    worker_id: str,
    database_url: str,
    lease_seconds: int = SEARCH_RUN_WORKER_LEASE_SECONDS,
) -> bool:
    """Claim and execute at most one operation; return whether work was found."""

    claimed_at = datetime.now(UTC)
    operation = claim_next_search_run_operation(
        holder_id=worker_id,
        now=claimed_at,
        lease_expires_at=claimed_at + timedelta(seconds=lease_seconds),
        database_url=database_url,
    )
    if operation is None:
        return False

    stop_heartbeat = Event()
    heartbeat = Thread(
        target=_renew_lease_until_finished,
        kwargs={
            "operation_id": operation.operation_id,
            "worker_id": worker_id,
            "database_url": database_url,
            "lease_seconds": lease_seconds,
            "stop": stop_heartbeat,
        },
        daemon=True,
    )
    heartbeat.start()
    try:
        execute_search_run_operation(operation, database_url=database_url)
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=1)
        release_search_run_operation_lease(
            operation.operation_id,
            holder_id=worker_id,
            database_url=database_url,
        )
    return True


def run_search_run_worker(*, database_url: str = DATABASE_URL) -> None:
    """Continuously process database-backed Explore operations."""

    configure_logging()
    worker_id = _build_worker_id()
    logger.info("Explore search worker started: %s", worker_id)
    while True:
        processed = process_next_search_run_operation(
            worker_id=worker_id,
            database_url=database_url,
        )
        if not processed:
            sleep(SEARCH_RUN_WORKER_POLL_SECONDS)


def _renew_lease_until_finished(
    *,
    operation_id: str,
    worker_id: str,
    database_url: str,
    lease_seconds: int,
    stop: Event,
) -> None:
    interval_seconds = max(1, lease_seconds // 3)
    while not stop.wait(interval_seconds):
        renewed = renew_search_run_operation_lease(
            operation_id,
            holder_id=worker_id,
            lease_expires_at=(
                datetime.now(UTC) + timedelta(seconds=lease_seconds)
            ),
            database_url=database_url,
        )
        if not renewed:
            logger.error("Explore search worker lost operation lease: %s", operation_id)
            return


def _build_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}"


if __name__ == "__main__":
    run_search_run_worker()
