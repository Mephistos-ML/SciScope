"""Application configuration lives here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
MONITORING_INTERVAL_SECONDS = 7200  # 2 hours
POLLING_FREQUENCY_SECONDS = 30  # scheduler polling frequency: 30 seconds
DEFAULT_EXPLORE_QUOTA_WINDOW_SECONDS = 86400  # 24 hours


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


def _read_optional_float_env(name: str, default: float) -> float:
    raw_value = _read_optional_env(name)
    if not raw_value:
        return default

    try:
        return float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Environment variable {name} must be a number, got {raw_value!r}"
        ) from exc


def _read_required_csv_env(name: str) -> tuple[str, ...]:
    raw_value = _read_required_env(name)
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    if not values:
        raise RuntimeError(
            f"Environment variable {name} must contain at least one value"
        )
    return values


def _read_optional_csv_env(name: str) -> tuple[str, ...]:
    raw_value = _read_optional_env(name)
    if not raw_value:
        return ()
    return tuple(item.strip().lower() for item in raw_value.split(",") if item.strip())


REPLAY_FIXTURES_PATH = _read_optional_path_env(
    "REPLAY_FIXTURES_PATH",
    BACKEND_ROOT / "tests" / "fixtures" / "replay_signals.json",
)
APP_ENV = _read_required_env("APP_ENV")
APP_LOG_LEVEL = (_read_optional_env("APP_LOG_LEVEL") or "INFO").upper()
BETA_USER_EMAILS = _read_optional_csv_env("BETA_USER_EMAILS")
SEARCH_QUOTA_BYPASS_USER_EMAILS = _read_optional_csv_env(
    "SEARCH_QUOTA_BYPASS_USER_EMAILS"
)
APP_HOST = _read_required_env("APP_HOST")
APP_PORT = _read_required_int_env("APP_PORT")
CORS_ORIGINS = _read_required_csv_env("CORS_ORIGINS")
DATABASE_URL = _read_required_env("DATABASE_URL")
AUTH_SESSION_COOKIE_NAME = (
    _read_optional_env("AUTH_SESSION_COOKIE_NAME") or "sciscope_session"
)
AUTH_SESSION_COOKIE_DOMAIN = _read_optional_env("AUTH_SESSION_COOKIE_DOMAIN")
AUTH_SESSION_TTL_SECONDS = int(
    _read_optional_env("AUTH_SESSION_TTL_SECONDS") or "2592000"
)
AUTH_SESSION_SECURE = _read_bool_env("AUTH_SESSION_SECURE", APP_ENV == "production")
AUTH_SESSION_SAMESITE = (_read_optional_env("AUTH_SESSION_SAMESITE") or "lax").lower()
FRONTEND_BASE_URL = _read_optional_env("FRONTEND_BASE_URL")
EXPLORE_PUBLIC_GUEST_SEARCH_ENABLED = _read_bool_env(
    "EXPLORE_PUBLIC_GUEST_SEARCH_ENABLED",
    True,
)
EXPLORE_QUOTA_WINDOW_SECONDS = _read_optional_int_env(
    "EXPLORE_QUOTA_WINDOW_SECONDS",
    DEFAULT_EXPLORE_QUOTA_WINDOW_SECONDS,
)
EXPLORE_GUEST_DAILY_LIMIT = _read_optional_int_env("EXPLORE_GUEST_DAILY_LIMIT", 3)
EXPLORE_GUEST_COOLDOWN_SECONDS = _read_optional_int_env(
    "EXPLORE_GUEST_COOLDOWN_SECONDS",
    30,
)
EXPLORE_SUSPICIOUS_WINDOW_SECONDS = _read_optional_int_env(
    "EXPLORE_SUSPICIOUS_WINDOW_SECONDS",
    3600,
)
EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD = _read_optional_int_env(
    "EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD",
    3,
)
EXPLORE_USER_DAILY_LIMIT = _read_optional_int_env("EXPLORE_USER_DAILY_LIMIT", 25)
EXPLORE_USER_COOLDOWN_SECONDS = _read_optional_int_env(
    "EXPLORE_USER_COOLDOWN_SECONDS",
    8,
)
EXPLORE_GLOBAL_DAILY_LIMIT = _read_optional_int_env("EXPLORE_GLOBAL_DAILY_LIMIT", 250)
TURNSTILE_ENABLED = _read_bool_env("TURNSTILE_ENABLED", False)
TURNSTILE_SITE_KEY = _read_optional_env("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = _read_optional_env("TURNSTILE_SECRET_KEY")
TURNSTILE_VERIFY_TIMEOUT_SECONDS = _read_optional_int_env(
    "TURNSTILE_VERIFY_TIMEOUT_SECONDS",
    5,
)
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
EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS = _read_optional_int_env(
    "EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS",
    75,
)
EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS = _read_optional_int_env(
    "EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS",
    120,
)
EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS = _read_optional_int_env(
    "EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS",
    20,
)
EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS = _read_optional_int_env(
    "EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS",
    30,
)
EXPLORE_ADMISSION_MODE = _read_optional_env("EXPLORE_ADMISSION_MODE") or "enforced"
EXPLORE_SEARCH_RELEVANCE_CUTOFF = _read_optional_float_env(
    "EXPLORE_SEARCH_RELEVANCE_CUTOFF",
    50.0,
)
EXPLORE_LOCAL_MIN_STRONG_RESULTS = _read_optional_int_env(
    "EXPLORE_LOCAL_MIN_STRONG_RESULTS",
    10,
)
EXPLORE_LOCAL_REQUIRED_QUERY_COVERAGE = _read_optional_float_env(
    "EXPLORE_LOCAL_REQUIRED_QUERY_COVERAGE",
    0.80,
)
EXPLORE_LOCAL_MIN_QUERY_ALIGNMENT = _read_optional_float_env(
    "EXPLORE_LOCAL_MIN_QUERY_ALIGNMENT",
    0.80,
)
SEMANTIC_CATALOG_ENABLED = _read_bool_env("SEMANTIC_CATALOG_ENABLED", False)
SEMANTIC_EMBEDDING_MODEL = (
    _read_optional_env("SEMANTIC_EMBEDDING_MODEL") or "text-embedding-3-small"
)
SEMANTIC_EMBEDDING_DIMENSIONS = _read_optional_int_env(
    "SEMANTIC_EMBEDDING_DIMENSIONS",
    1536,
)
SEMANTIC_CATALOG_QUERY_LIMIT = _read_optional_int_env(
    "SEMANTIC_CATALOG_QUERY_LIMIT",
    20,
)
SEMANTIC_CATALOG_PROFILE_LIMIT = _read_optional_int_env(
    "SEMANTIC_CATALOG_PROFILE_LIMIT",
    20,
)
SEMANTIC_CATALOG_MIN_SIMILARITY = _read_optional_float_env(
    "SEMANTIC_CATALOG_MIN_SIMILARITY",
    0.72,
)
SEMANTIC_EMBEDDING_BATCH_SIZE = _read_optional_int_env(
    "SEMANTIC_EMBEDDING_BATCH_SIZE",
    100,
)
SEMANTIC_EMBEDDING_MAX_INPUT_CHARS = _read_optional_int_env(
    "SEMANTIC_EMBEDDING_MAX_INPUT_CHARS",
    6_000,
)
SEMANTIC_EMBEDDING_BATCH_MAX_CHARS = _read_optional_int_env(
    "SEMANTIC_EMBEDDING_BATCH_MAX_CHARS",
    40_000,
)

if APP_LOG_LEVEL not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
    raise RuntimeError(
        "APP_LOG_LEVEL must be one of: CRITICAL, DEBUG, ERROR, INFO, WARNING"
    )

if AUTH_SESSION_TTL_SECONDS <= 0:
    raise RuntimeError("AUTH_SESSION_TTL_SECONDS must be a positive integer")

if AUTH_SESSION_SAMESITE not in {"lax", "strict", "none"}:
    raise RuntimeError("AUTH_SESSION_SAMESITE must be one of: lax, strict, none")

if EXPLORE_QUOTA_WINDOW_SECONDS <= 0:
    raise RuntimeError("EXPLORE_QUOTA_WINDOW_SECONDS must be a positive integer")

if EXPLORE_GUEST_DAILY_LIMIT <= 0:
    raise RuntimeError("EXPLORE_GUEST_DAILY_LIMIT must be a positive integer")

if EXPLORE_GUEST_COOLDOWN_SECONDS <= 0:
    raise RuntimeError("EXPLORE_GUEST_COOLDOWN_SECONDS must be a positive integer")

if EXPLORE_SUSPICIOUS_WINDOW_SECONDS <= 0:
    raise RuntimeError("EXPLORE_SUSPICIOUS_WINDOW_SECONDS must be a positive integer")

if EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD <= 0:
    raise RuntimeError("EXPLORE_SUSPICIOUS_BLOCK_THRESHOLD must be a positive integer")

if EXPLORE_USER_DAILY_LIMIT <= 0:
    raise RuntimeError("EXPLORE_USER_DAILY_LIMIT must be a positive integer")

if EXPLORE_USER_COOLDOWN_SECONDS <= 0:
    raise RuntimeError("EXPLORE_USER_COOLDOWN_SECONDS must be a positive integer")

if EXPLORE_GLOBAL_DAILY_LIMIT <= 0:
    raise RuntimeError("EXPLORE_GLOBAL_DAILY_LIMIT must be a positive integer")

if TURNSTILE_ENABLED and (not TURNSTILE_SITE_KEY or not TURNSTILE_SECRET_KEY):
    raise RuntimeError(
        "TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY are required when TURNSTILE_ENABLED=true"
    )

if TURNSTILE_VERIFY_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("TURNSTILE_VERIFY_TIMEOUT_SECONDS must be a positive integer")

if AI_PLANNER_MODE not in {"bootstrap", "openai"}:
    raise RuntimeError("AI_PLANNER_MODE must be one of: bootstrap, openai")

if OPENAI_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("OPENAI_TIMEOUT_SECONDS must be a positive integer")

if EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS must be a positive integer")

if EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS <= 0:
    raise RuntimeError("EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS must be a positive integer")

if (
    EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS
    < EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS
):
    raise RuntimeError(
        "EXPLORE_SEARCH_HARD_TIMEOUT_SECONDS must be greater than or equal to EXPLORE_SEARCH_SOFT_TIMEOUT_SECONDS"
    )

if EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS <= 0:
    raise RuntimeError(
        "EXPLORE_SEARCH_REPOSITORY_LANE_TIMEOUT_SECONDS must be a positive integer"
    )

if EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS <= 0:
    raise RuntimeError(
        "EXPLORE_SEARCH_CODE_LANE_TIMEOUT_SECONDS must be a positive integer"
    )

if EXPLORE_ADMISSION_MODE not in {"off", "enforced"}:
    raise RuntimeError("EXPLORE_ADMISSION_MODE must be one of: off, enforced")

if not 0.0 <= EXPLORE_SEARCH_RELEVANCE_CUTOFF <= 100.0:
    raise RuntimeError(
        "EXPLORE_SEARCH_RELEVANCE_CUTOFF must be between 0 and 100"
    )

if EXPLORE_LOCAL_MIN_STRONG_RESULTS <= 0:
    raise RuntimeError("EXPLORE_LOCAL_MIN_STRONG_RESULTS must be a positive integer")

if not 0.0 < EXPLORE_LOCAL_REQUIRED_QUERY_COVERAGE <= 1.0:
    raise RuntimeError("EXPLORE_LOCAL_REQUIRED_QUERY_COVERAGE must be in (0, 1]")

if not 0.0 <= EXPLORE_LOCAL_MIN_QUERY_ALIGNMENT <= 1.0:
    raise RuntimeError("EXPLORE_LOCAL_MIN_QUERY_ALIGNMENT must be between 0 and 1")

if SEMANTIC_EMBEDDING_DIMENSIONS != 1536:
    raise RuntimeError(
        "SEMANTIC_EMBEDDING_DIMENSIONS must be 1536 for the current pgvector schema"
    )

if SEMANTIC_CATALOG_QUERY_LIMIT <= 0 or SEMANTIC_CATALOG_PROFILE_LIMIT <= 0:
    raise RuntimeError("Semantic catalog retrieval limits must be positive integers")

if not 0.0 <= SEMANTIC_CATALOG_MIN_SIMILARITY <= 1.0:
    raise RuntimeError("SEMANTIC_CATALOG_MIN_SIMILARITY must be between 0 and 1")

if SEMANTIC_EMBEDDING_BATCH_SIZE <= 0:
    raise RuntimeError("SEMANTIC_EMBEDDING_BATCH_SIZE must be a positive integer")

if SEMANTIC_EMBEDDING_MAX_INPUT_CHARS <= 0:
    raise RuntimeError("SEMANTIC_EMBEDDING_MAX_INPUT_CHARS must be a positive integer")

if SEMANTIC_EMBEDDING_BATCH_MAX_CHARS <= 0:
    raise RuntimeError("SEMANTIC_EMBEDDING_BATCH_MAX_CHARS must be a positive integer")
