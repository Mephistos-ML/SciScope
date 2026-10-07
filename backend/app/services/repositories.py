"""Inspect and repair catalog profiles using authoritative provider facts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.models.repository import Repository, parse_repository_id
from app.sources.common.source_status import RepositorySourceError
from app.storage.repositories.repositories import (
    list_repository_profile_snapshots,
    replace_repository_profile_if_unchanged,
)


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
    snapshots = list_repository_profile_snapshots(
        database_url=database_url, repository_ids=repository_ids,
    )
    selected = [
        snapshot for snapshot in snapshots
        if repository_ids or _looks_like_subscription_profile(snapshot.repository)
    ][:limit]
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
    missing_ids = set(repository_ids) - {snapshot.repository.repository_id for snapshot in snapshots}
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
