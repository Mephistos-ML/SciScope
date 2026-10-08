"""Test bootstrap helpers."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
import os
from pathlib import Path
import sys
import tempfile

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_HOST", "127.0.0.1")
os.environ.setdefault("APP_PORT", "8000")
os.environ.setdefault(
    "CORS_ORIGINS",
    "http://localhost:5173,https://sciscope.uk,https://www.sciscope.uk",
)
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+pysqlite:///{Path(tempfile.gettempdir()) / 'sciscope-test-bootstrap.sqlite3'}",
)
os.environ.setdefault("AI_PLANNER_MODE", "bootstrap")


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
    parser.addoption("--postgres", action="store_true", help="Run PostgreSQL/pgvector correctness tests.")


def pytest_configure(config) -> None:
    import pytest

    config.addinivalue_line("markers", "postgres: requires an isolated PostgreSQL/pgvector test server")
    if config.getoption("--postgres") and not os.environ.get("SCISCOPE_TEST_POSTGRES_URL"):
        raise pytest.UsageError("--postgres requires SCISCOPE_TEST_POSTGRES_URL pointing to a test server.")


def pytest_collection_modifyitems(config, items) -> None:
    import pytest

    if not config.getoption("--postgres"):
        for item in items:
            if item.get_closest_marker("postgres"):
                item.add_marker(pytest.mark.skip(reason="Enable PostgreSQL tests with --postgres."))
