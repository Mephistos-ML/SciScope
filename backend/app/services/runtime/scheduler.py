"""Background scheduling policy for the monitoring runtime."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import MONITORING_INTERVAL_SECONDS, POLLING_FREQUENCY_SECONDS
from app.runtime.state import STATE
from app.services.runtime.cycle import run_scan_cycle_unlocked


def run_auto_scan_loop(*, database_url: str) -> None:
    stop_event = STATE.auto_scan_stop_event
    while not stop_event.wait(POLLING_FREQUENCY_SECONDS):
        with STATE.scan_lock:
            if should_run_monitoring():
                run_scan_cycle_unlocked(database_url=database_url)


def should_run_monitoring() -> bool:
    """Return whether the next source monitoring cycle is due."""

    if STATE.last_scan_at is None:
        return True

    return datetime.now(UTC) - STATE.last_scan_at >= timedelta(
        seconds=MONITORING_INTERVAL_SECONDS
    )
