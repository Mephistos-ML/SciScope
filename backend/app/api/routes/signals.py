"""Signal read routes."""

from __future__ import annotations

from app.services.runtime import (
    get_signal_detail_payload,
    get_signal_list_payload,
    get_status_payload,
)


def get_status_response() -> dict[str, object]:
    """Return current dashboard status payload."""

    return get_status_payload()


def get_signal_list_response() -> dict[str, object]:
    """Return current signal list payload."""

    return get_signal_list_payload()


def get_signal_detail_response(item_id: str) -> dict[str, object] | None:
    """Return detail payload for one signal if present."""

    return get_signal_detail_payload(item_id)
