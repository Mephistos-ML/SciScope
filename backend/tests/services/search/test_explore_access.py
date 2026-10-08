"""Explore access control tests."""

from __future__ import annotations

import pytest

from app.models.explore_access import ExploreAccessOutcome, ExploreActor, ExploreTier, ExploreUsage
from app.services.search.access import service as access_service
from app.services.search.access import policy as access_policy
from app.services.search.access.policy import should_require_turnstile


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

    actor = access_service.resolve_explore_actor(None, client_ip="203.0.113.10", database_url="unused")

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

    decision = access_service.check_explore_access(actor, usage=ExploreUsage(0, 0, None, None))

    assert should_require_turnstile(actor) is True
    assert decision.allowed is False
    assert decision.turnstile_required is True


def test_check_explore_access_allows_verified_turnstile_guest(monkeypatch) -> None:
    monkeypatch.setattr("app.services.search.access.policy.TURNSTILE_ENABLED", True)

    actor = ExploreActor(
        tier=ExploreTier.SUSPICIOUS,
        subject_type="guest_ip",
        subject_key="guest_hash",
    )

    decision = access_service.check_explore_access(actor, turnstile_verified=True, usage=ExploreUsage(0, 0, None, None))

    assert decision.allowed is True


def test_check_explore_access_bypasses_product_quotas_for_internal_actor(
    monkeypatch,
) -> None:
    actor = ExploreActor(
        tier=ExploreTier.USER,
        subject_type="user",
        subject_key="internal-user",
        user_id="internal-user",
    )

    decision = access_service.check_explore_access(actor, bypass_quota=True, usage=ExploreUsage(9999, 9999, None, None))

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
        database_url="unused",
    )

    assert recorded["outcome"] == str(ExploreAccessOutcome.ALLOWED_INTERNAL)


def test_has_search_quota_bypass_matches_normalized_email(monkeypatch) -> None:
    monkeypatch.setattr(
        access_policy,
        "SEARCH_QUOTA_BYPASS_USER_EMAILS",
        ("internal@example.com",),
    )

    assert access_policy.has_search_quota_bypass(" Internal@Example.com ") is True
    assert access_policy.has_search_quota_bypass("other@example.com") is False


@pytest.mark.parametrize("shared_actor", [True, False])
def test_parallel_reservations_do_not_exceed_last_slot(tmp_path, monkeypatch, shared_actor):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from tests.conftest import build_test_database_url, migrate_test_database
    from app.storage.explore import count_global_explore_events_since
    from datetime import UTC, datetime, timedelta

    database_url = build_test_database_url(tmp_path / "parallel-admission.sqlite3")
    migrate_test_database(database_url)
    monkeypatch.setattr(access_policy, "EXPLORE_GUEST_DAILY_LIMIT", 1 if shared_actor else 100)
    monkeypatch.setattr(access_policy, "EXPLORE_GLOBAL_DAILY_LIMIT", 100 if shared_actor else 1)
    monkeypatch.setattr(access_policy, "EXPLORE_GUEST_COOLDOWN_SECONDS", 0)
    barrier = Barrier(8)
    def reserve(index):
        actor = ExploreActor(ExploreTier.GUEST, "guest_ip", "same" if shared_actor else str(index))
        barrier.wait()
        return access_service.reserve_explore_access(actor, topic_hash="topic", database_url=database_url)
    with ThreadPoolExecutor(max_workers=8) as pool:
        decisions = list(pool.map(reserve, range(8)))
    assert sum(decision.allowed for decision in decisions) == 1
    assert count_global_explore_events_since(since=datetime.now(UTC) - timedelta(days=1),
                                            outcomes=("allowed",), database_url=database_url) == 1


def test_failed_reservation_transaction_rolls_back(tmp_path):
    from tests.conftest import build_test_database_url, migrate_test_database
    from app.storage.search_admission import explore_admission_transaction
    from datetime import UTC, datetime, timedelta
    from app.storage.explore import count_global_explore_events_since
    database_url = build_test_database_url(tmp_path / "rollback.sqlite3")
    migrate_test_database(database_url)
    with pytest.raises(RuntimeError, match="abort"):
        with explore_admission_transaction(database_url=database_url) as store:
            store.record_event(user_id=None, subject_type="guest_ip", subject_key="ip", ip_hash="ip",
                               topic_hash="topic", outcome="allowed", created_at=datetime.now(UTC))
            raise RuntimeError("abort")
    assert count_global_explore_events_since(since=datetime.now(UTC) - timedelta(days=1),
                                            outcomes=("allowed",), database_url=database_url) == 0
