"""Control routes for starting and stopping scans."""

from __future__ import annotations

from app.services.scan_service import (
    get_status_payload,
    start_monitoring,
    stop_monitoring,
)


def start_scan_response() -> dict[str, object]:
    """Start monitoring and return the refreshed status payload."""

    start_monitoring()
    return get_status_payload()


def stop_scan_response() -> dict[str, object]:
    """Stop monitoring and return the refreshed status payload."""

    stop_monitoring()
    return get_status_payload()
