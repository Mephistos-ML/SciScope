"""Test bootstrap helpers."""

from __future__ import annotations

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_HOST", "127.0.0.1")
os.environ.setdefault("APP_PORT", "8000")
os.environ.setdefault(
    "CORS_ORIGINS",
    "http://localhost:5173,https://sciscope.uk,https://www.sciscope.uk",
)
os.environ.setdefault("DATABASE_URL", "sqlite:///backend/data/test-sciscope.sqlite3")
