"""Dashboard and health API routes."""

from __future__ import annotations


def get_root_payload() -> dict[str, object]:
    """Return a compact service description for the API root."""

    return {
        "service": "sciscope-api",
        "status": "ok",
        "endpoints": [
            "/api/me",
            "/api/logout",
            "/api/explore/search",
            "/api/status",
            "/api/signals",
            "/api/signals/{id}",
            "/api/subscriptions",
            "/api/subscriptions/{id}",
            "/api/start",
            "/api/stop",
            "/health",
            "/ready",
        ],
    }


def get_health_payload() -> str:
    """Return a minimal health response body."""

    return "ok"
