"""Lifecycle control for the monitoring runtime."""

from __future__ import annotations

from datetime import UTC, datetime
import threading

from app.config import DATABASE_URL
from app.runtime.state import STATE
from app.services.runtime.cycle import run_baseline_sync
from app.services.runtime.scheduler import run_auto_scan_loop


def start_monitoring(*, database_url: str = DATABASE_URL) -> None:
    """Start the scheduler and initialize repository monitoring baselines."""

    if not STATE.auto_scan_started:
        STATE.monitoring_started_at = datetime.now(UTC)
        STATE.auto_scan_stop_event = threading.Event()
        STATE.auto_scan_started = True
        STATE.auto_scan_thread = _build_auto_scan_thread(database_url=database_url)
        STATE.auto_scan_thread.start()
    elif STATE.monitoring_started_at is None:
        STATE.monitoring_started_at = datetime.now(UTC)

    run_baseline_sync(database_url=database_url)


def stop_monitoring(*, database_url: str = DATABASE_URL) -> None:
    """Stop the background auto-scan loop."""

    if not STATE.auto_scan_started:
        return

    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.set()
    STATE.auto_scan_thread = None


def _build_auto_scan_thread(*, database_url: str) -> threading.Thread:
    return threading.Thread(
        target=lambda: run_auto_scan_loop(database_url=database_url),
        name="sciscope-auto-scan",
        daemon=True,
    )
