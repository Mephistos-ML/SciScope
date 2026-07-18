"""Web API tests for the first backend split migration."""

from __future__ import annotations

import io
import json

from app.models.signal import RawSignal
from app.models.topic import ResearchProfile, ResearchTopic
from app.runtime.state import STATE
from app.services import runtime
from app.api.routes import application


def _request(
    path: str,
    *,
    method: str = "GET",
) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(
        status: str,
        headers: list[tuple[str, str]],
    ) -> None:
        captured["status"] = status
        captured["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "wsgi.input": io.BytesIO(),
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


def test_status_and_signal_endpoints_return_json(monkeypatch) -> None:
    STATE.signals.clear()
    STATE.monitoring_started_at = None
    STATE.last_scan_at = None
    STATE.last_scan_error = None
    STATE.last_discovery_at = None
    STATE.last_discovery_error = None
    STATE.last_discovery_result = None
    STATE.auto_scan_started = False
    STATE.auto_scan_stop_event.clear()
    STATE.auto_scan_thread = None

    monkeypatch.setattr(runtime, "get_active_topic", _build_active_topic)
    monkeypatch.setattr(runtime, "get_active_profile", _build_active_profile)
    monkeypatch.setattr(runtime, "describe_watched_github_repositories", lambda topic_slug: [])
    monkeypatch.setattr(runtime, "describe_release_checkpoints", lambda topic_slug: [])
    monkeypatch.setattr(runtime, "load_replay_signals", lambda: [_build_raw_signal("demo")])
    monkeypatch.setattr(runtime, "load_github_signals_for_profile", lambda profile: [])
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
