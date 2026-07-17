"""Application entrypoint for the local SciScope dashboard."""

from __future__ import annotations

from pathlib import Path
import sys
from wsgiref.simple_server import make_server

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.web.routes import application


def main() -> None:
    """Run the local SciScope dashboard."""

    host = "127.0.0.1"
    port = 8000
    print(f"SciScope dashboard running at http://{host}:{port}")
    with make_server(host, port, application) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
