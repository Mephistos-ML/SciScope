"""Explore access-control package."""

from app.services.search.access.errors import ExploreAccessDeniedError, build_explore_access_denied_error
from app.services.search.access.policy import has_search_quota_bypass
from app.services.search.access.service import (
    build_turnstile_failure_decision, check_explore_access, hash_explore_topic,
    read_explore_client_ip, record_allowed_explore_attempt, record_blocked_explore_attempt,
    resolve_explore_actor,
)
