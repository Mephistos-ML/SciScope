"""GitLab monitoring adapter for repository releases and commits."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from json import JSONDecodeError
from urllib.parse import quote, quote_plus, urlencode

from app.models.repository import Repository
from app.models.signal import Signal
from app.sources.common import (
    RepositoryActivity,
    RepositoryCommit,
    RepositoryRelease,
    RepositorySourceError,
    build_repository_main_commit_signal,
    build_repository_release_signal,
    read_repository_name,
)
from app.sources.common.models import RepositoryActivityBatch
from app.sources.gitlab.client import (
    GITLAB_API_BASE,
    fetch_json,
)


RELEASE_PAGE_SIZE = 100
MAX_RELEASE_PAGES = 10
COMMIT_PAGE_SIZE = 100
MAX_COMMIT_PAGES = 10

def load_repository_activity(
    repository: Repository,
    *,
    release_started_after: datetime | None,
    commit_started_after: datetime | None,
    commit_after_sha: str | None = None,
) -> RepositoryActivity:
    """Load repository activity and report whether its provider URL redirected."""

    repo_full_name = read_repository_name(repository)
    if repo_full_name is None:
        return RepositoryActivity(signals=(), releases_complete=False, commits_complete=False)

    releases = RepositoryActivityBatch(signals=(), complete=True)
    commits = RepositoryActivityBatch(signals=(), complete=True)
    if release_started_after is not None:
        releases = _load_release_signals(repo_full_name, started_after=release_started_after)
    if commit_started_after is not None:
        try:
            commits = _load_commit_signals(repo_full_name, started_after=commit_started_after, after_sha=commit_after_sha)
        except (RepositorySourceError, JSONDecodeError):
            commits = RepositoryActivityBatch(signals=(), complete=False)
    return RepositoryActivity(
        signals=(*releases.signals, *commits.signals),
        releases_complete=releases.complete, commits_complete=commits.complete,
        commit_head_sha=commits.head_sha,
        redirected=releases.redirected or commits.redirected,
    )


def refresh_repository_profile(repository: Repository) -> Repository:
    """Load the canonical GitLab profile by immutable provider project ID."""

    provider_repository_id = repository.provider_repository_id.strip()
    if not provider_repository_id:
        return repository

    response = fetch_json(
        f"{GITLAB_API_BASE}/projects/{quote_plus(provider_repository_id)}"
    )
    payload = response.payload
    if not isinstance(payload, dict):
        return repository

    full_name = str(payload.get("path_with_namespace") or "").strip()
    url = str(payload.get("web_url") or "").strip()
    if not full_name or not url:
        return repository
    metadata = dict(repository.metadata)
    metadata["repo"] = full_name
    return replace(repository, full_name=full_name, url=url, metadata=metadata)

def _load_release_signals(
    repo_full_name: str,
    *,
    started_after: datetime,
) -> RepositoryActivityBatch:
    encoded_repo = quote_plus(repo_full_name)
    signals: list[Signal] = []
    seen_ids: set[str] = set()
    redirected = False
    complete = True
    for page in range(1, MAX_RELEASE_PAGES + 1):
        releases_url = (
            f"{GITLAB_API_BASE}/projects/{encoded_repo}/releases"
            f"?per_page={RELEASE_PAGE_SIZE}&page={page}&order_by=released_at&sort=desc"
        )
        try:
            response = fetch_json(releases_url)
        except (RepositorySourceError, JSONDecodeError):
            return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)
        redirected = redirected or response.url != releases_url
        payload = response.payload
        if not isinstance(payload, list):
            return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)
        crossed_boundary = False
        for item in payload:
            if not isinstance(item, dict):
                complete = False
                continue

            published_at = _parse_gitlab_datetime(
                item.get("released_at"),
            )
            if published_at is None:
                complete = False
                continue
            if published_at < started_after:
                crossed_boundary = True
                continue

            title = str(item.get("name") or item.get("tag_name") or "GitLab release")
            body = str(item.get("description") or "")
            tag_name = str(item.get("tag_name") or "")
            if not tag_name:
                complete = False
                continue
            release_id = tag_name or title

            release = RepositoryRelease(
                source="gitlab",
                repo_full_name=repo_full_name,
                release_id=release_id,
                title=title,
                url=str(
                    item.get("_links", {}).get("self")
                    if isinstance(item.get("_links"), dict)
                    else item.get("commit_path")
                    or f"https://gitlab.com/{repo_full_name}/-/releases"
                ),
                published_at=published_at,
                tag_name=tag_name,
                body=body,
            )
            signal = build_repository_release_signal(release)
            if signal.item_id not in seen_ids:
                seen_ids.add(signal.item_id)
                signals.append(signal)
        if len(payload) < RELEASE_PAGE_SIZE or crossed_boundary:
            return RepositoryActivityBatch(signals=tuple(signals), complete=complete, redirected=redirected)

    return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)


def _load_commit_signals(
    repo_full_name: str, *, started_after: datetime, after_sha: str | None,
) -> RepositoryActivityBatch:
    signals: list[Signal] = []
    seen_ids: set[str] = set()
    redirected = False
    complete = True
    base_url = f"{GITLAB_API_BASE}/projects/{quote_plus(repo_full_name)}"

    def fetch(url: str) -> object:
        nonlocal redirected
        response = fetch_json(url)
        redirected = redirected or response.url != url
        return response.payload

    def collect(items: list, *, bootstrap: bool = False) -> None:
        nonlocal complete
        for item in items:
            signal = _map_commit(repo_full_name, item)
            if signal is None:
                complete = False
                continue
            if bootstrap and signal.published_at < started_after:
                continue
            if signal.item_id not in seen_ids:
                seen_ids.add(signal.item_id)
                signals.append(signal)

    try:
        profile = fetch(base_url)
        branch = profile.get("default_branch") if isinstance(profile, dict) else None
        if not isinstance(branch, str) or not branch:
            return RepositoryActivityBatch(signals=(), complete=False, redirected=redirected)
        branch_payload = fetch(f"{base_url}/repository/branches/{quote(branch, safe='')}")
        tip = branch_payload.get("commit") if isinstance(branch_payload, dict) else None
        head_sha = tip.get("id") if isinstance(tip, dict) else None
        if not isinstance(head_sha, str) or not head_sha:
            return RepositoryActivityBatch(signals=(), complete=False, redirected=redirected)
        if after_sha == head_sha:
            return RepositoryActivityBatch(signals=(), complete=True, head_sha=head_sha, redirected=redirected)
        if after_sha is None:
            for page in range(1, MAX_COMMIT_PAGES + 1):
                parameters = urlencode({
                    "ref_name": head_sha,
                    "since": started_after.isoformat(), "per_page": COMMIT_PAGE_SIZE, "page": page,
                })
                items = fetch(f"{base_url}/repository/commits?{parameters}")
                if not isinstance(items, list):
                    break
                collect(items, bootstrap=True)
                if len(items) < COMMIT_PAGE_SIZE:
                    return RepositoryActivityBatch(signals=tuple(signals), complete=complete,
                                                   head_sha=head_sha if complete else None, redirected=redirected)
        else:
            reverse = fetch(f"{base_url}/repository/compare?" + urlencode({
                "from": head_sha, "to": after_sha, "straight": "true",
            }))
            if not isinstance(reverse, dict) or reverse.get("commits") != []:
                return RepositoryActivityBatch(signals=(), complete=False, redirected=redirected)
            reverse_tip = reverse.get("commit")
            if not isinstance(reverse_tip, dict) or reverse_tip.get("id") != after_sha:
                return RepositoryActivityBatch(signals=(), complete=False, redirected=redirected)
            payload = fetch(f"{base_url}/repository/compare?" + urlencode({
                "from": after_sha, "to": head_sha, "straight": "true",
            }))
            if isinstance(payload, dict) and isinstance(payload.get("commits"), list):
                items = payload["commits"]
                budget = COMMIT_PAGE_SIZE * MAX_COMMIT_PAGES
                collect(items[:budget])
                tip = payload.get("commit")
                complete = (complete and len(items) <= budget and isinstance(tip, dict)
                            and tip.get("id") == head_sha
                            and any(item.get("id") == head_sha for item in items if isinstance(item, dict)))
                return RepositoryActivityBatch(signals=tuple(signals), complete=complete,
                                               head_sha=head_sha if complete else None, redirected=redirected)
    except (RepositorySourceError, JSONDecodeError):
        pass
    return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)


def _map_commit(repo_full_name: str, item: object) -> Signal | None:
    """Map a provider commit without treating its timestamp as an arrival boundary."""
    if not isinstance(item, dict):
        return None
    published_at = _parse_gitlab_datetime(
        item.get("committed_date") or item.get("created_at"),
    )
    if published_at is None:
        return None

    commit_sha = str(item.get("id") or "").strip()
    if not commit_sha:
        return None

    message = str(item.get("message") or item.get("title") or "").strip()
    title = str(item.get("title") or (message.splitlines()[0] if message else "GitLab commit"))
    commit = RepositoryCommit(
        source="gitlab",
        repo_full_name=repo_full_name,
        commit_sha=commit_sha,
        title=title.strip(),
        url=str(
            item.get("web_url")
            or f"https://gitlab.com/{repo_full_name}/-/commit/{commit_sha}"
        ),
        published_at=published_at,
        branch="default",
        author_name=str(item.get("author_name") or ""),
        body=message,
    )
    return build_repository_main_commit_signal(commit)


def _parse_gitlab_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
