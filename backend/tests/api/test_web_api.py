"""Web API tests for the FastAPI backend transport."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient

from tests.conftest import build_test_database_url, migrate_test_database
from app.api.app import app
from app.config import AUTH_SESSION_COOKIE_NAME
from app.models.ai import AiSearchPlan
from app.models.explore_access import ExploreAccessDecision, ExploreActor, ExploreLimitCode, ExploreTier
from app.models.feed import FeedEvent, build_feed_event_id
from app.models.repository import Repository
from app.models.signal import Signal
from app.api import auth as auth_transport
from app.models.auth import User, GoogleIdentity
from app.integrations.identity.google import GoogleOAuthClient
from jwt import PyJWKClient
from app.services.auth.service import create_authenticated_session
from app.models.security import TurnstileVerificationResult
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievalMatchEvidence,
    RetrievalMatchLocation,
    RetrievedCandidates,
)
from app.storage import auth as auth_storage
from app.storage.feed import upsert_feed_events
from app.storage.search_runs import (
    count_search_run_ranking_candidates,
    count_search_run_stages,
    get_search_run_report,
    get_search_run_stage,
)
from app.storage.subscriptions import SubscriptionWatchRecord


@pytest.fixture(autouse=True)
def explore_run_database(tmp_path):
    """Give API scenarios an isolated migrated database instead of relying on missing-table fallback."""

    database_url = build_test_database_url(tmp_path / "explore-runs.sqlite3")
    migrate_test_database(database_url)
    previous_database_url = app.state.database_url
    app.state.database_url = database_url
    try:
        yield database_url
    finally:
        app.state.database_url = previous_database_url


def _build_explore_repository_signal(
    item_id: str,
    *,
    source: str = "github",
    query: str = "paramagnetic nmr",
) -> Signal:
    return Signal(
        source=source,
        kind="repository",
        item_id=item_id,
        title="Mephistos-ML/paranmr",
        url="https://github.com/Mephistos-ML/paranmr",
        published_at=None,
        raw_text=(
            "Mephistos-ML/paranmr\n"
            "Paramagnetic NMR software for susceptibility tensor fitting "
            "and PCS workflows."
        ),
        payload={
            "repo": "Mephistos-ML/paranmr",
            "query": query,
            "topics": ["paramagnetic-nmr", "pcs"],
            "language": "Python",
            "stars": 14,
        },
    )


def _build_code_only_explore_repository_signal(
    item_id: str,
    *,
    source: str = "github",
    query: str = "LAMMPS Feynman-Hibbs",
) -> Signal:
    return Signal(
        source=source,
        kind="repository",
        item_id=item_id,
        title="thermotools/lammps_mie_fh",
        url="https://github.com/thermotools/lammps_mie_fh",
        published_at=None,
        raw_text=(
            "thermotools/lammps_mie_fh\n"
            "A LAMMPS package for Mie-FH simulations.\n"
            "Matched code path: src/pair_mie_fh.cpp"
        ),
        payload={
            "repo": "thermotools/lammps_mie_fh",
            "query": query,
            "topics": ["lammps", "molecular-simulation"],
            "language": "C++",
            "stars": 4,
        },
    )


def _build_subscription_watch() -> SubscriptionWatchRecord:
    return SubscriptionWatchRecord(
        subscription_id="sub_pnmr",
        user_id="user_test",
        repository=Repository(
            repository_id="github:repo:102",
            source="github",
            full_name="Mephistos-ML/paranmr",
            url="https://github.com/Mephistos-ML/paranmr",
            metadata={"repo": "Mephistos-ML/paranmr", "stars": 14},
        ),
        selected_query="paramagnetic nmr",
        created_at="2026-08-14T10:00:00+00:00",
    )


def _build_retrieved_candidates(
    *signals: Signal,
    source_statuses: tuple[dict[str, object], ...],
    successful_source_count: int,
    partial: bool = False,
    warnings: tuple[str, ...] = (),
    matched_channels: tuple[str, ...] = ("repository_search",),
    hit_count: int = 1,
    match_locations: tuple[RetrievalMatchLocation, ...] | None = None,
) -> RetrievedCandidates:
    return RetrievedCandidates(
        candidates=tuple(
            RepositoryCandidate(
                repository_id=signal.item_id,
                signal=signal,
                provenance=CandidateProvenance(
                    matched_queries=(str(signal.payload.get("query") or ""),),
                    matched_channels=matched_channels,
                    best_rank_by_channel={
                        channel_name: 1 for channel_name in matched_channels
                    },
                    hit_count=hit_count,
                    match_evidence=(
                        RetrievalMatchEvidence(
                            query=str(signal.payload.get("query") or ""),
                            location=(
                                (
                                    match_locations[index]
                                    if match_locations is not None
                                    else None
                                )
                                or (
                                    "code"
                                    if "Matched code path:" in signal.raw_text
                                    else "description"
                                )
                            ),
                            channel=matched_channels[0],
                            origin="provider",
                            retrieval_rank=1,
                        ),
                    ),
                ),
            )
            for index, signal in enumerate(signals)
        ),
        source_statuses=source_statuses,
        successful_source_count=successful_source_count,
        partial=partial,
        warnings=warnings,
    )


def _build_ready_repository_ai_plan(*queries: str) -> AiSearchPlan:
    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )


def _allow_explore_access(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.explore.get_current_user",
        lambda request, *, database_url: None,
    )
    monkeypatch.setattr(
        "app.services.search.access.service.resolve_explore_actor",
        lambda user, *, client_ip, database_url: ExploreActor(
            tier=ExploreTier.GUEST,
            subject_type="guest_ip",
            subject_key="guest_hash",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.hash_explore_topic",
        lambda topic_description: "topic_hash",
    )
    monkeypatch.setattr(
        "app.api.routes.explore.reserve_explore_access",
        lambda actor, turnstile_verified=False, bypass_quota=False, *, topic_hash, database_url: ExploreAccessDecision(
            allowed=True
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.jobs.record_explore_admission",
        lambda actor, **kwargs: ExploreAccessDecision(allowed=True),
    )


def _use_search_plan_builder(monkeypatch, build_plan) -> None:
    dependencies = app.state.explore_dependencies
    monkeypatch.setattr(app.state, "explore_dependencies", replace(
        dependencies, planner=replace(dependencies.planner, build_search_plan=build_plan),
    ))


def _process_next_search_run_operation(database_url: str) -> None:
    from app.jobs.process_search_runs import process_next_search_run_operation

    assert process_next_search_run_operation(
        dependencies=app.state.explore_dependencies,
        worker_id="test-worker",
        database_url=database_url,
        lease_seconds=30,
    )


def test_feed_endpoints_return_json() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "api-runtime-test.sqlite3")
        migrate_test_database(database_url)
        user = auth_storage.create_user(
            user_id="user_test",
            email="test@example.com",
            display_name="Test User",
            database_url=database_url,
        )

        upsert_feed_events(
            (
                FeedEvent(
                    event_id=build_feed_event_id(
                        "sub_pnmr",
                        "github",
                        "Mephistos-ML/paranmr:release:demo",
                    ),
                    user_id=user.user_id,
                    subscription_id="sub_pnmr",
                    repository_id="github:repo:102",
                    repository_full_name="Mephistos-ML/paranmr",
                    repository_source="github",
                    repository_url="https://github.com/Mephistos-ML/paranmr",
                    selected_query="paramagnetic nmr",
                    source="github",
                    kind="release",
                    item_id="Mephistos-ML/paranmr:release:demo",
                    title="Mephistos-ML/paranmr release v0.3.0",
                    url="https://github.com/Mephistos-ML/paranmr/releases/tag/demo",
                    published_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
                    raw_text="Adds PCS tensor fitting improvements.",
                    normalized_text="Adds PCS tensor fitting improvements.",
                    created_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
                ),
            ),
            database_url=database_url,
        )

        with TestClient(app) as client:
            client.app.state.database_url = database_url
            session_token = create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600)
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)

            response = client.get("/api/feed")
            assert response.status_code == 200
            feed_list = response.json()
            assert len(feed_list["items"]) == 1
            assert feed_list["items"][0]["subscriptionId"] == "sub_pnmr"
            assert feed_list["items"][0]["repositoryId"] == "github:repo:102"
            assert feed_list["unreadCount"] == 1
            assert feed_list["hasMore"] is False
            assert feed_list["nextCursor"] is None

            event_id = feed_list["items"][0]["eventId"]
            response = client.get(f"/api/feed/{event_id}")
            assert response.status_code == 200
            detail_payload = response.json()
            assert detail_payload["title"] == "Mephistos-ML/paranmr release v0.3.0"
            assert detail_payload["repositoryId"] == "github:repo:102"

            response = client.patch(f"/api/feed/{event_id}")
            assert response.status_code == 200
            assert response.json()["readAt"] is not None

            response = client.get("/api/feed")
            assert response.status_code == 200
            assert response.json()["unreadCount"] == 0


def test_root_health_and_ready_endpoints() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "sciscope-api"
        assert "/api/feed" in payload["endpoints"]
        assert "/ready" in payload["endpoints"]

        response = client.get("/health")
        assert response.status_code == 200
        assert response.text == "ok"

        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_feed_loads_older_events_with_an_opaque_cursor() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "feed-pagination.sqlite3")
        migrate_test_database(database_url)
        user = auth_storage.create_user(
            user_id="user_feed_pagination",
            email="feed-pagination@example.com",
            display_name="Feed Pagination User",
            database_url=database_url,
        )
        newest = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
        upsert_feed_events(
            tuple(
                FeedEvent(
                    event_id=f"event-{index:02d}",
                    user_id=user.user_id,
                    subscription_id="sub_pnmr",
                    repository_id="github:repo:102",
                    repository_full_name="Mephistos-ML/paranmr",
                    repository_source="github",
                    repository_url="https://github.com/Mephistos-ML/paranmr",
                    selected_query="paramagnetic nmr",
                    source="github",
                    kind="release",
                    item_id=f"release-{index:02d}",
                    title=f"Release {index}",
                    url=f"https://github.com/Mephistos-ML/paranmr/releases/tag/{index}",
                    published_at=newest - timedelta(minutes=index),
                    raw_text=f"Release {index}",
                    normalized_text=f"Release {index}",
                    created_at=newest - timedelta(minutes=index),
                )
                for index in range(21)
            ),
            database_url=database_url,
        )

        with TestClient(app) as client:
            client.app.state.database_url = database_url
            session_token = create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600)
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)

            first_response = client.get("/api/feed?limit=20")
            assert first_response.status_code == 200
            first_page = first_response.json()
            assert len(first_page["items"]) == 20
            assert first_page["hasMore"] is True
            assert isinstance(first_page["nextCursor"], str)

            second_response = client.get(
                "/api/feed",
                params={"limit": 20, "cursor": first_page["nextCursor"]},
            )

    assert second_response.status_code == 200
    second_page = second_response.json()
    assert len(second_page["items"]) == 1
    assert second_page["hasMore"] is False
    assert second_page["nextCursor"] is None
    assert {
        item["eventId"] for item in first_page["items"]
    }.isdisjoint({item["eventId"] for item in second_page["items"]})


def test_missing_feed_event_returns_404_json() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "feed-missing.sqlite3")
        migrate_test_database(database_url)
        user = auth_storage.create_user(
            user_id="user_test_feed",
            email="feed@example.com",
            display_name="Feed User",
            database_url=database_url,
        )

        with TestClient(app) as client:
            client.app.state.database_url = database_url
            session_token = create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600)
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)
            response = client.get("/api/feed/missing")

    assert response.status_code == 404
    assert response.json()["error"] == "Feed event not found"


def test_session_auth_and_subscription_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(app.state, "load_repository_profile", lambda repository_id: Repository(
        repository_id=repository_id, source="github", provider_repository_id="123",
        full_name="Mephistos-ML/paranmr", url="https://github.com/Mephistos-ML/paranmr",
    ))
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "subscriptions.sqlite3")
        migrate_test_database(database_url)
        with TestClient(app) as client:
            client.app.state.database_url = database_url
            response = client.get("/api/subscriptions")
            assert response.status_code == 401

            user = auth_storage.create_user(
                user_id="user_test_subscriptions",
                email="test@example.com",
                display_name="Test User",
                database_url=database_url,
            )
            session_token = create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600)
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)

            response = client.post(
                "/api/subscriptions",
                json={
                    "repository": {
                            "itemId": "github:repo:123",
                        "source": "github",
                        "fullName": "Mephistos-ML/paranmr",
                        "url": "https://github.com/Mephistos-ML/paranmr",
                    },
                    "selectedQuery": "paramagnetic nmr",
                },
            )
            assert response.status_code == 201
            created = response.json()
            assert created["repository"]["fullName"] == "Mephistos-ML/paranmr"
            assert created["selectedQuery"] == "paramagnetic nmr"

            response = client.get("/api/subscriptions")
            assert response.status_code == 200
            listed = response.json()
            assert len(listed["items"]) == 1
            assert (
                listed["items"][0]["repository"]["repositoryId"]
                == "github:repo:123"
            )

            subscription_id = listed["items"][0]["subscriptionId"]
            response = client.delete(f"/api/subscriptions/{subscription_id}")
            assert response.status_code == 200
            assert response.json() == {"deleted": True}

            response = client.get("/api/subscriptions")
            assert response.status_code == 200
            assert response.json()["items"] == []


def _configure_google_auth(monkeypatch):
    monkeypatch.setattr(auth_transport, "FRONTEND_BASE_URL", "https://sciscope.uk")
    monkeypatch.setattr(app.state, "google_oauth", GoogleOAuthClient(
        "google-client-id", "google-client-secret",
        "https://api.sciscope.uk/api/auth/google/callback", PyJWKClient("https://example.test/jwks"),
    ))


def test_google_auth_start_redirects_to_google(monkeypatch) -> None:

    _configure_google_auth(monkeypatch)
    with TestClient(app) as client:
        response = client.get("/api/auth/google/start", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://accounts.google.com/o/oauth2/v2/auth?"
    )


def test_google_auth_callback_creates_user_session(monkeypatch) -> None:
    _configure_google_auth(monkeypatch)
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "google-auth.sqlite3")
        migrate_test_database(database_url)


        monkeypatch.setattr(
            GoogleOAuthClient, "authenticate",
            lambda self, code, *, expected_nonce: GoogleIdentity(
                subject="google-subject-123", email="scientist@example.com",
                display_name="Research Scientist", avatar_url="https://example.com/avatar.png",
            ),
        )
        with TestClient(app) as client:
            client.app.state.database_url = database_url
            client.cookies.set(auth_transport.GOOGLE_OAUTH_STATE_COOKIE_NAME, "state-123", domain="testserver.local")
            client.cookies.set(auth_transport.GOOGLE_OAUTH_NONCE_COOKIE_NAME, "nonce-123", domain="testserver.local")

            callback_response = client.get(
                "/api/auth/google/callback?state=state-123&code=good-code",
                follow_redirects=False,
            )

            assert callback_response.status_code == 302
            assert callback_response.headers["location"] == "https://sciscope.uk"
            session_cookie = next(value for value in callback_response.headers.get_list("set-cookie")
                                  if value.startswith(AUTH_SESSION_COOKIE_NAME + "="))
            assert "HttpOnly" in session_cookie and "Path=/" in session_cookie
            assert "SameSite=" in session_cookie and "Max-Age=" in session_cookie
            assert auth_transport.GOOGLE_OAUTH_STATE_COOKIE_NAME not in client.cookies
            assert auth_transport.GOOGLE_OAUTH_NONCE_COOKIE_NAME not in client.cookies
            assert client.get("/api/me").json()["user"]["email"] == "scientist@example.com"


def test_get_me_exposes_enabled_search_diagnostics_feature(monkeypatch) -> None:
    user = User(
        user_id="user_diagnostics",
        email="diagnostics@example.com",
        display_name="Diagnostics User",
    )
    monkeypatch.setattr(
        "app.api.routes.auth.get_current_user",
        lambda request, *, database_url: user,
    )
    monkeypatch.setattr(
        "app.services.features.access.SEARCH_DIAGNOSTICS_USER_EMAILS",
        ("diagnostics@example.com",),
    )

    with TestClient(app) as client:
        response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["user"]["features"] == ["search_diagnostics"]


def test_search_diagnostics_report_requires_feature_access(monkeypatch) -> None:
    user = User(
        user_id="user_diagnostics",
        email="diagnostics@example.com",
        display_name="Diagnostics User",
    )
    monkeypatch.setattr(
        "app.api.routes.run_reports.get_current_user",
        lambda request, *, database_url: user,
    )
    monkeypatch.setattr(
        "app.api.routes.run_reports.has_feature",
        lambda _email, _feature: False,
    )

    with TestClient(app) as client:
        response = client.get("/api/internal/search-runs/run_1/report")

    assert response.status_code == 403
    assert response.json()["error"] == "Search diagnostics access is required."


def test_search_diagnostics_report_rejects_another_users_run(monkeypatch) -> None:
    user = User(
        user_id="user_diagnostics",
        email="diagnostics@example.com",
        display_name="Diagnostics User",
    )
    monkeypatch.setattr(
        "app.api.routes.run_reports.get_current_user",
        lambda request, *, database_url: user,
    )
    monkeypatch.setattr(
        "app.api.routes.run_reports.has_feature",
        lambda _email, _feature: True,
    )

    def reject_other_users_run(**_kwargs) -> None:
        raise PermissionError("This search run does not belong to the current user.")

    monkeypatch.setattr(
        "app.api.routes.run_reports.read_search_run_report",
        reject_other_users_run,
    )

    with TestClient(app) as client:
        response = client.get("/api/internal/search-runs/run_1/report")

    assert response.status_code == 403
    assert response.json()["error"] == "This search run does not belong to the current user."


def test_search_diagnostics_report_returns_owners_run(monkeypatch) -> None:
    user = User(
        user_id="user_diagnostics",
        email="diagnostics@example.com",
        display_name="Diagnostics User",
    )
    report = {"run": {"runId": "run_1", "ownerUserId": user.user_id}, "stages": []}
    monkeypatch.setattr(
        "app.api.routes.run_reports.get_current_user",
        lambda request, *, database_url: user,
    )
    monkeypatch.setattr(
        "app.api.routes.run_reports.has_feature",
        lambda _email, _feature: True,
    )
    monkeypatch.setattr(
        "app.api.routes.run_reports.read_search_run_report",
        lambda **_kwargs: report,
    )

    with TestClient(app) as client:
        response = client.get("/api/internal/search-runs/run_1/report")

    assert response.status_code == 200
    assert response.json() == report


def test_explore_search_bypasses_quota_for_internal_email(monkeypatch) -> None:
    user = User(
        user_id="user_internal",
        email="internal@example.com",
        display_name="Internal User",
    )
    recorded: dict[str, object] = {}
    monkeypatch.setattr(
        "app.api.routes.explore.get_current_user",
        lambda request, *, database_url: user,
    )
    monkeypatch.setattr(
        "app.services.search.access.service.resolve_explore_actor",
        lambda user, *, client_ip, database_url: ExploreActor(
            tier=ExploreTier.USER,
            subject_type="user",
            subject_key="user_internal",
            user_id="user_internal",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.hash_explore_topic",
        lambda topic_description: "topic_hash",
    )
    monkeypatch.setattr(
        "app.services.search.access.policy.SEARCH_QUOTA_BYPASS_USER_EMAILS",
        ("internal@example.com",),
    )

    def check_access(actor, turnstile_verified=False, bypass_quota=False, *, topic_hash, database_url):
        assert bypass_quota is True
        recorded.update(topic_hash=topic_hash, quota_bypassed=bypass_quota)
        return ExploreAccessDecision(allowed=True)

    monkeypatch.setattr("app.api.routes.explore.reserve_explore_access", check_access)
    monkeypatch.setattr(
        "app.api.routes.explore.run_explore_search",
        lambda **kwargs: {"items": []},
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

    assert response.status_code == 200
    assert recorded == {"topic_hash": "topic_hash", "quota_bypassed": True}


def test_google_auth_callback_redirects_with_error_when_state_is_invalid(monkeypatch) -> None:

    _configure_google_auth(monkeypatch)
    with TestClient(app) as client:
        client.cookies.set(auth_transport.GOOGLE_OAUTH_STATE_COOKIE_NAME, "expected-state", domain="testserver.local")
        client.cookies.set(auth_transport.GOOGLE_OAUTH_NONCE_COOKIE_NAME, "expected-nonce", domain="testserver.local")

        response = client.get(
            "/api/auth/google/callback?state=wrong-state&code=good-code",
            follow_redirects=False,
        )
        assert auth_transport.GOOGLE_OAUTH_STATE_COOKIE_NAME not in client.cookies
        assert auth_transport.GOOGLE_OAUTH_NONCE_COOKIE_NAME not in client.cookies
        assert AUTH_SESSION_COOKIE_NAME not in client.cookies

    assert response.status_code == 302
    assert (
        response.headers["location"]
        == "https://sciscope.uk?authError=google_state_mismatch"
    )


def test_explore_search_returns_partial_results_when_one_source_fails(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:102",
                query=queries[0],
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
                {
                    "source": "gitlab",
                    "status": "unauthorized",
                    "candidateCount": 0,
                    "error": "GitLab auth failed.",
                },
            ),
            successful_source_count=1,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["aiSearchPlan"] == {"status": "ready", "queries": []}
    assert payload["sourceStatuses"][0]["source"] == "github"
    assert payload["sourceStatuses"][1]["status"] == "unauthorized"


def test_explore_search_refreshes_external_candidates_after_a_strong_catalog_match(
    monkeypatch,
) -> None:
    _allow_explore_access(monkeypatch)
    query = "paramagnetic nmr"
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(query),
    )
    local_candidates = _build_retrieved_candidates(
        *(
            _build_explore_repository_signal(
                f"github:repo:catalog-{index}",
                query=query,
            )
            for index in range(10)
        ),
        source_statuses=(),
        successful_source_count=1,
    ).candidates
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: local_candidates,
    )
    external_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: (
            external_calls.append(queries)
            or _build_retrieved_candidates(
                _build_explore_repository_signal(
                    "github:repo:external-paranmr",
                    query=queries[0],
                ),
                source_statuses=(
                    {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
                ),
                successful_source_count=1,
            )
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

    assert response.status_code == 200
    assert external_calls == [(query,)]


def test_explore_search_keeps_retrieved_candidate_without_literal_query_phrase(
    monkeypatch,
) -> None:
    _allow_explore_access(monkeypatch)
    query = "LAMMPS Feynman-Hibbs"
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(query),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: RetrievedCandidates(
            candidates=(
                RepositoryCandidate(
                    repository_id="github:repo:115",
                    signal=_build_code_only_explore_repository_signal(
                        "github:repo:115",
                        query=queries[0],
                    ),
                    provenance=CandidateProvenance(
                        matched_queries=(queries[0],),
                        matched_channels=("code_search",),
                        best_rank_by_channel={"code_search": 1},
                        hit_count=1,
                        match_evidence=(
                            RetrievalMatchEvidence(
                                query=queries[0],
                                location="code",
                                path="src/pair_mie_fh.cpp",
                            ),
                        ),
                    ),
                ),
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={
                "topicDescription": (
                    "LAMMPS extension for Feynman-Hibbs corrected Mie pair potentials"
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["itemId"] == "github:repo:115"
    assert payload["items"][0]["score"] >= 50.0


def test_explore_search_applies_ranking_order_and_relevance_cutoff(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    queries = (
        "lammps feynman-hibbs",
        "feynman-hibbs mie potential",
        "quantum-corrected mie potential",
        "lammps pair style mie",
        "semiclassical correction",
    )
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(*queries),
    )
    top_signal = _build_explore_repository_signal(
        "github:repo:108",
        query=queries[0],
    )
    top_signal = Signal(
        source=top_signal.source,
        kind=top_signal.kind,
        item_id=top_signal.item_id,
        title="science/feynman-hibbs-mie",
        url=top_signal.url,
        published_at=top_signal.published_at,
        raw_text=top_signal.raw_text,
        payload=top_signal.payload,
    )
    metadata_signal = _build_explore_repository_signal(
        "github:repo:110",
        query=queries[0],
    )
    weak_signal = _build_explore_repository_signal(
        "github:repo:109",
        query=queries[0],
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda _queries, **kwargs: _build_retrieved_candidates(
            top_signal,
            metadata_signal,
            weak_signal,
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 3, "error": None},
            ),
            successful_source_count=1,
            match_locations=("name", "description", "other"),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "LAMMPS Feynman-Hibbs Mie potential"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["itemId"] for item in payload["items"]] == [
        top_signal.item_id,
        metadata_signal.item_id,
    ]


def test_explore_search_enforced_mode_hides_rejected_candidates(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    monkeypatch.setattr(
        "app.services.search.admission.service.EXPLORE_ADMISSION_MODE",
        "enforced",
    )
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("orca parser"),
    )
    weak_signal = Signal(
        source="github",
        kind="repository",
        item_id="github:repo:101",
        title="HeinrichHartmann/arxiv_meta",
        url="https://github.com/HeinrichHartmann/arxiv_meta",
        published_at=None,
        raw_text="HeinrichHartmann/arxiv_meta\nArxiv metadata mirror.",
        payload={
            "repo": "HeinrichHartmann/arxiv_meta",
            "query": "orca parser",
            "topics": ["metadata"],
            "language": "",
            "stars": 0,
        },
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: _build_retrieved_candidates(
            _build_code_only_explore_repository_signal(
                "github:repo:115",
                query=queries[0],
            ),
            weak_signal,
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 2, "error": None},
            ),
            successful_source_count=1,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "A python package for working with Orca."},
        )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["itemId"] == "github:repo:115"
    assert "admission" not in payload


def test_explore_search_retries_timeouts_before_advancing_to_next_query(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(
            "primary query",
            "fallback query",
            "final query",
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: (),
    )
    attempted_queries: list[str] = []

    def _retrieve(queries, **_kwargs):
        query = queries[0]
        attempted_queries.append(query)
        if query == "primary query":
            return _build_retrieved_candidates(
                source_statuses=(
                    {
                        "source": "github",
                        "status": "timed_out",
                        "candidateCount": 0,
                        "error": "GitHub search timed out.",
                    },
                ),
                successful_source_count=0,
                partial=True,
                warnings=("GitHub search timed out.",),
            )
        return _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:107",
                query=query,
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
        )

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Fallback workflow"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["itemId"] == "github:repo:107"
    assert payload["canExpand"] is True
    assert attempted_queries == [
        "primary query",
        "primary query",
        "primary query",
        "fallback query",
    ]


def test_explore_search_retries_partial_timeouts_and_merges_attempt_results(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(
            "primary query",
            "fallback query",
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: (),
    )
    attempted_queries: list[str] = []
    attempt_results = iter(
        (
            _build_retrieved_candidates(
                _build_explore_repository_signal(
                    "github:repo:112",
                    query="primary query",
                ),
                source_statuses=(
                    {
                        "source": "github",
                        "status": "ok",
                        "candidateCount": 1,
                        "error": None,
                    },
                ),
                successful_source_count=1,
                partial=True,
                warnings=("GitHub search timed out after partial results.",),
            ),
            _build_retrieved_candidates(
                _build_explore_repository_signal(
                    "github:repo:113",
                    query="primary query",
                ),
                source_statuses=(
                    {
                        "source": "github",
                        "status": "ok",
                        "candidateCount": 1,
                        "error": None,
                    },
                ),
                successful_source_count=1,
                partial=True,
                warnings=("GitHub search timed out after partial results.",),
            ),
            _build_retrieved_candidates(
                _build_explore_repository_signal(
                    "github:repo:106",
                    query="primary query",
                ),
                source_statuses=(
                    {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
                ),
                successful_source_count=1,
            ),
        )
    )

    def _retrieve(queries, **_kwargs):
        attempted_queries.append(queries[0])
        return next(attempt_results)

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Partial timeout workflow"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert attempted_queries == ["primary query", "primary query", "primary query"]
    assert {
        item["itemId"] for item in payload["items"]
    } == {
        "github:repo:112",
        "github:repo:113",
        "github:repo:106",
    }


def test_explore_search_run_fails_after_all_timeout_retries_are_exhausted(
    monkeypatch, explore_run_database
) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(
            "primary query",
            "fallback query",
            "final query",
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.retrieve_catalog_candidates",
        lambda *_, **__: (),
    )
    attempted_queries: list[str] = []

    def _retrieve(queries, **_kwargs):
        attempted_queries.append(queries[0])
        return _build_retrieved_candidates(
            source_statuses=(
                {
                    "source": "github",
                    "status": "timed_out",
                    "candidateCount": 0,
                    "error": "GitHub search timed out.",
                },
            ),
            successful_source_count=0,
            partial=True,
            warnings=("GitHub search timed out.",),
        )

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "Exhausted timeout workflow"},
        )
        client.headers['X-Search-Run-Token'] = response.json()['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        response = client.get(f"/api/explore/search-runs/{response.json()['runId']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error"] == "Repository search is temporarily unavailable across all providers."
    assert attempted_queries == [
        "primary query",
        "primary query",
        "primary query",
        "fallback query",
        "fallback query",
        "fallback query",
        "final query",
        "final query",
        "final query",
    ]


def test_explore_search_rejects_removed_beta_mode(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR", "betaMode": True},
        )

    assert response.status_code == 422


def test_explore_search_returns_502_when_all_sources_fail(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: _build_retrieved_candidates(
            source_statuses=(
                {
                    "source": "github",
                    "status": "unauthorized",
                    "candidateCount": 0,
                    "error": "GitHub auth failed.",
                },
                {
                    "source": "gitlab",
                    "status": "error",
                    "candidateCount": 0,
                    "error": "GitLab failed.",
                },
            ),
            successful_source_count=0,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

    assert response.status_code == 502
    assert "sourceStatuses" in response.json()


def test_explore_search_returns_structured_access_denial_payload(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.explore.get_current_user",
        lambda request, *, database_url: None,
    )
    monkeypatch.setattr(
        "app.services.search.access.service.resolve_explore_actor",
        lambda user, *, client_ip, database_url: ExploreActor(
            tier=ExploreTier.GUEST,
            subject_type="guest_ip",
            subject_key="guest_hash",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.hash_explore_topic",
        lambda topic_description: "topic_hash",
    )
    monkeypatch.setattr(
        "app.api.routes.explore.reserve_explore_access",
        lambda actor, turnstile_verified=False, bypass_quota=False, *, topic_hash, database_url: ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.GUEST_COOLDOWN,
            message="Please wait 30 seconds before running another search.",
            retry_after_seconds=30,
            sign_in_suggested=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.search.access.service.record_blocked_explore_attempt",
        lambda actor, decision, *, topic_hash, database_url: None,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

    assert response.status_code == 429
    payload = response.json()
    assert payload == {
        "error": "Please wait 30 seconds before running another search.",
        "code": "explore_guest_cooldown",
        "signInSuggested": True,
        "turnstileRequired": False,
        "retryAfterSeconds": 30,
    }
    assert response.headers["retry-after"] == "30"


def test_explore_search_returns_turnstile_requirement_payload(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.explore.get_current_user",
        lambda request, *, database_url: None,
    )
    monkeypatch.setattr(
        "app.services.search.access.service.resolve_explore_actor",
        lambda user, *, client_ip, database_url: ExploreActor(
            tier=ExploreTier.SUSPICIOUS,
            subject_type="guest_ip",
            subject_key="guest_hash",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.hash_explore_topic",
        lambda topic_description: "topic_hash",
    )
    monkeypatch.setattr(
        "app.api.routes.explore.reserve_explore_access",
        lambda actor, turnstile_verified=False, bypass_quota=False, *, topic_hash, database_url: ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.TURNSTILE_REQUIRED,
            message="Please complete the verification challenge before continuing.",
            turnstile_required=True,
        ),
    )
    monkeypatch.setattr(
        "app.services.search.access.service.record_blocked_explore_attempt",
        lambda actor, decision, *, topic_hash, database_url: None,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

    assert response.status_code == 403
    assert response.json() == {
        "error": "Please complete the verification challenge before continuing.",
        "code": "explore_turnstile_required",
        "signInSuggested": False,
        "turnstileRequired": True,
    }


def test_explore_search_accepts_verified_turnstile_token_for_suspicious_guest(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.api.routes.explore.get_current_user",
        lambda request, *, database_url: None,
    )
    monkeypatch.setattr(
        "app.services.search.access.service.resolve_explore_actor",
        lambda user, *, client_ip, database_url: ExploreActor(
            tier=ExploreTier.SUSPICIOUS,
            subject_type="guest_ip",
            subject_key="guest_hash",
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.hash_explore_topic",
        lambda topic_description: "topic_hash",
    )
    monkeypatch.setattr(
        "app.api.routes.explore.read_explore_client_ip",
        lambda request: "203.0.113.10",
    )
    monkeypatch.setattr(
        app.state, "verify_turnstile_token",
        lambda token, *, remote_ip=None: TurnstileVerificationResult(success=True),
    )

    def _check_access(actor, turnstile_verified=False, bypass_quota=False, *, topic_hash, database_url):
        assert turnstile_verified is True
        return ExploreAccessDecision(allowed=True)

    monkeypatch.setattr("app.api.routes.explore.reserve_explore_access", _check_access)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:102",
                query=queries[0],
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
                {"source": "gitlab", "status": "ok", "candidateCount": 0, "error": None},
            ),
            successful_source_count=2,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={
                "topicDescription": "Paramagnetic NMR analysis workflows",
                "turnstileToken": "valid-token",
            },
        )

    assert response.status_code == 200
    assert response.json()["items"][0]["itemId"] == "github:repo:102"


def test_explore_search_run_returns_completed_snapshot(
    monkeypatch, explore_run_database
) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(
            "paramagnetic nmr",
            "pcs tensor fitting",
            "pseudocontact shift",
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, progress_callback=None, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:102",
                query=queries[0],
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

        assert response.status_code == 202
        assert response.json()["status"] == "queued"
        client.headers['X-Search-Run-Token'] = response.json()['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        created = client.get(f"/api/explore/search-runs/{response.json()['runId']}").json()
        assert created["status"] == "completed"
        assert created["canExpand"] is True
        assert created["items"][0]["itemId"] == "github:repo:102"
        assert "ownerUserId" not in created

        follow_up = client.get(f"/api/explore/search-runs/{created['runId']}")

    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "completed"
    assert "_execution" not in follow_up.json()
    assert count_search_run_stages(
        created["runId"],
        database_url=explore_run_database,
    ) == 1
    assert count_search_run_ranking_candidates(
        created["runId"],
        database_url=explore_run_database,
    ) == 1
    report = get_search_run_report(
        created["runId"],
        database_url=explore_run_database,
    )
    assert report is not None
    evidence = report["rankingSnapshots"][0]["retrievalFacts"]["match_evidence"][0]
    assert evidence["channel"] == "repository_search"
    assert evidence["origin"] == "provider"
    assert evidence["retrieval_rank"] == 1
    stage = get_search_run_stage(
        created["runId"],
        1,
        database_url=explore_run_database,
    )
    assert stage is not None
    assert set(stage.timings) >= {
        "ai_planning",
        "catalog_retrieval",
        "candidate_merge",
        "admission",
        "ranking",
        "repository_persistence",
        "response_serialization",
        "stage_wall_time",
    }


def test_explore_search_run_expands_one_pending_query_and_merges_candidates(
    monkeypatch, explore_run_database
) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(
            "paramagnetic nmr",
            "pcs tensor fitting",
            "pseudocontact shift",
        ),
    )
    retrieval_queries: list[tuple[str, ...]] = []

    def _retrieve(queries, **_kwargs):
        retrieval_queries.append(tuple(queries))
        return _build_retrieved_candidates(
            _build_explore_repository_signal(
                {'paramagnetic nmr': 'github:repo:111', 'pcs tensor fitting': 'github:repo:114', 'pseudocontact shift': 'github:repo:120'}[queries[0]],
                query=queries[0],
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
        )

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        ).json()
        client.headers['X-Search-Run-Token'] = created['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        created = client.get(f"/api/explore/search-runs/{created['runId']}").json()
        expanded = client.post(
            f"/api/explore/search-runs/{created['runId']}/expand",
        )
        _process_next_search_run_operation(explore_run_database)
        expanded = client.get(f"/api/explore/search-runs/{created['runId']}")

    assert expanded.status_code == 200
    payload = expanded.json()
    assert payload["status"] == "completed"
    assert payload["canExpand"] is True
    assert {item["itemId"] for item in payload["items"]} == {
        "github:repo:111",
        "github:repo:114",
    }
    assert retrieval_queries == [("paramagnetic nmr",), ("pcs tensor fitting",)]


def test_explore_search_expansion_preserves_all_previous_results(
    monkeypatch, explore_run_database
) -> None:
    """Incremental expansion may add candidates but must not remove prior ones."""

    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan(
            "angle one",
            "angle two",
            "angle three",
        ),
    )

    repository_ids = {
        "angle one": "github:repo:103",
        "angle two": "github:repo:105",
        "angle three": "github:repo:104",
    }

    def _retrieve(queries, **_kwargs):
        query = queries[0]
        return _build_retrieved_candidates(
            _build_explore_repository_signal(
                repository_ids[query],
                query=query,
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
        )

    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        _retrieve,
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "Incremental search preservation"},
        ).json()
        client.headers['X-Search-Run-Token'] = created['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        created = client.get(f"/api/explore/search-runs/{created['runId']}").json()
        initial_ids = {item["itemId"] for item in created["items"]}

        first_expansion = client.post(
            f"/api/explore/search-runs/{created['runId']}/expand",
        )
        _process_next_search_run_operation(explore_run_database)
        first_expansion = client.get(f"/api/explore/search-runs/{created['runId']}")
        assert first_expansion.status_code == 200
        first_expansion_ids = {
            item["itemId"] for item in first_expansion.json()["items"]
        }

        second_expansion = client.post(
            f"/api/explore/search-runs/{created['runId']}/expand",
        )
        _process_next_search_run_operation(explore_run_database)
        second_expansion = client.get(f"/api/explore/search-runs/{created['runId']}")
        assert second_expansion.status_code == 200
        second_expansion_ids = {
            item["itemId"] for item in second_expansion.json()["items"]
        }

    assert initial_ids == {"github:repo:103"}
    assert initial_ids <= first_expansion_ids
    assert first_expansion_ids == {
        "github:repo:103",
        "github:repo:105",
    }
    assert first_expansion_ids <= second_expansion_ids
    assert second_expansion_ids == {
        "github:repo:103",
        "github:repo:105",
        "github:repo:104",
    }


def test_explore_search_run_rejects_expansion_after_plan_is_exhausted(
    monkeypatch, explore_run_database
) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:102",
                query=queries[0],
            ),
            source_statuses=(
                {"source": "github", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
        ),
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        ).json()
        client.headers['X-Search-Run-Token'] = created['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        response = client.post(f"/api/explore/search-runs/{created['runId']}/expand")

    assert response.status_code == 409
    assert response.json()["error"] == "Explore search run has no more planned queries."


def test_explore_search_run_returns_failed_snapshot_when_all_sources_fail(
    monkeypatch, explore_run_database
) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("orca parser"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, progress_callback=None, **kwargs: _build_retrieved_candidates(
            source_statuses=(
                {
                    "source": "github",
                    "status": "unauthorized",
                    "candidateCount": 0,
                    "error": "GitHub auth failed.",
                },
                {
                    "source": "gitlab",
                    "status": "error",
                    "candidateCount": 0,
                    "error": "GitLab failed.",
                },
            ),
            successful_source_count=0,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "A python package for working with Orca."},
        )
        client.headers['X-Search-Run-Token'] = response.json()['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        response = client.get(f"/api/explore/search-runs/{response.json()['runId']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["sourceStatuses"][0]["source"] == "github"
    assert payload["error"] == "Repository search is temporarily unavailable across all providers."


def test_explore_search_run_returns_completed_partial_snapshot(
    monkeypatch, explore_run_database
) -> None:
    _allow_explore_access(monkeypatch)
    _use_search_plan_builder(
        monkeypatch,
        lambda topic_description: _build_ready_repository_ai_plan("orca parser"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.service.run_external_repository_retrieval",
        lambda queries, progress_callback=None, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "gitlab:repo:116",
                source="gitlab",
                query=queries[0],
            ),
            source_statuses=(
                {"source": "github", "status": "timed_out", "candidateCount": 0, "error": "GitHub code search timed out."},
                {"source": "gitlab", "status": "ok", "candidateCount": 1, "error": None},
            ),
            successful_source_count=1,
            partial=True,
            warnings=("GitHub code search returned timed_out.",),
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search-runs",
            json={"topicDescription": "A python package for working with Orca."},
        )
        client.headers['X-Search-Run-Token'] = response.json()['guestAccessToken']
        _process_next_search_run_operation(explore_run_database)
        response = client.get(f"/api/explore/search-runs/{response.json()['runId']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed_partial"
    assert payload["items"][0]["itemId"] == "gitlab:repo:116"
    assert "partial coverage" in payload["message"]
