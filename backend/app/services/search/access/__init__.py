"""Explore access-control package."""

from app.services.search.access.errors import (
    ExploreAccessDeniedError,
    ExploreCapacityError,
    ExploreCooldownError,
    ExploreQuotaExceededError,
    ExploreTurnstileRequiredError,
    build_explore_access_denied_error,
)
from app.services.search.access.service import (
    build_turnstile_failure_decision,
    check_explore_access,
    hash_explore_topic,
    read_explore_client_ip,
    record_allowed_explore_attempt,
    record_blocked_explore_attempt,
    resolve_explore_actor,
)
from app.services.search.access.policy import has_search_quota_bypass

__all__ = [
    "build_explore_access_denied_error",
    "build_turnstile_failure_decision",
    "check_explore_access",
    "ExploreAccessDeniedError",
    "ExploreCapacityError",
    "ExploreCooldownError",
    "ExploreQuotaExceededError",
    "ExploreTurnstileRequiredError",
    "hash_explore_topic",
    "has_search_quota_bypass",
    "read_explore_client_ip",
    "record_allowed_explore_attempt",
    "record_blocked_explore_attempt",
    "resolve_explore_actor",
]
