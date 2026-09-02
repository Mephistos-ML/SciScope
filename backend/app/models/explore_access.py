"""Domain models for explore access control."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExploreTier(StrEnum):
    """Supported access tiers for repository exploration."""

    GUEST = "guest"
    USER = "user"
    SUSPICIOUS = "suspicious"


class ExploreLimitCode(StrEnum):
    """Stable machine-readable explore access outcomes."""

    GUEST_SEARCH_DISABLED = "explore_guest_search_disabled"
    GUEST_COOLDOWN = "explore_guest_cooldown"
    GUEST_QUOTA_EXCEEDED = "explore_guest_quota_exceeded"
    USER_COOLDOWN = "explore_user_cooldown"
    USER_QUOTA_EXCEEDED = "explore_user_quota_exceeded"
    TURNSTILE_REQUIRED = "explore_turnstile_required"
    TURNSTILE_VERIFICATION_FAILED = "explore_turnstile_verification_failed"
    GLOBAL_CAPACITY_REACHED = "explore_global_capacity_reached"


class ExploreAccessOutcome(StrEnum):
    """Persisted access outcomes for one explore attempt."""

    ALLOWED = "allowed"
    ALLOWED_INTERNAL = "allowed_internal"
    BLOCKED_DISABLED = "blocked_disabled"
    BLOCKED_COOLDOWN = "blocked_cooldown"
    BLOCKED_QUOTA = "blocked_quota"
    BLOCKED_CAPACITY = "blocked_capacity"
    BLOCKED_TURNSTILE = "blocked_turnstile"


@dataclass(frozen=True)
class ExploreActor:
    """Resolved subject for one explore access decision."""

    tier: ExploreTier
    subject_type: str
    subject_key: str
    user_id: str | None = None
    ip_hash: str | None = None


@dataclass(frozen=True)
class ExploreAccessDecision:
    """Result of one explore access check."""

    allowed: bool
    code: ExploreLimitCode | None = None
    message: str | None = None
    retry_after_seconds: int | None = None
    sign_in_suggested: bool = False
    turnstile_required: bool = False
