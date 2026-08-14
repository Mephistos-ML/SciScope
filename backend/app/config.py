"""Application configuration lives here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

APP_VERSION = "0.1.0"
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


def _read_bool_env(name: str, default: bool) -> bool:
    raw_value = _read_optional_env(name)
    if not raw_value:
        return default

    normalized = raw_value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise RuntimeError(
        f"Environment variable {name} must be a boolean, got {raw_value!r}"
    )


def _read_optional_int_env(name: str, default: int) -> int:
    raw_value = _read_optional_env(name)
    if not raw_value:
        return default

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
AUTH_SESSION_COOKIE_NAME = _read_optional_env("AUTH_SESSION_COOKIE_NAME") or "sciscope_session"
AUTH_SESSION_COOKIE_DOMAIN = _read_optional_env("AUTH_SESSION_COOKIE_DOMAIN")
AUTH_SESSION_TTL_SECONDS = int(_read_optional_env("AUTH_SESSION_TTL_SECONDS") or "2592000")
AUTH_SESSION_SECURE = _read_bool_env("AUTH_SESSION_SECURE", APP_ENV == "production")
AUTH_SESSION_SAMESITE = (_read_optional_env("AUTH_SESSION_SAMESITE") or "lax").lower()
FRONTEND_BASE_URL = _read_optional_env("FRONTEND_BASE_URL")
GOOGLE_CLIENT_ID = _read_optional_env("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = _read_optional_env("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_REDIRECT_URI = _read_optional_env("GOOGLE_OAUTH_REDIRECT_URI")
GITHUB_AUTH_MODE = _read_optional_env("GITHUB_AUTH_MODE") or "disabled"
GITHUB_APP_ID = _read_optional_env("GITHUB_APP_ID")
GITHUB_APP_INSTALLATION_ID = _read_optional_env("GITHUB_APP_INSTALLATION_ID")
GITHUB_APP_PRIVATE_KEY = _read_optional_env("GITHUB_APP_PRIVATE_KEY")
GITLAB_AUTH_MODE = _read_optional_env("GITLAB_AUTH_MODE") or "disabled"
GITLAB_BASE_URL = _read_optional_env("GITLAB_BASE_URL") or "https://gitlab.com"
GITLAB_SERVICE_ACCOUNT_TOKEN = _read_optional_env("GITLAB_SERVICE_ACCOUNT_TOKEN")
AI_PLANNER_MODE = _read_optional_env("AI_PLANNER_MODE") or "bootstrap"
OPENAI_API_KEY = _read_optional_env("OPENAI_API_KEY")
OPENAI_BASE_URL = _read_optional_env("OPENAI_BASE_URL") or "https://api.openai.com/v1"
OPENAI_MODEL = _read_optional_env("OPENAI_MODEL") or "gpt-5.4-mini"
OPENAI_TIMEOUT_SECONDS = _read_optional_int_env("OPENAI_TIMEOUT_SECONDS", 20)

if AUTH_SESSION_TTL_SECONDS <= 0:
    raise RuntimeError("AUTH_SESSION_TTL_SECONDS must be a positive integer")

if AUTH_SESSION_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError(
        "AUTH_SESSION_SAMESITE must be one of: lax, strict, none"
    )

if AI_PLANNER_MODE not in {"bootstrap", "openai"}:
    raise RuntimeError(
        "AI_PLANNER_MODE must be one of: bootstrap, openai"
    )

if OPENAI_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("OPENAI_TIMEOUT_SECONDS must be a positive integer")
