"""Run one stateless repository monitoring scan."""

from __future__ import annotations

from app.config import DATABASE_URL
from app.services.monitoring.scan import run_repository_monitoring_scan


def main() -> None:
    """Execute one complete scan using the configured durable database."""

    run_repository_monitoring_scan(database_url=DATABASE_URL)


if __name__ == "__main__":
    main()
