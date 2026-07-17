"""WSGI API router for SciScope backend."""

from __future__ import annotations

import json
from typing import Callable

from app.api.routes.control import start_scan_response, stop_scan_response
from app.api.routes.dashboard import get_health_payload, get_root_payload
from app.api.routes.signals import (
    get_signal_detail_response,
    get_signal_list_response,
    get_status_response,
)


def application(environ: dict, start_response: Callable) -> list[bytes]:
    """Dispatch HTTP requests for the backend API."""

    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    if method == "GET" and path == "/":
        return _json_response(start_response, get_root_payload())

    if method == "POST" and path == "/api/start":
        return _json_response(start_response, start_scan_response())

    if method == "POST" and path == "/api/stop":
        return _json_response(start_response, stop_scan_response())

    if method == "GET" and path == "/api/status":
        return _json_response(start_response, get_status_response())

    if method == "GET" and path == "/api/signals":
        return _json_response(start_response, get_signal_list_response())

    if method == "GET" and path.startswith("/api/signals/"):
        item_id = path.removeprefix("/api/signals/")
        payload = get_signal_detail_response(item_id)
        if payload is None:
            return _json_response(
                start_response,
                {"error": "Signal not found"},
                "404 Not Found",
            )
        return _json_response(start_response, payload)

    if method == "GET" and path == "/health":
        return _plain_response(start_response, get_health_payload())

    return _not_found_response(start_response)


def _plain_response(start_response: Callable, body: str) -> list[bytes]:
    data = body.encode("utf-8")
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(data))),
        ],
    )
    return [data]


def _json_response(
    start_response: Callable,
    payload: dict[str, object],
    status: str = "200 OK",
) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def _not_found_response(start_response: Callable) -> list[bytes]:
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"Not Found"]
