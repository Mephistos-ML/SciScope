"""HTTP errors expose application categories without provider SQL or parameters."""

import psycopg.errors
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.exc import DBAPIError

from app.api.app import app
from app.api.routes import subscriptions
from app.database.session import get_engine
from app.models.auth import User
from tests.conftest import build_test_database_url, migrate_test_database


@pytest.mark.parametrize("driver_error,http_status,code", [
    (psycopg.errors.ConnectionFailure, 503, "persistence_unavailable"),
    (psycopg.errors.SerializationFailure, 409, "persistence_conflict"),
    (psycopg.errors.UndefinedTable, 500, "persistence_failed"),
])
def test_http_persistence_failures_are_safe_and_distinct(tmp_path, monkeypatch, driver_error, http_status, code):
    url = build_test_database_url(tmp_path / "http-errors.sqlite3")
    migrate_test_database(url)
    monkeypatch.setattr(app.state, "database_url", url)
    monkeypatch.setattr(subscriptions, "get_current_user", lambda *args, **kwargs: User("user", "user@example.test", "User"))
    engine = get_engine(url)
    def fail(*args):
        raise DBAPIError("private SQL", {"secret": "private parameters"}, driver_error("private diagnostics"))
    with TestClient(app) as client:
        event.listen(engine, "before_cursor_execute", fail)
        try:
            response = client.get("/api/subscriptions")
        finally:
            event.remove(engine, "before_cursor_execute", fail)
    assert response.status_code == http_status
    assert response.json()["code"] == code
    assert "private" not in response.text
    assert "secret" not in response.text
