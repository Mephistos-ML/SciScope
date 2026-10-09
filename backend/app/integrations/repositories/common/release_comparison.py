"""Bounded predecessor lookup and identity validation for release comparisons."""

from collections.abc import Callable
from datetime import datetime

from app.models.signal import Signal

MAX_RELEASE_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_RELEASE_CATALOG_PAGES = 3
RELEASE_CATALOG_PAGE_SIZE = 100


def find_previous_release_tag(
    release: Signal, fetch_page: Callable[[int], object], *, timestamp_field: str,
    parse_timestamp: Callable[[object], datetime | None],
) -> str | None:
    """Require a complete bounded catalogue and an unambiguous preceding release."""
    candidates: list[tuple[datetime, str]] = []
    found_target = False
    for page in range(1, MAX_RELEASE_CATALOG_PAGES + 1):
        items = fetch_page(page)
        if not isinstance(items, list) or len(items) > RELEASE_CATALOG_PAGE_SIZE:
            return None
        for item in items:
            if not isinstance(item, dict):
                return None
            if item.get("draft") is True:
                continue
            timestamp, tag = parse_timestamp(item.get(timestamp_field)), item.get("tag_name")
            if timestamp is None or not isinstance(tag, str) or not tag:
                return None
            found_target = found_target or (tag == release.payload.get("tag_name") and timestamp == release.published_at)
            if release.published_at is not None and timestamp < release.published_at:
                candidates.append((timestamp, tag))
        if len(items) < RELEASE_CATALOG_PAGE_SIZE:
            break
    else:
        return None
    if not found_target or not candidates:
        return None
    latest = max(timestamp for timestamp, _ in candidates)
    tags = {tag for timestamp, tag in candidates if timestamp == latest}
    return tags.pop() if len(tags) == 1 else None


def valid_commit_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) in {40, 64} and all(c in "0123456789abcdef" for c in value)
