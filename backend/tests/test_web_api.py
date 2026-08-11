"""Web API tests for the FastAPI backend transport."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from tests.conftest import build_test_database_url, migrate_test_database
from app.api.app import app
from app.models.signal import RawSignal
from app.models.topic import ResearchProfile, ResearchTopic
from app.runtime.state import STATE
from app.services import runtime
from app.storage import entities as entity_storage
from app.storage import subscriptions as subscription_storage


def _build_raw_signal(item_id: str) -> RawSignal:
    return RawSignal(
        source="github",
        source_type="github_commit",
        item_id=item_id,
        title="Add PCS tensor fitting improvements",
        url=f"https://github.com/Mephistos-ML/paranmr/commit/{item_id}",
        published_at=None,
        raw_text=(
            "Improves susceptibility tensor fitting and automated PCS "
            "assignment workflow for paramagnetic NMR datasets."
        ),
        payload={
            "signal_kind": "github_commit",
            "repo": "Mephistos-ML/paranmr",
            "files": [
                "paranmr/core/fitting/tensor.py",
            ],
        },
    )


def _build_explore_repository_signal(
    item_id: str,
    *,
    source: str = "github",
    query: str = "paramagnetic nmr",
) -> RawSignal:
    return RawSignal(
        source=source,
        source_type=f"{source}_repository",
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
            "signal_kind": f"{source}_repository",
            "repo": "Mephistos-ML/paranmr",
            "query": query,
            "topics": ["paramagnetic-nmr", "pcs"],
            "language": "Python",
            "stars": 14,
        },
    )


def _build_active_topic() -> ResearchTopic:
    return ResearchTopic(slug="pnmr", label="Paramagnetic NMR")


def _build_active_profile() -> ResearchProfile:
    return ResearchProfile(topic_slug="pnmr", core_terms=("paramagnetic nmr", "pcs"))


def _build_runtime_profiles() -> tuple[ResearchProfile, ...]:
    return (_build_active_profile(),)


def _build_runtime_topics() -> tuple[ResearchTopic, ...]:
    return (_build_active_topic(),)


def test_status_and_signal_endpoints_return_json(monkeypatch) -> None:
    STATE.signals.clear()
    STATE.current_user_id = None
    STATE.monitoring_started_at = None
    STATE.last_scan_at = None
    STATE.last_scan_error = None
    STATE.last_discovery_at = None
    STATE.last_discovery_error = None
    STATE.last_discovery_result = None
    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.clear()
    STATE.auto_scan_thread = None

    monkeypatch.setattr(runtime, "list_runtime_profiles", _build_runtime_profiles)
    monkeypatch.setattr(runtime, "list_runtime_topics", _build_runtime_topics)
    monkeypatch.setattr(runtime, "describe_watched_repositories", lambda topic_slug: [])
    monkeypatch.setattr(runtime, "describe_repository_checkpoints", lambda topic_slug: [])
    monkeypatch.setattr(runtime, "load_replay_signals", lambda: [_build_raw_signal("demo")])
    monkeypatch.setattr(runtime, "load_repository_signals_for_profile", lambda profile: [])
    monkeypatch.setattr(runtime, "load_seen_signal_ids", lambda source: set())
    monkeypatch.setattr(runtime, "upsert_raw_signals", lambda signals: None)

    runtime.run_scan_cycle()

    with TestClient(app) as client:
        response = client.get("/api/status")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        status_payload = response.json()
        assert status_payload["topicSlug"] == "pnmr"
        assert status_payload["discoveryQueries"] == []
        assert status_payload["watchedEntities"] == []
        assert status_payload["sourceCheckpoints"] == []
        assert status_payload["totalSignals"] == 1
        assert status_payload["matchedSignals"] == 1

        response = client.get("/api/signals")
        assert response.status_code == 200
        signal_list = response.json()
        assert len(signal_list["items"]) == 1
        assert signal_list["items"][0]["itemId"] == "demo"

        response = client.get("/api/signals/demo")
        assert response.status_code == 200
        detail_payload = response.json()
        assert detail_payload["itemId"] == "demo"
        assert detail_payload["matched"] is True


def test_root_health_and_ready_endpoints() -> None:
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
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


def test_api_start_endpoint_returns_status_json(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.control.start_monitoring", lambda: None)
    monkeypatch.setattr(
        "app.api.routes.control.get_status_payload",
        lambda: {
            "topicSlug": "pnmr",
            "topicLabel": "Paramagnetic NMR",
            "autoScanStarted": True,
            "autoScanIntervalSeconds": 300,
            "lastScanAt": None,
            "lastScanError": None,
            "totalSignals": 0,
            "matchedSignals": 0,
        },
    )

    with TestClient(app) as client:
        response = client.post("/api/start")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    payload = response.json()
    assert payload["topicSlug"] == "pnmr"
    assert payload["autoScanStarted"] is True


def test_api_stop_endpoint_returns_status_json(monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.control.stop_monitoring", lambda: None)
    monkeypatch.setattr(
        "app.api.routes.control.get_status_payload",
        lambda: {
            "topicSlug": "pnmr",
            "topicLabel": "Paramagnetic NMR",
            "autoScanStarted": False,
            "autoScanIntervalSeconds": 300,
            "lastScanAt": None,
            "lastScanError": None,
            "totalSignals": 0,
            "matchedSignals": 0,
        },
    )

    with TestClient(app) as client:
        response = client.post("/api/stop")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    payload = response.json()
    assert payload["topicSlug"] == "pnmr"
    assert payload["autoScanStarted"] is False


def test_missing_signal_returns_404_json() -> None:
    STATE.signals.clear()

    with TestClient(app) as client:
        response = client.get("/api/signals/missing")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    payload = response.json()
    assert payload["error"] == "Signal not found"


def test_dev_login_and_subscription_endpoints(monkeypatch) -> None:
    STATE.current_user_id = None

    with tempfile.TemporaryDirectory() as temp_dir:
        database_url = build_test_database_url(Path(temp_dir) / "subscriptions.sqlite3")
        migrate_test_database(database_url)
        monkeypatch.setattr(subscription_storage, "DATABASE_URL", database_url)
        monkeypatch.setattr(entity_storage, "DATABASE_URL", database_url)

        with TestClient(app) as client:
            response = client.get("/api/me")
            assert response.status_code == 200
            assert response.json() == {"user": None}

            response = client.get("/api/subscriptions")
            assert response.status_code == 401
            assert response.json()["error"] == "Authentication required"

            response = client.post("/api/auth/dev-login")
            assert response.status_code == 200
            payload = response.json()
            assert payload["user"]["userId"] == "local-dev-user"

            response = client.post(
                "/api/subscriptions",
                json={
                    "topicDescription": "paramagnetic NMR software",
                },
            )
            assert response.status_code == 201
            created = response.json()
            assert created["topicDescription"] == "paramagnetic NMR software"
            assert "paramagnetic NMR software" in created["queries"]

            response = client.get("/api/subscriptions")
            assert response.status_code == 200
            listed = response.json()
            assert len(listed["items"]) == 1
            assert listed["items"][0]["topicDescription"] == "paramagnetic NMR software"
            assert "paramagnetic NMR software" in listed["items"][0]["queries"]

            subscription_id = listed["items"][0]["subscriptionId"]
            response = client.delete(f"/api/subscriptions/{subscription_id}")
            assert response.status_code == 200
            assert response.json() == {"deleted": True}

            response = client.get("/api/subscriptions")
            assert response.status_code == 200
            listed = response.json()
            assert listed["items"] == []

            response = client.post("/api/logout")
            assert response.status_code == 200
            assert response.json() == {"user": None}


def test_explore_search_returns_partial_results_when_one_source_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.explore.discover_github_repository_candidates",
        lambda queries: [
            _build_explore_repository_signal(
                "github:repo:Mephistos-ML/paranmr",
                query=str(queries[0]),
            )
        ],
    )

    def fail_gitlab(_queries) -> list[RawSignal]:
        raise RuntimeError("GitLab upstream failed")

    monkeypatch.setattr(
        "app.services.explore.discover_gitlab_repository_candidates",
        fail_gitlab,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={
                "topicDescription": "Paramagnetic NMR analysis workflows",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    payload = response.json()
    assert "Paramagnetic NMR analysis workflows" in payload["queries"]
    assert len(payload["items"]) == 1
    assert payload["items"][0]["itemId"] == "github:repo:Mephistos-ML/paranmr"
    assert payload["items"][0]["source"] == "github"
    assert payload["sourceStatuses"] == [
        {
            "source": "github",
            "status": "ok",
            "candidateCount": 1,
            "error": None,
        },
        {
            "source": "gitlab",
            "status": "error",
            "candidateCount": 0,
            "error": "GitLab repository search is unavailable right now.",
        },
    ]


def test_explore_search_returns_502_when_all_sources_fail(monkeypatch) -> None:
    def fail_github(_queries) -> list[RawSignal]:
        raise RuntimeError("GitHub upstream failed")

    def fail_gitlab(_queries) -> list[RawSignal]:
        raise RuntimeError("GitLab upstream failed")

    monkeypatch.setattr(
        "app.services.explore.discover_github_repository_candidates",
        fail_github,
    )
    monkeypatch.setattr(
        "app.services.explore.discover_gitlab_repository_candidates",
        fail_gitlab,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/explore/search",
            json={
                "topicDescription": "Paramagnetic NMR analysis workflows",
            },
        )

    assert response.status_code == 502
    assert response.headers["content-type"] == "application/json"
    payload = response.json()
    assert payload["error"] == "Repository search is temporarily unavailable across all providers."
    assert payload["sourceStatuses"] == [
        {
            "source": "github",
            "status": "error",
            "candidateCount": 0,
            "error": "GitHub repository search is unavailable right now.",
        },
        {
            "source": "gitlab",
            "status": "error",
            "candidateCount": 0,
            "error": "GitLab repository search is unavailable right now.",
        },
    ]
