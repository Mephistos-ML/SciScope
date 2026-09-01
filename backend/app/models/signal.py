"""Signal domain models shared across ingestion, matching, and delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Signal:
    """Canonical signal shape used across ingestion, matching, and delivery."""

    source: str
    kind: str
    item_id: str
    title: str
    url: str
    published_at: datetime | None
    raw_text: str
    normalized_text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.normalized_text.strip():
            return
        object.__setattr__(self, "normalized_text", _build_normalized_text(self))


def _build_normalized_text(signal: Signal) -> str:
    parts: list[str] = [
        signal.title,
        signal.raw_text,
    ]

    repo = signal.payload.get("repo")
    if isinstance(repo, str) and repo.strip():
        parts.append(repo)

    author = signal.payload.get("author")
    if isinstance(author, str) and author.strip():
        parts.append(author)

    files = signal.payload.get("files")
    if isinstance(files, list):
        parts.extend(str(file_path) for file_path in files if str(file_path).strip())

    return "\n".join(part.strip() for part in parts if part.strip())
