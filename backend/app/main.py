"""Application entrypoint for the SciScope backend API."""

from __future__ import annotations

from pathlib import Path
import sys
from wsgiref.simple_server import make_server

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.routes import application


def main() -> None:
    """Run the local SciScope backend API."""

    host = "127.0.0.1"
    port = 8000
    print(f"SciScope backend running at http://{host}:{port}")
    try:
        with make_server(host, port, application) as server:
            server.serve_forever()
    except KeyboardInterrupt:
        print("\nSciScope backend stopped.")


if __name__ == "__main__":
    main()
