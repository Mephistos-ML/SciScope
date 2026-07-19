"""Application configuration lives here."""

import os
from pathlib import Path

APP_VERSION = "0.1.0"
DISCOVERY_INTERVAL_SECONDS = 86400  # 24 hours
MONITORING_INTERVAL_SECONDS = 7200  # 2 hours
POLLING_FREQUENCY_SECONDS = 30  # scheduler polling frequency: 30 seconds
REPLAY_FIXTURES_PATH = Path(__file__).resolve().parents[2] / "data" / "replay_signals.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "").strip()
