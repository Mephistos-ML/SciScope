"""AI planner tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from time import monotonic

from app.composition.repositories import build_repository_adapters
from app.api.app import app
from app.composition import search as composition
from app.jobs.process_search_runs import process_next_search_run_operation
from app.models.ai import AiPlannerIdentity
from app.models.explore_access import ExploreActor, ExploreAdmission, ExploreTier
from app.services.ai.planner import AiSearchPlanner
from app.services.search.explore.dependencies import ExploreDependencies
from app.services.search.retrieval.models import RetrievalLane
from app.services.search.retrieval.service import run_external_repository_retrieval
from app.storage.search_runs import get_search_run
from tests.fixtures.database import build_test_database_url, migrate_test_database


from app import config
from app.models.ai import AiSearchPlan
from app.composition.search import build_explore_dependencies


def test_composition_selects_bootstrap_planner() -> None:
    plan = build_explore_dependencies(repositories=build_repository_adapters()).planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.status == "pending"
    assert plan.queries == ()


def test_composition_selects_openai_planner(
    monkeypatch,
) -> None:
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")

    def _build_search_plan(_self, **kwargs) -> AiSearchPlan:
        assert kwargs["topic_description"] == "Paramagnetic NMR analysis workflows"
        return AiSearchPlan(
            status="ready",
            queries=("paramagnetic nmr software", "pcs tensor fitting"),
        )

    monkeypatch.setattr(
        "app.integrations.ai.openai.planner.OpenAiSearchPlanner.build_search_plan",
        _build_search_plan,
    )

    plan = build_explore_dependencies(repositories=build_repository_adapters()).planner.build_search_plan(topic_description="Paramagnetic NMR analysis workflows")

    assert plan.status == "ready"
    assert plan.queries == (
        "paramagnetic nmr software",
        "pcs tensor fitting",
    )


@pytest.mark.parametrize("base_url,code_enabled", [
    ("https://gitlab.com", False),
    ("https://www.gitlab.com", False),
    ("https://GITLAB.COM/api/v4", False),
    ("https://gitlab.example.org", True),
])
def test_composition_registers_supported_provider_channels(monkeypatch, base_url, code_enabled):
    monkeypatch.setattr(config, "GITLAB_BASE_URL", base_url)
    lanes = build_explore_dependencies(repositories=build_repository_adapters()).lanes
    expected = {
        ("github", "repository_search"), ("github", "code_search"),
        ("gitlab", "repository_search"),
    }
    if code_enabled:
        expected.add(("gitlab", "code_search"))
    assert {(lane.source, lane.channel) for lane in lanes} == expected


def test_unknown_planner_mode_fails_at_composition(monkeypatch):
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "unsupported")
    with pytest.raises(ValueError, match="Unsupported AI planner mode"):
        build_explore_dependencies(repositories=build_repository_adapters())


def test_selected_openai_settings_remain_bound_after_configuration_changes(monkeypatch):
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")
    monkeypatch.setattr(config, "OPENAI_MODEL", "selected-model")
    monkeypatch.setattr(config, "OPENAI_REASONING_EFFORT", "low")
    dependencies = build_explore_dependencies(repositories=build_repository_adapters())
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "bootstrap")
    monkeypatch.setattr(config, "OPENAI_MODEL", "other-model")
    monkeypatch.setattr(config, "OPENAI_REASONING_EFFORT", "high")
    captured = {}

    def generate(**kwargs):
        captured.update(kwargs)
        return {"queries": ["first query", "second query", "third query"]}

    monkeypatch.setattr("app.integrations.ai.openai.planner.build_openai_json_response", generate)
    plan = dependencies.planner.build_search_plan(topic_description="Research topic")
    assert plan.queries == ("first query", "second query", "third query")
    assert captured["model"] == dependencies.planner.identity.model == "selected-model"
    assert captured["reasoning_effort"] == dependencies.planner.identity.reasoning_effort == "low"
    assert dependencies.planner.identity.mode == "openai"


def test_registered_lanes_receive_deadlines_through_real_orchestration(monkeypatch):
    calls = []

    def discover(queries, *, deadline_monotonic, client):
        calls.append((tuple(queries), deadline_monotonic))
        return []

    for name in ("github_repositories", "github_code", "gitlab_repositories", "gitlab_code"):
        monkeypatch.setattr(composition, name, discover)
    monkeypatch.setattr(config, "GITLAB_BASE_URL", "https://gitlab.example.org")
    dependencies = build_explore_dependencies(repositories=build_repository_adapters())
    deadline = monotonic() + 30
    result = run_external_repository_retrieval(
        ("scientific query",), lanes=dependencies.lanes, hard_deadline_monotonic=deadline,
    )
    assert len(calls) == 4
    assert all(queries == ("scientific query",) and 0 < received <= deadline for queries, received in calls)
    assert result.successful_source_count == 2
    assert not result.partial


def test_async_api_and_worker_use_injected_capabilities_and_actual_planner_provenance(tmp_path, monkeypatch):
    url = build_test_database_url(tmp_path / "search-composition.sqlite3")
    migrate_test_database(url)
    planned = []
    retrieved = []

    def api_plan(*, topic_description):
        pytest.fail("The API must queue async work without executing its planner")

    def worker_plan(*, topic_description):
        planned.append(topic_description)
        return AiSearchPlan("ready", ("first query", "second query", "third query"))

    def provider(queries, *, deadline_monotonic):
        assert deadline_monotonic is not None
        retrieved.extend(queries)
        return []

    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")
    monkeypatch.setattr(config, "OPENAI_MODEL", "api-model")
    monkeypatch.setattr(config, "OPENAI_REASONING_EFFORT", "high")
    selected = build_explore_dependencies(repositories=build_repository_adapters())
    api_dependencies = ExploreDependencies(
        AiSearchPlanner(api_plan, selected.planner.identity), (), None,
    )
    worker_dependencies = ExploreDependencies(
        AiSearchPlanner(worker_plan, AiPlannerIdentity("openai", "worker-model", "low")),
        (RetrievalLane("github", "repository_search", provider),), None,
    )
    monkeypatch.setattr(app.state, "database_url", url)
    monkeypatch.setattr(app.state, "explore_dependencies", api_dependencies)
    monkeypatch.setattr("app.api.routes.explore._prepare_explore_search_request", lambda *args: ExploreAdmission(
        ExploreActor(ExploreTier.GUEST, "guest_ip", "composition-test"), bypass_quota=True,
    ))
    with TestClient(app) as client:
        response = client.post("/api/explore/search-runs", json={"topicDescription": "Scientific research"})
        assert response.status_code == 202
        created = response.json()
        before = get_search_run(created["runId"], database_url=url)
        assert before.planner_model == "api-model"
        assert before.planner_reasoning_effort == "high"
        monkeypatch.setattr(config, "AI_PLANNER_MODE", "bootstrap")
        assert process_next_search_run_operation(
            worker_id="test-worker", database_url=url, dependencies=worker_dependencies,
        )
        completed = get_search_run(created["runId"], database_url=url)
        assert completed.status == "completed"
        assert completed.planner_model == "worker-model"
        assert completed.planner_reasoning_effort == "low"
        assert planned == ["Scientific research"]
        assert retrieved == ["first query"]
        assert completed.execution_state["plan"]["queries"] == ["first query", "second query", "third query"]
        snapshot = client.get(f"/api/explore/search-runs/{created['runId']}", headers={
            "X-Search-Run-Token": created["guestAccessToken"],
        }).json()
        assert snapshot["status"] == "completed" and snapshot["canExpand"]
        assert snapshot["aiSearchPlan"]["status"] == "ready"
        assert client.post(f"/api/explore/search-runs/{created['runId']}/expand", headers={
            "X-Search-Run-Token": created["guestAccessToken"],
        }).status_code == 202
        expansion_dependencies = ExploreDependencies(
            planner=api_dependencies.planner, lanes=worker_dependencies.lanes, embeddings=None,
        )
        assert process_next_search_run_operation(
            worker_id="test-worker", database_url=url, dependencies=expansion_dependencies,
        )
        assert planned == ["Scientific research"]
        assert retrieved == ["first query", "second query"]
        assert get_search_run(created["runId"], database_url=url).planner_model == "worker-model"


@pytest.mark.parametrize("failure_kind", ["timeout", "invalid_plan"])
def test_ai_adapter_failure_finishes_queued_run_without_provider_retrieval(tmp_path, monkeypatch, failure_kind):
    import httpx2 as httpx
    url = build_test_database_url(tmp_path / "ai-failure.sqlite3")
    migrate_test_database(url)
    monkeypatch.setattr(config, "AI_PLANNER_MODE", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")
    dependencies = build_explore_dependencies(repositories=build_repository_adapters())

    def post(*args, **kwargs):
        if failure_kind == "timeout":
            raise httpx.ReadTimeout("private provider diagnostics")
        return httpx.Response(200, json={"output_text": '{"queries":[1,"second","third"]}'},
                              request=httpx.Request("POST", "https://example.test/responses"))

    def retrieve(*args, **kwargs):
        pytest.fail("An invalid or unavailable plan must not trigger provider retrieval")

    dependencies = ExploreDependencies(dependencies.planner, (RetrievalLane("github", "repository_search", retrieve),), None)
    monkeypatch.setattr(app.state, "database_url", url)
    monkeypatch.setattr(app.state, "explore_dependencies", dependencies)
    monkeypatch.setattr("app.api.routes.explore._prepare_explore_search_request", lambda *args: ExploreAdmission(
        ExploreActor(ExploreTier.GUEST, "guest_ip", "ai-failure"), bypass_quota=True,
    ))
    with TestClient(app) as client:
        response = client.post("/api/explore/search-runs", json={"topicDescription": "Scientific research"})
        assert response.status_code == 202
        created = response.json()
        with monkeypatch.context() as provider_patch:
            provider_patch.setattr(httpx.Client, "post", post)
            assert process_next_search_run_operation(worker_id="test", database_url=url, dependencies=dependencies)
        run = get_search_run(created["runId"], database_url=url)
        assert run.status == "failed"
        assert run.execution_state is None
        assert run.error_message == "AI search planning is temporarily unavailable."
        snapshot = client.get(f"/api/explore/search-runs/{created['runId']}", headers={
            "X-Search-Run-Token": created["guestAccessToken"],
        }).json()
        assert snapshot["status"] == "failed"
        assert not snapshot["canExpand"]
        assert "private provider diagnostics" not in str(snapshot)


@pytest.mark.parametrize("enabled", [True, False])
def test_semantic_capability_selection_remains_bound_after_configuration_changes(monkeypatch, enabled):
    monkeypatch.setattr(config, "SEMANTIC_CATALOG_ENABLED", enabled)
    selected = build_explore_dependencies(repositories=build_repository_adapters())
    monkeypatch.setattr(config, "SEMANTIC_CATALOG_ENABLED", not enabled)
    assert (selected.embeddings is not None) == enabled
    if selected.embeddings is not None:
        assert selected.embeddings.model == config.SEMANTIC_EMBEDDING_MODEL
