"""GitHub source loader for live repository releases."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from urllib.request import Request, urlopen

from app.models.signal import RawSignal

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_USER_AGENT = "SciScope/0.1"


def load_repo_activity(
    repo_full_name: str,
    *,
    started_after: datetime | None,
) -> list[RawSignal]:
    """Load releases created after the monitoring start time."""

    if started_after is None:
        return []

    return _load_release_signals(repo_full_name, started_after=started_after)


def _load_release_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> list[RawSignal]:
    releases_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases?per_page=10"
    payload = _fetch_json(releases_url)

    if not isinstance(payload, list):
        return []

    signals: list[RawSignal] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        published_at = _parse_github_datetime(
            item.get("published_at") or item.get("created_at"),
        )
        if published_at is None or published_at <= started_after:
            continue

        title = str(item.get("name") or item.get("tag_name") or "GitHub release")
        body = str(item.get("body") or "")
        tag_name = str(item.get("tag_name") or "")
        release_id = str(item.get("id") or tag_name or title)

        signals.append(
            RawSignal(
                source="github",
                source_type="github_release",
                item_id=f"{repo_full_name}:release:{release_id}",
                title=f"{repo_full_name} release {title}",
                url=str(item.get("html_url") or f"https://github.com/{repo_full_name}/releases"),
                published_at=published_at,
                raw_text=f"{title}\n\n{body}\n\n{tag_name}".strip(),
                payload={
                    "signal_kind": "github_release",
                    "repo": repo_full_name,
                    "tag_name": tag_name,
                    "source_type": "github_release",
                },
            )
        )

    return signals

def _parse_github_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

def _fetch_json(url: str) -> object:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": DEFAULT_USER_AGENT,
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)
