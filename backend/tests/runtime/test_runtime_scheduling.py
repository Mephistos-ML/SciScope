"""Tests for repository-monitoring scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.runtime.state import STATE
from app.services import runtime


def test_should_run_monitoring_when_never_run() -> None:
    STATE.last_scan_at = None

    assert runtime._should_run_monitoring() is True


def test_should_run_monitoring_after_interval_elapsed() -> None:
    STATE.last_scan_at = datetime.now(UTC) - timedelta(hours=3)

    assert runtime._should_run_monitoring() is True


def test_should_not_run_monitoring_before_interval_elapsed() -> None:
    STATE.last_scan_at = datetime.now(UTC) - timedelta(minutes=30)

    assert runtime._should_run_monitoring() is False


def test_start_monitoring_runs_baseline_without_immediate_scan(
    monkeypatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(runtime, "run_baseline_sync", lambda: calls.append("baseline"))
    monkeypatch.setattr(runtime.threading, "Thread", _FakeThread)

    STATE.auto_scan_started = False
    STATE.auto_scan_thread = None
    STATE.monitoring_started_at = None

    runtime.start_monitoring()

    assert calls == ["baseline"]
    assert STATE.auto_scan_started is True

    runtime.stop_monitoring()


class _FakeThread:
    def __init__(self, *, target, name, daemon):
        self.target = target
        self.name = name
        self.daemon = daemon

    def start(self) -> None:
        return None
