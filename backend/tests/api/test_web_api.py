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
from app.services.search.retrieval.models import (
    CandidateProvenance,
    RepositoryCandidate,
    RetrievedCandidates,
)
from app.storage import auth as auth_storage
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
            repository_id="github:repo:Mephistos-ML/paranmr",
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
) -> RetrievedCandidates:
    return RetrievedCandidates(
        candidates=tuple(
            RepositoryCandidate(
                repository_id=signal.item_id,
                signal=signal,
                provenance=CandidateProvenance(
                    matched_queries=(str(signal.payload.get("query") or ""),),
                    matched_channels=("repository_search",),
                    best_rank_by_channel={"repository_search": 1},
                    hit_count=1,
                ),
            )
            for signal in signals
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
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user, *, database_url: ExploreActor(
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
        lambda actor, turnstile_verified=False, *, database_url: ExploreAccessDecision(
            allowed=True
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.record_allowed_explore_attempt",
        lambda actor, *, topic_hash, database_url: None,
    )


def _run_explore_job_inline(job_id: str, topic_description: str) -> None:
    from app.services.search import jobs as search_jobs

    search_jobs._run_explore_search_job(
        job_id=job_id,
        topic_description=topic_description,
    )


def test_status_and_signal_endpoints_return_json(monkeypatch) -> None:
    STATE.signals.clear()
    STATE.monitoring_started_at = None
    STATE.last_scan_at = None
    STATE.last_scan_error = None
    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.clear()
    STATE.auto_scan_thread = None

    monkeypatch.setattr(
        runtime,
        "list_all_subscription_watches",
        lambda *, database_url: [_build_subscription_watch()],
    )
    monkeypatch.setattr(runtime, "load_replay_signals", lambda: [_build_raw_signal("demo")])
    monkeypatch.setattr(
        runtime,
        "load_repository_signals",
        lambda subscription_id, repository, *, baseline_started_after, database_url: [],
    )
    monkeypatch.setattr(
        runtime,
        "list_repository_checkpoints",
        lambda subscription_id, repository_id, *, database_url: [],
    )
    monkeypatch.setattr(
        runtime,
        "load_seen_signal_ids",
        lambda source, *, database_url: set(),
    )
    monkeypatch.setattr(
        runtime,
        "upsert_signals",
        lambda signals, *, database_url: None,
    )

    runtime.run_scan_cycle(database_url="sqlite:///api-runtime-test.sqlite3")

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
    monkeypatch.setattr(
        "app.api.routes.control.start_monitoring",
        lambda *, database_url: None,
    )
    monkeypatch.setattr(
        "app.api.routes.control.stop_monitoring",
        lambda *, database_url: None,
    )
    monkeypatch.setattr(
        "app.api.routes.control.get_status_payload",
        lambda *, database_url: {
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
        monkeypatch.setattr(
            "app.services.subscriptions.service.sync_repository_baseline",
            lambda subscription_id, repository, *, database_url: None,
        )

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
            session_response = Response()
            session_token = create_authenticated_session(
                user.user_id,
                session_response,
                database_url=database_url,
            )
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
            client.app.state.database_url = database_url
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
        "app.services.search.explore.run_external_repository_retrieval",
        lambda queries: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:Mephistos-ML/paranmr",
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
    assert payload["sourceStatuses"][0]["source"] == "github"
    assert payload["sourceStatuses"][1]["status"] == "unauthorized"


def test_explore_search_keeps_retrieved_candidate_without_literal_query_phrase(
    monkeypatch,
) -> None:
    _allow_explore_access(monkeypatch)
    query = "LAMMPS Feynman-Hibbs"
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan(query),
    )
    monkeypatch.setattr(
        "app.services.search.explore.run_external_repository_retrieval",
        lambda queries: RetrievedCandidates(
            candidates=(
                RepositoryCandidate(
                    repository_id="github:repo:thermotools/lammps_mie_fh",
                    signal=_build_code_only_explore_repository_signal(
                        "github:repo:thermotools/lammps_mie_fh",
                        query=queries[0],
                    ),
                    provenance=CandidateProvenance(
                        matched_queries=(queries[0],),
                        matched_channels=("code_search",),
                        best_rank_by_channel={"code_search": 1},
                        hit_count=1,
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
    assert payload["items"][0]["itemId"] == "github:repo:thermotools/lammps_mie_fh"
    assert payload["items"][0]["matchedTerms"] == []
    assert "code_search" in payload["items"][0]["reason"]


def test_explore_search_returns_502_when_all_sources_fail(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.run_external_repository_retrieval",
        lambda queries: _build_retrieved_candidates(
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
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user, *, database_url: ExploreActor(
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
        lambda actor, turnstile_verified=False, *, database_url: ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.GUEST_COOLDOWN,
            message="Please wait 30 seconds before running another search.",
            retry_after_seconds=30,
            sign_in_suggested=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.record_blocked_explore_attempt",
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
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user, *, database_url: ExploreActor(
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
        lambda actor, turnstile_verified=False, *, database_url: ExploreAccessDecision(
            allowed=False,
            code=ExploreLimitCode.TURNSTILE_REQUIRED,
            message="Please complete the verification challenge before continuing.",
            turnstile_required=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.routes.explore.record_blocked_explore_attempt",
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
        "app.api.routes.explore.resolve_explore_actor",
        lambda request, user, *, database_url: ExploreActor(
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

    def _check_access(actor, turnstile_verified=False, *, database_url):
        assert turnstile_verified is True
        return ExploreAccessDecision(allowed=True)

    monkeypatch.setattr("app.api.routes.explore.check_explore_access", _check_access)
    monkeypatch.setattr(
        "app.api.routes.explore.record_allowed_explore_attempt",
        lambda actor, *, topic_hash, database_url: None,
    )
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.run_external_repository_retrieval",
        lambda queries: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:Mephistos-ML/paranmr",
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
    assert response.json()["items"][0]["itemId"] == "github:repo:Mephistos-ML/paranmr"


def test_explore_search_job_returns_completed_snapshot(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    STATE.explore_search_jobs.clear()
    monkeypatch.setattr(
        "app.services.search.jobs._start_explore_search_job_runner",
        _run_explore_job_inline,
    )
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("paramagnetic nmr"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.run_external_repository_retrieval",
        lambda queries, progress_callback=None, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "github:repo:Mephistos-ML/paranmr",
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
            "/api/explore/search-jobs",
            json={"topicDescription": "Paramagnetic NMR analysis workflows"},
        )

        assert response.status_code == 202
        created = response.json()
        assert created["status"] == "completed"
        assert created["items"][0]["itemId"] == "github:repo:Mephistos-ML/paranmr"

        follow_up = client.get(f"/api/explore/search-jobs/{created['jobId']}")

    assert follow_up.status_code == 200
    assert follow_up.json()["status"] == "completed"


def test_explore_search_job_returns_failed_snapshot_when_all_sources_fail(
    monkeypatch,
) -> None:
    _allow_explore_access(monkeypatch)
    STATE.explore_search_jobs.clear()
    monkeypatch.setattr(
        "app.services.search.jobs._start_explore_search_job_runner",
        _run_explore_job_inline,
    )
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("orca parser"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.run_external_repository_retrieval",
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
            "/api/explore/search-jobs",
            json={"topicDescription": "A python package for working with Orca."},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["sourceStatuses"][0]["source"] == "github"
    assert payload["error"] == "Repository search is temporarily unavailable across all providers."


def test_explore_search_job_returns_completed_partial_snapshot(monkeypatch) -> None:
    _allow_explore_access(monkeypatch)
    STATE.explore_search_jobs.clear()
    monkeypatch.setattr(
        "app.services.search.jobs._start_explore_search_job_runner",
        _run_explore_job_inline,
    )
    monkeypatch.setattr(
        "app.services.search.explore.build_ai_search_plan",
        lambda topic_description: _build_ready_repository_ai_plan("orca parser"),
    )
    monkeypatch.setattr(
        "app.services.search.explore.run_external_repository_retrieval",
        lambda queries, progress_callback=None, **kwargs: _build_retrieved_candidates(
            _build_explore_repository_signal(
                "gitlab:repo:kragskow-group/orto",
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
            "/api/explore/search-jobs",
            json={"topicDescription": "A python package for working with Orca."},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "completed_partial"
    assert payload["items"][0]["itemId"] == "gitlab:repo:kragskow-group/orto"
    assert "partial coverage" in payload["message"]
