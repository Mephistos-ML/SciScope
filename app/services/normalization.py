"""Signal normalization logic lives here.

Normalization converts ``RawSignal`` objects into ``NormalizedSignal`` objects
that can be matched against a research profile without source-specific logic.
"""

from __future__ import annotations

from app.models.signal import NormalizedSignal, RawSignal


def normalize_raw_signal(raw_signal: RawSignal) -> NormalizedSignal:
    """Normalize a raw signal into a matching-ready shared shape.

    V0 keeps normalization intentionally small and explainable. The first target
    is GitHub-like software signals, so the normalizer primarily concatenates
    the text fields that matter for deterministic matching.
    """

    signal_kind = _read_signal_kind(raw_signal)
    normalized_text = _build_normalized_text(raw_signal)

    return NormalizedSignal(
        source=raw_signal.source,
        item_id=raw_signal.item_id,
        signal_kind=signal_kind,
        title=raw_signal.title,
        url=raw_signal.url,
        published_at=raw_signal.published_at,
        normalized_text=normalized_text,
        metadata={
            "source_type": raw_signal.source_type,
            "repo": raw_signal.payload.get("repo"),
            "author": raw_signal.payload.get("author"),
            "files": raw_signal.payload.get("files", []),
        },
    )


def _read_signal_kind(raw_signal: RawSignal) -> str:
    signal_kind = raw_signal.payload.get("signal_kind")
    if isinstance(signal_kind, str) and signal_kind.strip():
        return signal_kind.strip()

    return raw_signal.source_type


def _build_normalized_text(raw_signal: RawSignal) -> str:
    parts: list[str] = [
        raw_signal.title,
        raw_signal.raw_text,
    ]

    repo = raw_signal.payload.get("repo")
    if isinstance(repo, str) and repo.strip():
        parts.append(repo)

    author = raw_signal.payload.get("author")
    if isinstance(author, str) and author.strip():
        parts.append(author)

    files = raw_signal.payload.get("files")
    if isinstance(files, list):
        parts.extend(str(file_path) for file_path in files if str(file_path).strip())

    return "\n".join(part.strip() for part in parts if part.strip())
