"""Replay fixtures for forward-only testing without live publication."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import REPLAY_FIXTURES_PATH
from app.models.signal import RawSignal


def load_replay_signals(fixtures_path: Path = REPLAY_FIXTURES_PATH) -> list[RawSignal]:
    """Load replay signals from a local JSON file.

    The fixtures file is the intended place for manually curated relevant and
    irrelevant events with explicit event times.
    """

    if not fixtures_path.exists():
        return []

    with fixtures_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Replay fixtures must be a JSON list.")

    signals: list[RawSignal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        signals.append(_parse_raw_signal(item))

    return signals


def _parse_raw_signal(item: dict[str, Any]) -> RawSignal:
    published_at_raw = item.get("published_at")
    published_at = None
    if isinstance(published_at_raw, str) and published_at_raw.strip():
        published_at = datetime.fromisoformat(published_at_raw)

    payload = item.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    return RawSignal(
        source=str(item.get("source", "github_replay")),
        source_type=str(item.get("source_type", "github_commit")),
        item_id=str(item["item_id"]),
        title=str(item["title"]),
        url=str(item["url"]),
        published_at=published_at,
        raw_text=str(item.get("raw_text", "")),
        payload=payload,
    )
