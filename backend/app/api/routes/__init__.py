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
from app.config import CORS_ORIGINS


def application(environ: dict, start_response: Callable) -> list[bytes]:
    """Dispatch HTTP requests for the backend API."""

    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    cors_headers = _build_cors_headers(environ)

    if method == "OPTIONS":
        return _empty_response(start_response, "204 No Content", cors_headers)

    if method == "GET" and path == "/":
        return _json_response(start_response, get_root_payload(), extra_headers=cors_headers)

    if method == "POST" and path == "/api/start":
        return _json_response(start_response, start_scan_response(), extra_headers=cors_headers)

    if method == "POST" and path == "/api/stop":
        return _json_response(start_response, stop_scan_response(), extra_headers=cors_headers)

    if method == "GET" and path == "/api/me":
        return _json_response(start_response, get_me_response(), extra_headers=cors_headers)

    if method == "POST" and path == "/api/auth/dev-login":
        return _json_response(start_response, dev_login_response(), extra_headers=cors_headers)

    if method == "POST" and path == "/api/logout":
        return _json_response(start_response, logout_response(), extra_headers=cors_headers)

    if method == "POST" and path == "/api/explore/search":
        return _json_response(
            start_response,
            search_explore_response(_read_json_body(environ)),
            extra_headers=cors_headers,
        )

    if method == "GET" and path == "/api/subscriptions":
        payload = get_subscription_list_response()
        if payload is None:
            return _json_response(
                start_response,
                {"error": "Authentication required"},
                "401 Unauthorized",
                extra_headers=cors_headers,
            )
        return _json_response(start_response, payload, extra_headers=cors_headers)

    if method == "POST" and path == "/api/subscriptions":
        payload = create_subscription_response(_read_json_body(environ))
        if payload is None:
            return _json_response(
                start_response,
                {"error": "Authentication required"},
                "401 Unauthorized",
                extra_headers=cors_headers,
            )
        return _json_response(
            start_response,
            payload,
            "201 Created",
            extra_headers=cors_headers,
        )

    if method == "DELETE" and path.startswith("/api/subscriptions/"):
        subscription_id = path.removeprefix("/api/subscriptions/").strip("/")
        deleted = delete_subscription_response(subscription_id)
        if deleted is None:
            return _json_response(
                start_response,
                {"error": "Authentication required"},
                "401 Unauthorized",
                extra_headers=cors_headers,
            )
        if not deleted:
            return _json_response(
                start_response,
                {"error": "Subscription not found"},
                "404 Not Found",
                extra_headers=cors_headers,
            )
        return _json_response(start_response, {"deleted": True}, extra_headers=cors_headers)

    if method == "GET" and path == "/api/status":
        return _json_response(start_response, get_status_response(), extra_headers=cors_headers)

    if method == "GET" and path == "/api/signals":
        return _json_response(
            start_response,
            get_signal_list_response(),
            extra_headers=cors_headers,
        )

    if method == "GET" and path.startswith("/api/signals/"):
        item_id = path.removeprefix("/api/signals/")
        payload = get_signal_detail_response(item_id)
        if payload is None:
            return _json_response(
                start_response,
                {"error": "Signal not found"},
                "404 Not Found",
                extra_headers=cors_headers,
            )
        return _json_response(start_response, payload, extra_headers=cors_headers)

    if method == "GET" and path == "/health":
        return _plain_response(start_response, get_health_payload(), extra_headers=cors_headers)

    return _not_found_response(start_response, extra_headers=cors_headers)


def _plain_response(
    start_response: Callable,
    body: str,
    *,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    data = body.encode("utf-8")
    start_response(
        "200 OK",
        _merge_headers(
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(data))),
            ],
            extra_headers,
        ),
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
    *,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(
        status,
        _merge_headers(
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
            extra_headers,
        ),
    )
    return [body]


def _not_found_response(
    start_response: Callable,
    *,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    start_response(
        "404 Not Found",
        _merge_headers([("Content-Type", "text/plain; charset=utf-8")], extra_headers),
    )
    return [b"Not Found"]


def _empty_response(
    start_response: Callable,
    status: str,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    start_response(status, _merge_headers([("Content-Length", "0")], extra_headers))
    return [b""]


def _build_cors_headers(environ: dict) -> list[tuple[str, str]]:
    origin = str(environ.get("HTTP_ORIGIN") or "").strip()
    if not origin or origin not in CORS_ORIGINS:
        return []

    return [
        ("Access-Control-Allow-Origin", origin),
        ("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
        ("Access-Control-Max-Age", "86400"),
        ("Vary", "Origin"),
    ]


def _merge_headers(
    base_headers: list[tuple[str, str]],
    extra_headers: list[tuple[str, str]] | None,
) -> list[tuple[str, str]]:
    if not extra_headers:
        return base_headers
    return [*base_headers, *extra_headers]
