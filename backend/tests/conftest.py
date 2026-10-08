"""Test bootstrap helpers."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
import os
from pathlib import Path
import sys
import tempfile

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Tests select their own deployment configuration before importing app modules.
# SCISCOPE_TEST_POSTGRES_URL is the explicit opt-in test-server configuration.
_CONFIG_PREFIXES = (
    "APP_",
    "AUTH_",
    "CORS_",
    "FRONTEND_",
    "REPLAY_",
    "SEARCH_",
    "EXPLORE_",
    "TURNSTILE_",
    "GOOGLE_",
    "GITHUB_",
    "GITLAB_",
    "OPENAI_",
    "SEMANTIC_",
    "AI_",
)
for name in tuple(os.environ):
    if name == "DATABASE_URL" or name.startswith(_CONFIG_PREFIXES):
        del os.environ[name]
_BOOTSTRAP_DIRECTORY = tempfile.TemporaryDirectory(prefix="sciscope-test-bootstrap-")
os.environ.update(
    {
        "APP_ENV": "test",
        "APP_HOST": "127.0.0.1",
        "APP_PORT": "8000",
        "CORS_ORIGINS": "http://localhost:5173,https://sciscope.uk,https://www.sciscope.uk",
        "DATABASE_URL": f"sqlite+pysqlite:///{Path(_BOOTSTRAP_DIRECTORY.name) / 'bootstrap.sqlite3'}",
        "AI_PLANNER_MODE": "bootstrap",
    }
)


def build_test_database_url(path: Path) -> str:
    """Build one SQLAlchemy SQLite URL for an on-disk test database."""

    return f"sqlite+pysqlite:///{path}"


def migrate_test_database(database_url: str, revision: str = "head") -> None:
    """Apply Alembic migrations to one test database revision."""

    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option(
        "script_location",
        str(BACKEND_ROOT / "alembic"),
    )
    alembic_config.set_main_option(
        "prepend_sys_path",
        str(BACKEND_ROOT),
    )

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(alembic_config, revision)
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--postgres",
        action="store_true",
        help="Run PostgreSQL/pgvector correctness tests.",
    )


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers", "postgres: requires an isolated PostgreSQL/pgvector test server"
    )
    if config.getoption("--postgres") and not os.environ.get(
        "SCISCOPE_TEST_POSTGRES_URL"
    ):
        raise pytest.UsageError(
            "--postgres requires SCISCOPE_TEST_POSTGRES_URL pointing to a test server."
        )


def pytest_collection_modifyitems(config, items) -> None:
    if not config.getoption("--postgres"):
        for item in items:
            if item.get_closest_marker("postgres"):
                item.add_marker(
                    pytest.mark.skip(reason="Enable PostgreSQL tests with --postgres.")
                )


@pytest.fixture(autouse=True)
def isolated_database_resources():
    """Enforce SQLite constraints and dispose every engine owned by this test."""
    import sqlite3
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    from app.database import session as database

    engines = set()

    def track_engine(connection):
        engines.add(connection.engine)

    def enforce_constraints(connection, _record):
        if isinstance(connection, sqlite3.Connection):
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    event.listen(Engine, "engine_connect", track_engine)
    event.listen(Engine, "connect", enforce_constraints)
    try:
        yield
    finally:
        try:
            for engine in engines | set(database._ENGINE_CACHE.values()):
                engine.dispose()
        finally:
            database._SESSION_FACTORY_CACHE.clear()
            database._ENGINE_CACHE.clear()
            event.remove(Engine, "connect", enforce_constraints)
            event.remove(Engine, "engine_connect", track_engine)


@pytest.fixture(autouse=True)
def deny_uncontrolled_network(monkeypatch):
    """Provider tests must replace HTTP IO; in-process transports need no TCP."""
    import socket

    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def guarded_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            pytest.fail(f"Unexpected network connection in a test: {address!r}")
        return connect(sock, address)

    def guarded_connect_ex(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            pytest.fail(f"Unexpected network connection in a test: {address!r}")
        return connect_ex(sock, address)

    def guarded_resolution(*args, **kwargs):
        pytest.fail("Unexpected DNS lookup in a test; replace provider HTTP IO")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_resolution)


def pytest_sessionfinish(session, exitstatus):
    _BOOTSTRAP_DIRECTORY.cleanup()
