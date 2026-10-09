"""GitLab monitoring adapter for repository releases and commits."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import monotonic
from json import JSONDecodeError
from urllib.parse import quote, quote_plus, urlencode

from app.integrations.repositories.common.release_comparison import find_previous_release_tag, valid_commit_sha, MAX_RELEASE_RESPONSE_BYTES
from app.models.monitoring import RepositoryActivity, ReleaseCommitDetails, MAX_RELEASE_COMMIT_DETAILS
from app.models.repository import Repository
from app.models.signal import Signal
from app.integrations.repositories.common.models import (
    RepositoryCommit,
    RepositoryRelease,
)
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.common.factories import (
    build_repository_commit_signal,
    build_repository_release_signal,
    read_repository_name,
)
from app.integrations.repositories.common.models import RepositoryActivityBatch
from app.integrations.repositories.gitlab.client import GitLabClient


RELEASE_PAGE_SIZE = 100
MAX_RELEASE_PAGES = 10
COMMIT_PAGE_SIZE = 100
MAX_COMMIT_PAGES = 10


@dataclass(frozen=True)
class GitLabRepositoryMonitor:
    client: GitLabClient

    def load_repository_activity(
        self,
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
            releases = self._load_release_signals(repo_full_name, started_after=release_started_after)
        if commit_started_after is not None:
            try:
                commits = self._load_commit_signals(repo_full_name, started_after=commit_started_after, after_sha=commit_after_sha)
            except (RepositorySourceError, JSONDecodeError):
                commits = RepositoryActivityBatch(signals=(), complete=False)
        return RepositoryActivity(
            signals=(*releases.signals, *commits.signals),
            releases_complete=releases.complete, commits_complete=commits.complete,
            commit_head_sha=commits.head_sha,
            redirected=releases.redirected or commits.redirected,
        )


    def load_release_commit_details(
        self, repository: Repository, release: Signal, *, deadline_monotonic: float,
    ) -> ReleaseCommitDetails:
        """Compare the preceding published release to this tag, using pinned SHAs."""
        name = read_repository_name(repository)
        tag = release.payload.get("tag_name")
        if not name or not isinstance(tag, str) or not tag or release.published_at is None:
            return ReleaseCommitDetails()
        base_url = f"{self.client.api_base}/projects/{quote_plus(name)}"

        def fetch(url: str) -> object:
            if monotonic() >= deadline_monotonic:
                raise TimeoutError("Release comparison budget expired.")
            return self.client.fetch_json(url, deadline_monotonic=deadline_monotonic,
                                          max_response_bytes=MAX_RELEASE_RESPONSE_BYTES).payload

        commits: dict[str, Signal] = {}
        base_sha = head_sha = None
        total = None
        try:
            previous_tag = find_previous_release_tag(
                release, lambda page: fetch(f"{base_url}/releases?per_page=100&page={page}&order_by=released_at&sort=desc"),
                timestamp_field="released_at", parse_timestamp=_parse_gitlab_datetime,
            )
            if previous_tag is None:
                return ReleaseCommitDetails()
            base = fetch(f"{base_url}/repository/tags/{quote(previous_tag, safe='')}")
            head = fetch(f"{base_url}/repository/tags/{quote(tag, safe='')}")
            base_commit = base.get("commit") if isinstance(base, dict) else None
            head_commit = head.get("commit") if isinstance(head, dict) else None
            base_sha = base_commit.get("id") if isinstance(base_commit, dict) else None
            head_sha = head_commit.get("id") if isinstance(head_commit, dict) else None
            if not valid_commit_sha(base_sha) or not valid_commit_sha(head_sha):
                return ReleaseCommitDetails()
            if base_sha == head_sha:
                return ReleaseCommitDetails("complete", (), base_sha, head_sha, 0)
            reverse = fetch(f"{base_url}/repository/compare?" + urlencode({
                "from": head_sha, "to": base_sha, "straight": "true",
            }))
            reverse_tip = reverse.get("commit") if isinstance(reverse, dict) else None
            if (not isinstance(reverse, dict) or reverse.get("commits") != []
                    or not isinstance(reverse_tip, dict) or reverse_tip.get("id") != base_sha):
                return ReleaseCommitDetails()
            payload = fetch(f"{base_url}/repository/compare?" + urlencode({
                "from": base_sha, "to": head_sha, "straight": "true",
            }))
            if not isinstance(payload, dict) or not isinstance(payload.get("commits"), list):
                return ReleaseCommitDetails()
            tip = payload.get("commit")
            if not isinstance(tip, dict) or tip.get("id") != head_sha:
                return ReleaseCommitDetails()
            items = payload["commits"]
            total = len(items)
            valid = True
            for item in items[:MAX_RELEASE_COMMIT_DETAILS]:
                signal = _map_commit(name, item, branch="") if isinstance(item, dict) and valid_commit_sha(item.get("id")) else None
                if signal is None:
                    valid = False
                else:
                    commits[signal.item_id] = signal
            # GitLab documents commits as complete even if diff comparison times
            # out. The local size budget and commit mapping still limit coverage.
            if valid and len(commits) == total and any(c.payload.get("commit_sha") == head_sha for c in commits.values()):
                return ReleaseCommitDetails("complete", tuple(commits.values()), base_sha, head_sha, total)
        except (RepositorySourceError, JSONDecodeError, TimeoutError):
            pass
        if commits and base_sha and head_sha:
            return ReleaseCommitDetails("partial", tuple(commits.values()), base_sha, head_sha, total)
        return ReleaseCommitDetails()

    def refresh_repository_profile(self, repository: Repository) -> Repository:
        """Load the canonical GitLab profile by immutable provider project ID."""

        provider_repository_id = repository.provider_repository_id.strip()
        if not provider_repository_id:
            return repository

        response = self.client.fetch_json(
            f"{self.client.api_base}/projects/{quote_plus(provider_repository_id)}"
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
        self,
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
                f"{self.client.api_base}/projects/{encoded_repo}/releases"
                f"?per_page={RELEASE_PAGE_SIZE}&page={page}&order_by=released_at&sort=desc"
            )
            try:
                response = self.client.fetch_json(releases_url)
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
        self,
        repo_full_name: str, *, started_after: datetime, after_sha: str | None,
    ) -> RepositoryActivityBatch:
        signals: list[Signal] = []
        seen_ids: set[str] = set()
        redirected = False
        complete = True
        base_url = f"{self.client.api_base}/projects/{quote_plus(repo_full_name)}"

        def fetch(url: str) -> object:
            nonlocal redirected
            response = self.client.fetch_json(url)
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

def _map_commit(repo_full_name: str, item: object, *, branch: str = "default") -> Signal | None:
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
        branch=branch,
        author_name=str(item.get("author_name") or ""),
        body=message,
    )
    return build_repository_commit_signal(commit)


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
