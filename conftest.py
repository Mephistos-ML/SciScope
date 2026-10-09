"""Repository-wide pytest plugin registration."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

pytest_plugins = ("tests.fixtures.postgres",)
