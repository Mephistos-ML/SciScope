"""Application entrypoint for the SciScope backend API."""

from __future__ import annotations

from pathlib import Path
import sys
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.app import app
from app.config import APP_HOST, APP_PORT


def main() -> None:
    """Run the SciScope backend API."""

    uvicorn.run(app, host=APP_HOST, port=APP_PORT)


if __name__ == "__main__":
    main()
