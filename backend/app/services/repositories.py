"""Inspect and repair catalog profiles using authoritative provider facts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.models.repository import Repository, RepositoryProfileSnapshot, parse_repository_id
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.storage.repositories.repositories import (
    list_repository_profile_snapshots,
    replace_repository_profile_if_unchanged,
)


_REPAIR_PAGE_SIZE = 100


@dataclass(frozen=True)
class RepositoryProfileRepair:
    repository_id: str
    status: Literal["would_update", "updated", "unchanged", "skipped_changed", "failed"]
    changes: dict[str, dict[str, object]]
    error: str | None = None


def repair_repository_profiles(
    *,
    load_repository_profile: Callable[[str], Repository],
    database_url: str,
    apply: bool = False,
    repository_ids: Sequence[str] = (),
    limit: int = 100,
) -> list[RepositoryProfileRepair]:
    """Preview by default; apply refreshes only to unchanged catalog revisions."""
    if limit <= 0:
        raise ValueError("Repair limit must be positive.")
    selected: list[RepositoryProfileSnapshot] = []
    missing_ids = set(repository_ids)
    if repository_ids:
        requested_ids = sorted(missing_ids)
        # Check every requested ID, including those beyond the provider budget,
        # so existing but unprocessed profiles are never reported as missing.
        for start in range(0, len(requested_ids), _REPAIR_PAGE_SIZE):
            page = list_repository_profile_snapshots(
                database_url=database_url, limit=_REPAIR_PAGE_SIZE,
                repository_ids=requested_ids[start:start + _REPAIR_PAGE_SIZE],
            )
            missing_ids.difference_update(snapshot.repository.repository_id for snapshot in page)
            selected.extend(page[:limit - len(selected)])
    else:
        after_repository_id = None
        while len(selected) < limit:
            page = list_repository_profile_snapshots(
                database_url=database_url, limit=_REPAIR_PAGE_SIZE,
                after_repository_id=after_repository_id,
            )
            if not page:
                break
            for snapshot in page:
                if _looks_like_subscription_profile(snapshot.repository):
                    selected.append(snapshot)
                    if len(selected) == limit:
                        break
            after_repository_id = page[-1].repository.repository_id
    reports: list[RepositoryProfileRepair] = []
    for snapshot in selected:
        original = snapshot.repository
        try:
            refreshed = load_repository_profile(original.repository_id)
            if (
                refreshed.repository_id != original.repository_id
                or refreshed.source != original.source
                or refreshed.provider_repository_id != parse_repository_id(
                    original.repository_id, source=original.source,
                )
            ):
                raise ValueError("Provider profile does not match the requested repository ID.")
        except (RepositorySourceError, ValueError) as exc:
            reports.append(RepositoryProfileRepair(
                original.repository_id, "failed", {}, str(exc),
            ))
            continue
        changes = {
            name: {"before": getattr(original, name), "after": getattr(refreshed, name)}
            for name in (
                "full_name", "url", "owner_login", "description", "language",
                "stars", "topics", "provider_updated_at", "metadata",
            )
            if getattr(original, name) != getattr(refreshed, name)
        }
        if not changes:
            status = "unchanged"
        elif not apply:
            status = "would_update"
        elif replace_repository_profile_if_unchanged(
            refreshed, expected_updated_at=snapshot.updated_at, database_url=database_url,
        ):
            status = "updated"
        else:
            status = "skipped_changed"
        reports.append(RepositoryProfileRepair(original.repository_id, status, changes))
    reports.extend(
        RepositoryProfileRepair(repository_id, "failed", {}, "Repository is not in the catalog.")
        for repository_id in sorted(missing_ids)
    )
    return reports


def _looks_like_subscription_profile(repository: Repository) -> bool:
    """Select profiles with query metadata and missing provider facts."""
    return (
        "query" in repository.metadata
        and not repository.owner_login
        and not repository.description
        and not repository.language
        and repository.stars == 0
        and not repository.topics
        and repository.provider_updated_at is None
    )
