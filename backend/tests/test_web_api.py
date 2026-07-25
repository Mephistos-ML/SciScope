"""Web API tests for the first backend split migration."""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile

from app.models.signal import RawSignal
from app.models.topic import ResearchProfile, ResearchTopic
from app.runtime.state import STATE
from app.services import runtime
from app.api.routes import application
from app.storage import entities as entity_storage
from app.storage import subscriptions as subscription_storage


def _request(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}
    body_bytes = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else b""
    )

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
    ) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body_bytes)),
        "wsgi.input": io.BytesIO(body_bytes),
    }
    body = b"".join(application(environ, start_response))
    return (
        str(captured["status"]),
        dict(captured["headers"]),
        body,
    )


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

    status, headers, body = _request("/api/status")
    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    status_payload = json.loads(body)
    assert status_payload["topicSlug"] == "pnmr"
    assert status_payload["discoveryQueries"] == []
    assert status_payload["watchedEntities"] == []
    assert status_payload["sourceCheckpoints"] == []
    assert status_payload["totalSignals"] == 1
    assert status_payload["matchedSignals"] == 1

    status, _, body = _request("/api/signals")
    assert status == "200 OK"
    signal_list = json.loads(body)
    assert len(signal_list["items"]) == 1
    assert signal_list["items"][0]["itemId"] == "demo"

    status, _, body = _request("/api/signals/demo")
    assert status == "200 OK"
    detail_payload = json.loads(body)
    assert detail_payload["itemId"] == "demo"
    assert detail_payload["matched"] is True


def test_root_returns_service_description() -> None:
    status, headers, body = _request("/")

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
    assert payload["service"] == "sciscope-api"
    assert "/api/signals" in payload["endpoints"]


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

    status, headers, body = _request("/api/start", method="POST")

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
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

    status, headers, body = _request("/api/stop", method="POST")

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
    assert payload["topicSlug"] == "pnmr"
    assert payload["autoScanStarted"] is False


def test_missing_signal_returns_404_json() -> None:
    STATE.signals.clear()

    status, headers, body = _request("/api/signals/missing")

    assert status == "404 Not Found"
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    payload = json.loads(body)
    assert payload["error"] == "Signal not found"


def test_dev_login_and_subscription_endpoints(monkeypatch) -> None:
    STATE.current_user_id = None

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "subscriptions.sqlite3"
        monkeypatch.setattr(subscription_storage, "DB_PATH", db_path)
        monkeypatch.setattr(entity_storage, "DB_PATH", db_path)

        status, _, body = _request("/api/me")
        assert status == "200 OK"
        assert json.loads(body) == {"user": None}

        status, _, body = _request("/api/subscriptions")
        assert status == "401 Unauthorized"
        assert json.loads(body)["error"] == "Authentication required"

        status, _, body = _request("/api/auth/dev-login", method="POST")
        assert status == "200 OK"
        payload = json.loads(body)
        assert payload["user"]["userId"] == "local-dev-user"

        status, _, body = _request(
            "/api/subscriptions",
            method="POST",
            payload={
                "topicDescription": "paramagnetic NMR software",
                "manualQueries": ["pcs", "relaxation"],
            },
        )
        assert status == "201 Created"
        created = json.loads(body)
        assert created["topicDescription"] == "paramagnetic NMR software"
        assert created["manualQueries"] == ["pcs", "relaxation"]

        status, _, body = _request("/api/subscriptions")
        assert status == "200 OK"
        listed = json.loads(body)
        assert len(listed["items"]) == 1
        assert listed["items"][0]["topicDescription"] == "paramagnetic NMR software"

        subscription_id = listed["items"][0]["subscriptionId"]
        status, _, body = _request(f"/api/subscriptions/{subscription_id}", method="DELETE")
        assert status == "200 OK"
        assert json.loads(body) == {"deleted": True}

        status, _, body = _request("/api/subscriptions")
        assert status == "200 OK"
        listed = json.loads(body)
        assert listed["items"] == []

        status, _, body = _request("/api/logout", method="POST")
        assert status == "200 OK"
        assert json.loads(body) == {"user": None}
