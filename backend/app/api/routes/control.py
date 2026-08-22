"""Control routes for starting and stopping scans."""

from __future__ import annotations

from fastapi import Request

from app.services.runtime import (
    get_status_payload,
    start_monitoring,
    stop_monitoring,
)


def start_scan_response(request: Request) -> dict[str, object]:
    """Start monitoring and return the refreshed status payload."""

    start_monitoring(database_url=request.app.state.database_url)
    return get_status_payload(database_url=request.app.state.database_url)


def stop_scan_response(request: Request) -> dict[str, object]:
    """Stop monitoring and return the refreshed status payload."""

    stop_monitoring(database_url=request.app.state.database_url)
    return get_status_payload(database_url=request.app.state.database_url)
