"""Database setup shared by tests and pytest fixtures."""

from pathlib import Path
import os
from alembic import command
from alembic.config import Config

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


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
