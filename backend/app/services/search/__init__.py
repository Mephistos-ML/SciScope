"""Search and signal-processing service modules."""

from app.services.search.access import (
    build_turnstile_failure_decision,
    check_explore_access,
    hash_explore_topic,
    read_explore_client_ip,
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
    build_explore_access_denied_error,
)
from app.services.search.explore import (
    AiSearchPlanningError,
    ExploreSearchUnavailableError,
    run_explore_search,
)
from app.services.search.jobs import (
    create_explore_search_job,
    get_explore_search_job,
)

__all__ = [
    "AiSearchPlanningError",
    "build_explore_access_denied_error",
    "build_turnstile_failure_decision",
    "check_explore_access",
    "create_explore_search_job",
    "ExploreAccessDeniedError",
    "ExploreCapacityError",
    "ExploreCooldownError",
    "ExploreSearchUnavailableError",
    "ExploreQuotaExceededError",
    "ExploreTurnstileRequiredError",
    "get_explore_search_job",
    "hash_explore_topic",
    "read_explore_client_ip",
    "record_allowed_explore_attempt",
    "record_blocked_explore_attempt",
    "resolve_explore_actor",
    "run_explore_search",
]
