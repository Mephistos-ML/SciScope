"""Web API tests for the FastAPI backend transport."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import Response
from fastapi.testclient import TestClient

from tests.conftest import build_test_database_url, migrate_test_database
from app.api.app import app
from app.config import AUTH_SESSION_COOKIE_NAME
from app.models.ai import AiSearchPlan
from app.models.explore_access import ExploreAccessDecision, ExploreActor, ExploreLimitCode, ExploreTier
from app.models.repository import Repository
from app.models.signal import Signal
from app.runtime.state import STATE
from app.services.auth import create_authenticated_session
from app.services.auth import service as auth_service
from app.services import runtime
from app.services.security.turnstile import TurnstileVerificationResult
from app.sources.common import RepositorySourceError
from app.storage import auth as auth_storage
from app.storage import repositories as repository_storage
from app.storage import subscriptions as subscription_storage
from app.storage.subscriptions import SubscriptionWatchRecord


def _build_raw_signal(item_id: str) -> Signal:
    return Signal(
        source="github",
        kind="release",
        item_id=item_id,
        title="Mephistos-ML/paranmr release v0.3.0",
        url=f"https://github.com/Mephistos-ML/paranmr/releases/tag/{item_id}",
        published_at=None,
        raw_text="Adds PCS tensor fitting improvements.",
        payload={
            "repo": "Mephistos-ML/paranmr",
            "files": ["paranmr/core/fitting/tensor.py"],
        },
    )


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


def _build_subscription_watch() -> SubscriptionWatchRecord:
    return SubscriptionWatchRecord(
        subscription_id="sub_pnmr",
        user_id="user_test",
        repository=Repository(
            repository_id="github:repo:Mephistos-ML/paranmr",
            source="github",
            full_name="Mephistos-ML/paranmr",
            url="https://github.com/Mephistos-ML/paranmr",
            metadata={"repo": "Mephistos-ML/paranmr", "stars": 14},
        ),
        selected_query="paramagnetic nmr",
        created_at="2026-08-14T10:00:00+00:00",
    )


def _build_ready_repository_ai_plan(*queries: str) -> AiSearchPlan:
    return AiSearchPlan(
        status="ready" if queries else "pending",
        queries=queries,
    )


def _allow_explore_access(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.explore.get_current_user",
        lambda request: None,
    )
    monkeypatch.setattr(
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user: ExploreActor(
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
        "app.api.routes.explore.check_explore_access",
        lambda actor, turnstile_verified=False: ExploreAccessDecision(allowed=True),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.record_allowed_explore_attempt",
        lambda actor, *, topic_hash: None,
    )


def test_status_and_signal_endpoints_return_json(monkeypatch) -> None:
    STATE.signals.clear()
    STATE.monitoring_started_at = None
    STATE.last_scan_at = None
    STATE.last_scan_error = None
    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.clear()
    STATE.auto_scan_thread = None

    monkeypatch.setattr(runtime, "list_all_subscription_watches", lambda: [_build_subscription_watch()])
    monkeypatch.setattr(runtime, "load_replay_signals", lambda: [_build_raw_signal("demo")])
    monkeypatch.setattr(runtime, "load_repository_signals", lambda subscription_id, repository: [])
    monkeypatch.setattr(runtime, "list_repository_checkpoints", lambda subscription_id, repository_id: [])
    monkeypatch.setattr(runtime, "load_seen_signal_ids", lambda source: set())
    monkeypatch.setattr(runtime, "upsert_signals", lambda signals: None)

    runtime.run_scan_cycle()

    with TestClient(app) as client:
        response = client.get("/api/status")
        assert response.status_code == 200
        status_payload = response.json()
        assert status_payload["subscriptionCount"] == 1
        assert status_payload["watchedRepositories"][0]["fullName"] == "Mephistos-ML/paranmr"
        assert status_payload["sourceCheckpoints"] == []
        assert status_payload["totalSignals"] == 1

        response = client.get("/api/signals")
        assert response.status_code == 200
        signal_list = response.json()
        assert len(signal_list["items"]) == 1
        assert signal_list["items"][0]["subscriptionId"] == "sub_pnmr"

        response = client.get("/api/signals/demo")
        assert response.status_code == 200
        detail_payload = response.json()
        assert detail_payload["itemId"] == "demo"
        assert detail_payload["repositoryId"] == "github:repo:Mephistos-ML/paranmr"


def test_root_health_and_ready_endpoints() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "sciscope-api"
        assert "/api/signals" in payload["endpoints"]
        assert "/ready" in payload["endpoints"]

        response = client.get("/health")
        assert response.status_code == 200
        assert response.text == "ok"

        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_api_start_and_stop_endpoints_return_status_json(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.control.start_monitoring", lambda: None)
    monkeypatch.setattr("app.api.routes.control.stop_monitoring", lambda: None)
    monkeypatch.setattr(
        "app.api.routes.control.get_status_payload",
        lambda: {
            "subscriptionCount": 1,
            "subscriptions": [],
            "autoScanStarted": True,
            "autoScanIntervalSeconds": 300,
            "monitoringIntervalSeconds": 300,
            "lastScanAt": None,
            "lastScanError": None,
            "watchedRepositories": [],
            "sourceCheckpoints": [],
            "totalSignals": 0,
        },
    )

    with TestClient(app) as client:
        start_response = client.post("/api/start")
        stop_response = client.post("/api/stop")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert start_response.json()["subscriptionCount"] == 1
    assert stop_response.json()["subscriptionCount"] == 1


def test_missing_signal_returns_404_json() -> None:
    STATE.signals.clear()

    with TestClient(app) as client:
        response = client.get("/api/signals/missing")

    assert response.status_code == 404
    assert response.json()["error"] == "Signal not found"


def test_session_auth_and_subscription_endpoints(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "subscriptions.sqlite3")
        migrate_test_database(database_url)
        monkeypatch.setattr(auth_storage, "DATABASE_URL", database_url)
        monkeypatch.setattr(subscription_storage, "DATABASE_URL", database_url)
        monkeypatch.setattr(repository_storage, "DATABASE_URL", database_url)
        monkeypatch.setattr(
            "app.services.subscriptions.service.sync_repository_baseline",
            lambda subscription_id, repository: None,
        )

        with TestClient(app) as client:
            response = client.get("/api/subscriptions")
            assert response.status_code == 401

            user = auth_storage.create_user(
                user_id="user_test_subscriptions",
                email="test@example.com",
                display_name="Test User",
                database_url=database_url,
            )
            session_response = Response()
            session_token = create_authenticated_session(user.user_id, session_response)
            client.cookies.set(AUTH_SESSION_COOKIE_NAME, session_token)

            response = client.post(
                "/api/subscriptions",
                json={
                    "repository": {
                        "itemId": "github:repo:Mephistos-ML/paranmr",
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
                == "github:repo:Mephistos-ML/paranmr"
            )

            subscription_id = listed["items"][0]["subscriptionId"]
            response = client.delete(f"/api/subscriptions/{subscription_id}")
            assert response.status_code == 200
            assert response.json() == {"deleted": True}

            response = client.get("/api/subscriptions")
            assert response.status_code == 200
            assert response.json()["items"] == []


def test_google_auth_start_redirects_to_google(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(auth_service, "GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setattr(
        auth_service,
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://api.sciscope.uk/api/auth/google/callback",
    )
    monkeypatch.setattr(auth_service, "FRONTEND_BASE_URL", "https://sciscope.uk")

    with TestClient(app) as client:
        response = client.get("/api/auth/google/start", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "https://accounts.google.com/o/oauth2/v2/auth?"
    )


def test_google_auth_callback_creates_user_session(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "google-auth.sqlite3")
        migrate_test_database(database_url)
        monkeypatch.setattr(auth_storage, "DATABASE_URL", database_url)
        monkeypatch.setattr(auth_service, "GOOGLE_CLIENT_ID", "google-client-id")
        monkeypatch.setattr(auth_service, "GOOGLE_CLIENT_SECRET", "google-client-secret")
        monkeypatch.setattr(
            auth_service,
            "GOOGLE_OAUTH_REDIRECT_URI",
            "https://api.sciscope.uk/api/auth/google/callback",
        )
        monkeypatch.setattr(auth_service, "FRONTEND_BASE_URL", "https://sciscope.uk")

        monkeypatch.setattr(
            auth_service,
            "_exchange_google_code_for_tokens",
            lambda code: {"id_token": "fake-id-token"},
        )
        monkeypatch.setattr(
            auth_service,
            "_verify_google_identity",
            lambda id_token, *, expected_nonce: auth_service.GoogleIdentity(
                subject="google-subject-123",
                email="scientist@example.com",
                display_name="Research Scientist",
                avatar_url="https://example.com/avatar.png",
            ),
        )

        with TestClient(app) as client:
            client.cookies.set(auth_service.GOOGLE_OAUTH_STATE_COOKIE_NAME, "state-123")
            client.cookies.set(auth_service.GOOGLE_OAUTH_NONCE_COOKIE_NAME, "nonce-123")

            callback_response = client.get(
                "/api/auth/google/callback?state=state-123&code=good-code",
                follow_redirects=False,
            )

            assert callback_response.status_code == 302
            assert callback_response.headers["location"] == "https://sciscope.uk"
            assert client.get("/api/me").json()["user"]["email"] == "scientist@example.com"


def test_google_auth_callback_redirects_with_error_when_state_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(auth_service, "GOOGLE_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(auth_service, "GOOGLE_CLIENT_SECRET", "google-client-secret")
    monkeypatch.setattr(
        auth_service,
        "GOOGLE_OAUTH_REDIRECT_URI",
        "https://api.sciscope.uk/api/auth/google/callback",
    )
    monkeypatch.setattr(auth_service, "FRONTEND_BASE_URL", "https://sciscope.uk")

    with TestClient(app) as client:
        client.cookies.set(auth_service.GOOGLE_OAUTH_STATE_COOKIE_NAME, "expected-state")
        client.cookies.set(auth_service.GOOGLE_OAUTH_NONCE_COOKIE_NAME, "expected-nonce")

        response = client.get(
            "/api/auth/google/callback?state=wrong-state&code=good-code",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert (
        response.headers["location"]
        == "https://sciscope.uk?authError=google_state_mismatch"
    )


def test_explore_search_returns_partial_results_when_one_source_fails(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_github_repository_candidates",
        lambda queries: [
            _build_explore_repository_signal(
                "github:repo:Mephistos-ML/paranmr",
                query=queries[0],
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_github_repository_candidates_from_readme",
        lambda queries: [],
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_gitlab_repository_candidates",
        lambda queries: (_ for _ in ()).throw(
            RepositorySourceError(
                source="gitlab",
                status="unauthorized",
                public_message="GitLab auth failed.",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_gitlab_repository_candidates_from_readme",
        lambda queries: (_ for _ in ()).throw(
            RepositorySourceError(
                source="gitlab",
                status="unauthorized",
                public_message="GitLab auth failed.",
            )
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
    assert payload["sourceStatuses"][0]["source"] == "github"
    assert payload["sourceStatuses"][1]["status"] == "unauthorized"


def test_explore_search_returns_502_when_all_sources_fail(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_github_repository_candidates",
        lambda queries: (_ for _ in ()).throw(
            RepositorySourceError(
                source="github",
                status="unauthorized",
                public_message="GitHub auth failed.",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_github_repository_candidates_from_readme",
        lambda queries: (_ for _ in ()).throw(
            RepositorySourceError(
                source="github",
                status="unauthorized",
                public_message="GitHub auth failed.",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_gitlab_repository_candidates",
        lambda queries: (_ for _ in ()).throw(
            RepositorySourceError(
                source="gitlab",
                status="error",
                public_message="GitLab failed.",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_gitlab_repository_candidates_from_readme",
        lambda queries: (_ for _ in ()).throw(
            RepositorySourceError(
                source="gitlab",
                status="error",
                public_message="GitLab failed.",
            )
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
        lambda request: None,
    )
    monkeypatch.setattr(
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user: ExploreActor(
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
        "app.api.routes.explore.check_explore_access",
        lambda actor, turnstile_verified=False: ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.GUEST_COOLDOWN,
            message="Please wait 30 seconds before running another search.",
            retry_after_seconds=30,
            sign_in_suggested=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.record_blocked_explore_attempt",
        lambda actor, decision, *, topic_hash: None,
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
        lambda request: None,
    )
    monkeypatch.setattr(
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user: ExploreActor(
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
        "app.api.routes.explore.check_explore_access",
        lambda actor, turnstile_verified=False: ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.TURNSTILE_REQUIRED,
            message="Please complete the verification challenge before continuing.",
            turnstile_required=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.record_blocked_explore_attempt",
        lambda actor, decision, *, topic_hash: None,
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
        lambda request: None,
    )
    monkeypatch.setattr(
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user: ExploreActor(
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
        "app.api.routes.explore.verify_turnstile_token",
        lambda token, *, remote_ip=None: TurnstileVerificationResult(success=True),
    )

    def _check_access(actor, turnstile_verified=False):
        assert turnstile_verified is True
        return ExploreAccessDecision(allowed=True)

    monkeypatch.setattr("app.api.routes.explore.check_explore_access", _check_access)
    monkeypatch.setattr(
        "app.api.routes.explore.record_allowed_explore_attempt",
        lambda actor, *, topic_hash: None,
    )
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_github_repository_candidates",
        lambda queries: [
            _build_explore_repository_signal(
                "github:repo:Mephistos-ML/paranmr",
                query=queries[0],
            )
        ],
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_github_repository_candidates_from_readme",
        lambda queries: [],
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_gitlab_repository_candidates",
        lambda queries: [],
    )
    monkeypatch.setattr(
        "app.services.search.explore.discover_gitlab_repository_candidates_from_readme",
        lambda queries: [],
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
    assert response.json()["items"][0]["itemId"] == "github:repo:Mephistos-ML/paranmr"
