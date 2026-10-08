"""Database-backed worker for durable Explore search operations."""

from __future__ import annotations

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
from app.composition.repositories import build_repository_adapters
from app.composition.search import build_explore_dependencies
from app.services.search.explore.dependencies import ExploreDependencies
from app.models.search_run import SearchRunOperation
from app.services.search.explore.jobs import execute_search_run_operation
from app.storage.search_runs import (
    SearchRunLeaseLostError,
    claim_next_search_run_operation,
    release_search_run_operation_lease,
    renew_search_run_operation_lease,
)

logger = logging.getLogger(__name__)


def process_next_search_run_operation(
    *,
    worker_id: str,
    dependencies: ExploreDependencies,
    database_url: str,
    lease_seconds: int = SEARCH_RUN_WORKER_LEASE_SECONDS,
) -> bool:
    """Claim and execute at most one operation; return whether work was found."""

    operation = claim_next_search_run_operation(
        holder_id=worker_id,
        lease_seconds=lease_seconds,
        database_url=database_url,
    )
    if operation is None:
        return False

    stop_heartbeat = Event()
    lease_lost = Event()
    heartbeat = Thread(
        target=_renew_lease_until_finished,
        kwargs={
            "operation": operation,
            "lease_lost": lease_lost,
            "database_url": database_url,
            "lease_seconds": lease_seconds,
            "stop": stop_heartbeat,
        },
        daemon=True,
    )

    def ensure_lease() -> None:
        if lease_lost.is_set():
            raise SearchRunLeaseLostError("Heartbeat could not confirm operation ownership.")

    heartbeat.start()
    try:
        execute_search_run_operation(
            operation,
            dependencies=dependencies,
            ensure_lease=ensure_lease,
            database_url=database_url,
        )
    except SearchRunLeaseLostError:
        logger.warning("Discarded search attempt after lease loss: %s", operation.operation_id)
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=1)
        release_search_run_operation_lease(
            operation,
            database_url=database_url,
        )
    return True


def run_search_run_worker(*, database_url: str = DATABASE_URL) -> None:
    """Continuously process database-backed Explore operations."""

    configure_logging()
    dependencies = build_explore_dependencies(repositories=build_repository_adapters())
    worker_id = _build_worker_id()
    logger.info("Explore search worker started: %s", worker_id)
    while True:
        processed = process_next_search_run_operation(
            worker_id=worker_id,
            dependencies=dependencies,
            database_url=database_url,
        )
        if not processed:
            sleep(SEARCH_RUN_WORKER_POLL_SECONDS)


def _renew_lease_until_finished(
    *,
    operation: SearchRunOperation,
    lease_lost: Event,
    database_url: str,
    lease_seconds: int,
    stop: Event,
) -> None:
    interval_seconds = lease_seconds / 3
    while not stop.wait(interval_seconds):
        try:
            renewed = renew_search_run_operation_lease(
                operation, lease_seconds=lease_seconds, database_url=database_url,
            )
        except Exception:
            lease_lost.set()
            logger.exception("Could not renew search operation lease: %s", operation.operation_id)
            return
        if not renewed:
            lease_lost.set()
            logger.warning("Explore search worker lost operation lease: %s", operation.operation_id)
            return


def _build_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}"


if __name__ == "__main__":
    run_search_run_worker()
