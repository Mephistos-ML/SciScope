"""Public search lifecycle contract shared by HTTP responses and the client."""

from pathlib import Path
import re
from typing import get_args

from fastapi.testclient import TestClient
import pytest

from app.api.app import app
from app.models.search_run import SearchRunStatus
from tests.conftest import build_test_database_url, migrate_test_database
from tests.fixtures.search_runs import seed_search_run, set_search_run_state


def test_frontend_search_status_contract_matches_backend() -> None:
    """Guard the explicit TypeScript union until contracts are generated."""
    source = (Path(__file__).resolve().parents[3] / "frontend/src/types/api.ts").read_text()
    declaration = re.search(r"export type ExploreSearchRunStatus\s*=\s*(.*?);", source, re.DOTALL)
    assert declaration is not None, "The client must declare its public search run status contract"
    frontend_statuses = set(re.findall(r'"([^"]+)"', declaration.group(1)))
    assert frontend_statuses == set(get_args(SearchRunStatus))


@pytest.mark.parametrize("status", get_args(SearchRunStatus))
def test_search_snapshot_exposes_each_lifecycle_status(tmp_path, monkeypatch, status) -> None:
    database_url = build_test_database_url(tmp_path / "status-contract.sqlite3")
    migrate_test_database(database_url)
    monkeypatch.setattr(app.state, "database_url", database_url)
    created = seed_search_run(topic_description="Scientific software", database_url=database_url)
    set_search_run_state(created["runId"], status=status, database_url=database_url)

    with TestClient(app) as client:
        response = client.get(
            f"/api/explore/search-runs/{created['runId']}",
            headers={"X-Search-Run-Token": created["guestAccessToken"]},
        )
    assert response.status_code == 200
    assert response.json()["status"] == status
    assert response.json()["runId"] == created["runId"]
