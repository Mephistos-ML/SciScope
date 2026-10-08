"""Synchronize database contention on observed PostgreSQL state."""

from time import monotonic

import pytest
from sqlalchemy import text


def wait_until_blocked(connection, query_prefix):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        waiting = connection.scalar(text("""
            SELECT count(*) FROM pg_stat_activity
            WHERE datname = current_database() AND wait_event_type = 'Lock'
              AND query LIKE :prefix AND pid <> pg_backend_pid()
        """), {"prefix": query_prefix + "%"})
        if waiting:
            return
        # Server-side bounded yield; correctness depends on observed locking, not sleep duration.
        connection.execute(text("SELECT pg_sleep(0.01)"))
    pytest.fail("The contender never reached the expected PostgreSQL lock wait.")
