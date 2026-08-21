"""Explore access control tests."""

from __future__ import annotations

from fastapi import Request

from app.models import ExploreActor, ExploreTier
from app.services.search import access as access_service
from app.services.search.policy import should_require_turnstile
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
    monkeypatch.setattr("app.services.search.policy.TURNSTILE_ENABLED", True)
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
    monkeypatch.setattr("app.services.search.policy.TURNSTILE_ENABLED", True)
    monkeypatch.setattr(access_service, "count_global_explore_events_since", lambda **kwargs: 0)
    monkeypatch.setattr(access_service, "get_last_explore_event_at", lambda **kwargs: None)
    monkeypatch.setattr(access_service, "count_explore_events_since", lambda **kwargs: 0)

    actor = ExploreActor(
        tier=ExploreTier.SUSPICIOUS,
        subject_type="guest_ip",
        subject_key="guest_hash",
    )

    decision = access_service.check_explore_access(actor, turnstile_verified=True)

    assert decision.allowed is True


def test_verify_turnstile_token_rejects_empty_response_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(turnstile_service, "TURNSTILE_ENABLED", True)

    result = turnstile_service.verify_turnstile_token("")

    assert result.success is False
    assert result.error_codes == ("missing-input-response",)
