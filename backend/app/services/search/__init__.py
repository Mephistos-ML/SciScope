"""Search and signal-processing service modules."""

from app.services.search.access import (
    check_explore_access,
    hash_explore_topic,
    record_allowed_explore_attempt,
    record_blocked_explore_attempt,
    resolve_explore_actor,
)
from app.services.search.errors import (
    ExploreAccessDeniedError,
    ExploreCapacityError,
    ExploreCooldownError,
    ExploreQuotaExceededError,
    ExploreTurnstileRequiredError,
)

__all__ = [
    "check_explore_access",
    "ExploreAccessDeniedError",
    "ExploreCapacityError",
    "ExploreCooldownError",
    "ExploreQuotaExceededError",
    "ExploreTurnstileRequiredError",
    "hash_explore_topic",
    "record_allowed_explore_attempt",
    "record_blocked_explore_attempt",
    "resolve_explore_actor",
]
