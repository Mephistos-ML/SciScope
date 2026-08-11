"""Application configuration lives here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

APP_VERSION = "0.1.0"
DISCOVERY_INTERVAL_SECONDS = 86400  # 24 hours
MONITORING_INTERVAL_SECONDS = 7200  # 2 hours
POLLING_FREQUENCY_SECONDS = 30  # scheduler polling frequency: 30 seconds


def _read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _read_optional_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _read_optional_path_env(name: str, default: Path) -> Path:
    raw_value = _read_optional_env(name)
    if not raw_value:
        return default

    path = Path(raw_value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


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


REPLAY_FIXTURES_PATH = _read_optional_path_env(
    "REPLAY_FIXTURES_PATH",
    BACKEND_ROOT / "tests" / "fixtures" / "replay_signals.json",
)
APP_ENV = _read_required_env("APP_ENV")
APP_HOST = _read_required_env("APP_HOST")
APP_PORT = _read_required_int_env("APP_PORT")
CORS_ORIGINS = _read_required_csv_env("CORS_ORIGINS")
DATABASE_URL = _read_required_env("DATABASE_URL")
GITHUB_TOKEN = _read_optional_env("GITHUB_TOKEN")
GITLAB_TOKEN = _read_optional_env("GITLAB_TOKEN")
