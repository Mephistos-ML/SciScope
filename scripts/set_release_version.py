#!/usr/bin/env python3
"""Synchronize the release version across backend and frontend metadata."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_VERSION_FILE = ROOT / "backend" / "app" / "__version__.py"
FRONTEND_PACKAGE_FILE = ROOT / "frontend" / "package.json"
FRONTEND_LOCK_FILE = ROOT / "frontend" / "package-lock.json"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: set_release_version.py <version>")

    version = sys.argv[1].strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"Invalid semantic version: {version!r}")

    update_backend_version(version)
    update_frontend_package(version)
    update_frontend_lock(version)
    return 0


def update_backend_version(version: str) -> None:
    content = BACKEND_VERSION_FILE.read_text(encoding="utf-8")
    if not re.search(r'__version__ = "[^"]+"', content):
        raise RuntimeError("Failed to locate backend __version__ assignment.")
    updated = re.sub(
        r'__version__ = "[^"]+"',
        f'__version__ = "{version}"',
        content,
        count=1,
    )
    BACKEND_VERSION_FILE.write_text(updated, encoding="utf-8")


def update_frontend_package(version: str) -> None:
    payload = json.loads(FRONTEND_PACKAGE_FILE.read_text(encoding="utf-8"))
    payload["version"] = version
    FRONTEND_PACKAGE_FILE.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def update_frontend_lock(version: str) -> None:
    payload = json.loads(FRONTEND_LOCK_FILE.read_text(encoding="utf-8"))
    payload["version"] = version

    root_package = payload.get("packages", {}).get("")
    if isinstance(root_package, dict):
        root_package["version"] = version

    FRONTEND_LOCK_FILE.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
