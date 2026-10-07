"""GitHub monitoring adapter for repository releases and commits."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from json import JSONDecodeError
from urllib.parse import quote, urlencode

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
from app.sources.github.client import (
    GITHUB_API_BASE,
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
    """Load the canonical GitHub profile by immutable provider repository ID."""

    provider_repository_id = repository.provider_repository_id.strip()
    if not provider_repository_id:
        return repository

    response = fetch_json(
        f"{GITHUB_API_BASE}/repositories/{provider_repository_id}"
    )
    payload = response.payload
    if not isinstance(payload, dict):
        return repository

    full_name = str(payload.get("full_name") or "").strip()
    url = str(payload.get("html_url") or "").strip()
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
    signals: list[Signal] = []
    seen_ids: set[str] = set()
    redirected = False
    complete = True
    for page in range(1, MAX_RELEASE_PAGES + 1):
        releases_url = (
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/releases"
            f"?per_page={RELEASE_PAGE_SIZE}&page={page}"
        )
        try:
            response = fetch_json(releases_url)
        except (RepositorySourceError, JSONDecodeError):
            return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)
        redirected = redirected or response.url != releases_url
        payload = response.payload
        if not isinstance(payload, list):
            return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)
        for item in payload:
            if not isinstance(item, dict):
                complete = False
                continue

            published_at = _parse_github_datetime(
                item.get("published_at") or item.get("created_at"),
            )
            if published_at is None:
                complete = False
                continue
            if published_at < started_after:
                continue

            title = str(item.get("name") or item.get("tag_name") or "GitHub release")
            body = str(item.get("body") or "")
            tag_name = str(item.get("tag_name") or "")
            if not (item.get("id") or tag_name):
                complete = False
                continue
            release_id = str(item.get("id") or tag_name or title)

            release = RepositoryRelease(
                source="github",
                repo_full_name=repo_full_name,
                release_id=release_id,
                title=title,
                url=str(
                    item.get("html_url")
                    or f"https://github.com/{repo_full_name}/releases"
                ),
                published_at=published_at,
                tag_name=tag_name,
                body=body,
            )
            signal = build_repository_release_signal(release)
            if signal.item_id not in seen_ids:
                seen_ids.add(signal.item_id)
                signals.append(signal)
        if len(payload) < RELEASE_PAGE_SIZE:
            return RepositoryActivityBatch(signals=tuple(signals), complete=complete, redirected=redirected)

    return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)


def _load_commit_signals(
    repo_full_name: str, *, started_after: datetime, after_sha: str | None,
) -> RepositoryActivityBatch:
    signals: list[Signal] = []
    seen_ids: set[str] = set()
    redirected = False
    complete = True
    base_url = f"{GITHUB_API_BASE}/repos/{repo_full_name}"

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
        branch_payload = fetch(f"{base_url}/branches/{quote(branch, safe='')}")
        tip = branch_payload.get("commit") if isinstance(branch_payload, dict) else None
        head_sha = tip.get("sha") if isinstance(tip, dict) else None
        if not isinstance(head_sha, str) or not head_sha:
            return RepositoryActivityBatch(signals=(), complete=False, redirected=redirected)
        if after_sha == head_sha:
            return RepositoryActivityBatch(signals=(), complete=True, head_sha=head_sha, redirected=redirected)
        if after_sha is None:
            for page in range(1, MAX_COMMIT_PAGES + 1):
                parameters = urlencode({
                    "sha": head_sha,
                    "since": started_after.isoformat(), "per_page": COMMIT_PAGE_SIZE, "page": page,
                })
                items = fetch(f"{base_url}/commits?{parameters}")
                if not isinstance(items, list):
                    break
                collect(items, bootstrap=True)
                if len(items) < COMMIT_PAGE_SIZE:
                    return RepositoryActivityBatch(signals=tuple(signals), complete=complete,
                                                   head_sha=head_sha if complete else None, redirected=redirected)
        else:
            total = None
            for page in range(1, MAX_COMMIT_PAGES + 1):
                payload = fetch(f"{base_url}/compare/{quote(after_sha, safe='')}...{quote(head_sha, safe='')}"
                                f"?per_page={COMMIT_PAGE_SIZE}&page={page}")
                if not isinstance(payload, dict):
                    break
                items = payload.get("commits")
                merge_base = payload.get("merge_base_commit")
                if (payload.get("status") != "ahead" or not isinstance(merge_base, dict)
                        or merge_base.get("sha") != after_sha or not isinstance(items, list)):
                    break
                count = payload.get("total_commits")
                if type(count) is not int or count <= 0 or (total is not None and total != count):
                    break
                total = count
                collect(items)
                if len(seen_ids) == total:
                    complete = complete and any(signal.payload.get("commit_sha") == head_sha for signal in signals)
                    return RepositoryActivityBatch(signals=tuple(signals), complete=complete,
                                                   head_sha=head_sha if complete else None, redirected=redirected)
                if len(items) < COMMIT_PAGE_SIZE:
                    break
    except (RepositorySourceError, JSONDecodeError):
        pass
    return RepositoryActivityBatch(signals=tuple(signals), complete=False, redirected=redirected)


def _map_commit(repo_full_name: str, item: object) -> Signal | None:
    """Map a provider commit without treating its timestamp as an arrival boundary."""
    if not isinstance(item, dict):
        return None
    commit_payload = item.get("commit")
    if not isinstance(commit_payload, dict):
        return None

    author_payload = commit_payload.get("author")
    if not isinstance(author_payload, dict):
        author_payload = {}

    committer_payload = commit_payload.get("committer")
    if not isinstance(committer_payload, dict):
        committer_payload = {}
    published_at = _parse_github_datetime(committer_payload.get("date") or author_payload.get("date"))
    if published_at is None:
        return None

    commit_sha = str(item.get("sha") or "").strip()
    if not commit_sha:
        return None

    message = str(commit_payload.get("message") or "").strip()
    title = message.splitlines()[0].strip() if message else "GitHub commit"
    commit = RepositoryCommit(
        source="github",
        repo_full_name=repo_full_name,
        commit_sha=commit_sha,
        title=title,
        url=str(
            item.get("html_url")
            or f"https://github.com/{repo_full_name}/commit/{commit_sha}"
        ),
        published_at=published_at,
        branch="default",
        author_name=str(author_payload.get("name") or ""),
        body=message,
    )
    return build_repository_main_commit_signal(commit)


def _parse_github_datetime(value: object) -> datetime | None:
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
