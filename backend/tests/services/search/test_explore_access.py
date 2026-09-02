"""Explore access control tests."""

from __future__ import annotations

from fastapi import Request

from app.models import ExploreAccessOutcome, ExploreActor, ExploreTier
from app.services.search.access import service as access_service
from app.services.search.access import policy as access_policy
from app.services.search.access.policy import should_require_turnstile
from app.services.security import turnstile as turnstile_service


def _build_request() -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"203.0.113.10")],
            "client": ("203.0.113.10", 443),
        }
    )


def test_resolve_explore_actor_marks_guest_as_suspicious_after_block_threshold(
    monkeypatch,
) -> None:
    monkeypatch.setattr(access_service, "TURNSTILE_ENABLED", True)
    monkeypatch.setattr(access_service, "EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD", 3)
    monkeypatch.setattr(
        access_service,
        "count_explore_events_since",
        lambda **kwargs: 3,
    )

    actor = access_service.resolve_explore_actor(_build_request(), None)

    assert actor.tier is ExploreTier.SUSPICIOUS
    assert actor.subject_type == "guest_ip"
    assert actor.ip_hash is not None


def test_check_explore_access_requires_turnstile_for_suspicious_guest(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.services.search.access.policy.TURNSTILE_ENABLED", True)
    actor = ExploreActor(
        tier=ExploreTier.SUSPICIOUS,
        subject_type="guest_ip",
        subject_key="guest_hash",
    )

    decision = access_service.check_explore_access(actor)

    assert should_require_turnstile(actor) is True
    assert decision.allowed is False
    assert decision.turnstile_required is True


def test_check_explore_access_allows_verified_turnstile_guest(monkeypatch) -> None:
    monkeypatch.setattr("app.services.search.access.policy.TURNSTILE_ENABLED", True)
    monkeypatch.setattr(
        access_service,
        "count_global_explore_events_since",
        lambda **kwargs: 0,
    )
    monkeypatch.setattr(access_service, "get_last_explore_event_at", lambda **kwargs: None)
    monkeypatch.setattr(access_service, "count_explore_events_since", lambda **kwargs: 0)

    actor = ExploreActor(
        tier=ExploreTier.SUSPICIOUS,
        subject_type="guest_ip",
        subject_key="guest_hash",
    )

    decision = access_service.check_explore_access(actor, turnstile_verified=True)

    assert decision.allowed is True


def test_check_explore_access_bypasses_product_quotas_for_internal_actor(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        access_service,
        "count_global_explore_events_since",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("global quota checked")),
    )
    monkeypatch.setattr(
        access_service,
        "get_last_explore_event_at",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("cooldown checked")),
    )
    monkeypatch.setattr(
        access_service,
        "count_explore_events_since",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("actor quota checked")),
    )
    actor = ExploreActor(
        tier=ExploreTier.USER,
        subject_type="user",
        subject_key="internal-user",
        user_id="internal-user",
    )

    decision = access_service.check_explore_access(actor, bypass_quota=True)

    assert decision.allowed is True


def test_record_allowed_explore_attempt_marks_internal_quota_bypass(monkeypatch) -> None:
    recorded: dict[str, object] = {}
    monkeypatch.setattr(
        access_service,
        "record_explore_search_event",
        lambda **kwargs: recorded.update(kwargs),
    )
    actor = ExploreActor(
        tier=ExploreTier.USER,
        subject_type="user",
        subject_key="internal-user",
        user_id="internal-user",
    )

    access_service.record_allowed_explore_attempt(
        actor,
        topic_hash="topic_hash",
        quota_bypassed=True,
    )

    assert recorded["outcome"] == str(ExploreAccessOutcome.ALLOWED_INTERNAL)


def test_has_search_quota_bypass_matches_normalized_email(monkeypatch) -> None:
    monkeypatch.setattr(
        access_policy,
        "SEARCH_QUOTA_BYPASS_USER_EMAILS",
        ("faustrare@gmail.com",),
    )

    assert access_policy.has_search_quota_bypass(" FaustRare@Gmail.com ") is True
    assert access_policy.has_search_quota_bypass("other@example.com") is False


def test_verify_turnstile_token_rejects_empty_response_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(turnstile_service, "TURNSTILE_ENABLED", True)

    result = turnstile_service.verify_turnstile_token("")

    assert result.success is False
    assert result.error_codes == ("missing-input-response",)
