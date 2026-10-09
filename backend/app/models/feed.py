"""Feed event domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid5

from app.models.monitoring import MAX_RELEASE_COMMIT_DETAILS, ReleaseCommitStatus

FEED_EVENT_ID_NAMESPACE = UUID("e71b2aec-1284-582c-a932-f86ef904d44c")
FEED_UPDATE_GROUP_ID_NAMESPACE = UUID("fc1663e6-3c3d-4b77-8adc-70fbffb44c93")
RELEASE_COMMIT_METADATA_KEY = "release_commit_details"

FeedUpdateKind = Literal["release", "commits"]


def build_feed_update_group_id(
    subscription_id: str,
    kind: FeedUpdateKind,
    publication_key: str,
) -> str:
    """Identify a release or one scan publication independently of its display."""
    if not subscription_id or kind not in {"release", "commits"} or not publication_key:
        raise ValueError(
            "A group requires a subscription, supported kind, and publication key."
        )
    return str(
        uuid5(
            FEED_UPDATE_GROUP_ID_NAMESPACE,
            "\x1f".join((subscription_id, kind, publication_key)),
        )
    )


@dataclass(frozen=True)
class FeedUpdateGroup:
    """An immutable publication of events for one user's repository subscription."""

    group_id: str
    user_id: str
    subscription_id: str
    repository_id: str
    kind: FeedUpdateKind
    event_ids: tuple[str, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if not all(
            (self.group_id, self.user_id, self.subscription_id, self.repository_id)
        ):
            raise ValueError("Group identity and ownership are required.")
        if self.kind not in {"release", "commits"}:
            raise ValueError("Unsupported Feed update kind.")
        if (
            not self.event_ids
            or not all(self.event_ids)
            or len(set(self.event_ids)) != len(self.event_ids)
        ):
            raise ValueError("A group requires a nonempty set of distinct event IDs.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("Group creation time must include a timezone.")


def build_feed_event_id(subscription_id: str, source: str, item_id: str) -> str:
    """Build the stable opaque identity for one subscribed provider event."""

    return str(
        uuid5(FEED_EVENT_ID_NAMESPACE, "\x1f".join((subscription_id, source, item_id)))
    )


@dataclass(frozen=True)
class FeedEvent:
    """One user-visible monitoring event kept in the durable feed."""

    event_id: str
    user_id: str
    subscription_id: str
    repository_id: str
    repository_full_name: str
    repository_source: str
    repository_url: str
    selected_query: str | None
    source: str
    kind: str
    item_id: str
    title: str
    url: str
    published_at: datetime | None
    raw_text: str
    normalized_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    read_at: datetime | None = None


@dataclass(frozen=True)
class FeedCursor:
    """Stable position in one user's reverse-chronological Feed."""

    published_at: datetime | None
    created_at: datetime
    event_id: str


@dataclass(frozen=True)
class FeedGroupCursor:
    """Position in the activity-ordered publication list."""

    published_at: datetime | None
    created_at: datetime
    group_id: str


@dataclass(frozen=True)
class FeedGroupSummary:
    """Bounded publication view; membership and read state are derived facts."""

    group_id: str
    subscription_id: str
    repository_id: str
    kind: FeedUpdateKind
    created_at: datetime
    published_at: datetime | None
    event_count: int
    commit_count: int
    unread_event_count: int
    representative: FeedEvent


@dataclass(frozen=True)
class FeedReleaseCommitDetails:
    """Versioned references to canonical event facts, never copied commit content."""

    status: ReleaseCommitStatus = "unavailable"
    event_ids: tuple[str, ...] = ()
    base_sha: str | None = None
    head_sha: str | None = None
    total_count: int | None = None

    def __post_init__(self) -> None:
        if self.status not in {"complete", "partial", "unavailable"}:
            raise ValueError("Unsupported release commit coverage.")
        if (
            len(self.event_ids) > MAX_RELEASE_COMMIT_DETAILS
            or len(set(self.event_ids)) != len(self.event_ids)
            or not all(self.event_ids)
        ):
            raise ValueError("Release references must be distinct and bounded.")
        if self.status == "unavailable" and self.event_ids:
            raise ValueError("Unavailable comparisons cannot assert commit membership.")
        if self.status != "unavailable" and not (self.base_sha and self.head_sha):
            raise ValueError("Confirmed comparisons require pinned endpoints.")
        if self.total_count is not None and (
            self.total_count < len(self.event_ids) or self.total_count < 0
        ):
            raise ValueError("Invalid release comparison count.")
        if self.status == "complete" and self.total_count != len(self.event_ids):
            raise ValueError("Complete coverage requires the exact commit count.")

    def to_metadata(self) -> dict[str, object]:
        return {
            "v": 1,
            "status": self.status,
            "eventIds": list(self.event_ids),
            "baseSha": self.base_sha,
            "headSha": self.head_sha,
            "totalCount": self.total_count,
        }


def read_feed_release_commit_details(
    metadata: dict[str, Any],
) -> FeedReleaseCommitDetails:
    if RELEASE_COMMIT_METADATA_KEY not in metadata:
        return FeedReleaseCommitDetails()
    value = metadata[RELEASE_COMMIT_METADATA_KEY]
    if (
        not isinstance(value, dict)
        or type(value.get("v")) is not int
        or value["v"] != 1
    ):
        raise ValueError("Unsupported persisted release commit details version.")
    ids, total = value.get("eventIds"), value.get("totalCount")
    status = value.get("status")
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("Invalid persisted release commit references.")
    if not isinstance(status, str) or status not in {
        "complete",
        "partial",
        "unavailable",
    }:
        raise ValueError("Invalid persisted release commit coverage.")
    if total is not None and type(total) is not int:
        raise ValueError("Invalid persisted release comparison count.")
    for field_name in ("baseSha", "headSha"):
        if value.get(field_name) is not None and not isinstance(value[field_name], str):
            raise ValueError("Invalid persisted comparison endpoint.")
    return FeedReleaseCommitDetails(
        cast(ReleaseCommitStatus, status),
        tuple(ids),
        value.get("baseSha"),
        value.get("headSha"),
        total,
    )


@dataclass(frozen=True)
class FeedGroupCommitPage:
    """A bounded page and the count of currently retained referenced facts."""

    events: tuple[FeedEvent, ...]
    retained_count: int


@dataclass(frozen=True)
class FeedPublicationEvents:
    """Refresh observed activity, but only insert previously unseen detail facts."""

    events: tuple[FeedEvent, ...]
    supplemental_events: tuple[FeedEvent, ...]
