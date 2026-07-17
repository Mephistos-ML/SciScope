"""Application configuration lives here."""

from pathlib import Path

AUTO_SCAN_INTERVAL_SECONDS = 300
REPLAY_FIXTURES_PATH = Path(__file__).resolve().parents[1] / "data" / "replay_signals.json"
