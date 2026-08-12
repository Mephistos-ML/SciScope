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


def migrate_test_database(database_url: str) -> None:
    """Apply Alembic migrations to one test database."""

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
        command.upgrade(alembic_config, "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
