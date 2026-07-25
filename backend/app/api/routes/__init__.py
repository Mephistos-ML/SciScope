"""WSGI API router for SciScope backend."""

from __future__ import annotations

import json
from typing import Callable

from app.api.routes.auth import dev_login_response, get_me_response, logout_response
from app.api.routes.control import start_scan_response, stop_scan_response
from app.api.routes.dashboard import get_health_payload, get_root_payload
from app.api.routes.explore import search_explore_response
from app.api.routes.signals import (
    get_signal_detail_response,
    get_signal_list_response,
    get_status_response,
)
from app.api.routes.subscriptions import (
    create_subscription_response,
    delete_subscription_response,
    get_subscription_list_response,
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

    if method == "GET" and path == "/api/me":
        return _json_response(start_response, get_me_response())

    if method == "POST" and path == "/api/auth/dev-login":
        return _json_response(start_response, dev_login_response())

    if method == "POST" and path == "/api/logout":
        return _json_response(start_response, logout_response())

    if method == "POST" and path == "/api/explore/search":
        return _json_response(start_response, search_explore_response(_read_json_body(environ)))

    if method == "GET" and path == "/api/subscriptions":
        payload = get_subscription_list_response()
        if payload is None:
            return _json_response(
                start_response,
                {"error": "Authentication required"},
                "401 Unauthorized",
            )
        return _json_response(start_response, payload)

    if method == "POST" and path == "/api/subscriptions":
        payload = create_subscription_response(_read_json_body(environ))
        if payload is None:
            return _json_response(
                start_response,
                {"error": "Authentication required"},
                "401 Unauthorized",
            )
        return _json_response(start_response, payload, "201 Created")

    if method == "DELETE" and path.startswith("/api/subscriptions/"):
        subscription_id = path.removeprefix("/api/subscriptions/").strip("/")
        deleted = delete_subscription_response(subscription_id)
        if deleted is None:
            return _json_response(
                start_response,
                {"error": "Authentication required"},
                "401 Unauthorized",
            )
        if not deleted:
            return _json_response(
                start_response,
                {"error": "Subscription not found"},
                "404 Not Found",
            )
        return _json_response(start_response, {"deleted": True})

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


def _read_json_body(environ: dict) -> dict[str, object]:
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    body = environ.get("wsgi.input")
    if content_length <= 0 or body is None:
        return {}

    payload = body.read(content_length)
    if not payload:
        return {}

    loaded = json.loads(payload.decode("utf-8"))
    if isinstance(loaded, dict):
        return loaded
    return {}


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
