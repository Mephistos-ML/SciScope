"""Runtime state for the local SciScope backend."""

from __future__ import annotations

from dataclasses import dataclass, field
import threading


@dataclass
class RuntimeState:
    """Mutable in-memory state for short-lived Explore search jobs."""

    explore_search_jobs: dict[str, dict[str, object]] = field(default_factory=dict)
    explore_search_jobs_lock: threading.Lock = field(default_factory=threading.Lock)


STATE = RuntimeState()
