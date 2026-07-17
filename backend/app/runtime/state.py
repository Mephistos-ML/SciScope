"""Runtime state for the local SciScope backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import threading


@dataclass
class RuntimeState:
    """Mutable in-memory runtime state for scan results and loop status."""

    signals: dict[str, object] = field(default_factory=dict)
    monitoring_started_at: datetime | None = None
    last_scan_at: datetime | None = None
    last_scan_error: str | None = None
    auto_scan_started: bool = False
    auto_scan_stop_event: threading.Event = field(default_factory=threading.Event)
    auto_scan_thread: threading.Thread | None = None
    scan_lock: threading.Lock = field(default_factory=threading.Lock)


STATE = RuntimeState()
