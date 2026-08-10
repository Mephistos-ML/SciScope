"""Application configuration lives here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

APP_VERSION = "0.1.0"
DISCOVERY_INTERVAL_SECONDS = 86400  # 24 hours
MONITORING_INTERVAL_SECONDS = 7200  # 2 hours
POLLING_FREQUENCY_SECONDS = 30  # scheduler polling frequency: 30 seconds
REPLAY_FIXTURES_PATH = PROJECT_ROOT / "data" / "replay_signals.json"


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _read_optional_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _read_required_int_env(name: str) -> int:
    raw_value = _read_required_env(name)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be an integer, got {raw_value!r}"
        ) from exc


def _read_required_csv_env(name: str) -> tuple[str, ...]:
    raw_value = _read_required_env(name)
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    if not values:
        raise RuntimeError(f"Environment variable {name} must contain at least one value")
    return values


def _build_db_path(database_url: str) -> Path:
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        raise RuntimeError(
            "DATABASE_URL must currently use sqlite:///path/to/sciscope.sqlite3"
        )

    raw_path = database_url.removeprefix(sqlite_prefix).strip()
    if not raw_path:
        raise RuntimeError("DATABASE_URL must include a SQLite file path")

    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path
    return db_path


APP_ENV = _read_required_env("APP_ENV")
APP_HOST = _read_required_env("APP_HOST")
APP_PORT = _read_required_int_env("APP_PORT")
CORS_ORIGINS = _read_required_csv_env("CORS_ORIGINS")
DATABASE_URL = _read_required_env("DATABASE_URL")
DB_PATH = _build_db_path(DATABASE_URL)
GITHUB_TOKEN = _read_optional_env("GITHUB_TOKEN")
GITLAB_TOKEN = _read_optional_env("GITLAB_TOKEN")
