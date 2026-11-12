#!/usr/bin/env python3
"""Check the release version copies without importing application startup."""

import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check_versions(root: Path) -> dict[str, str]:
    tree = ast.parse((root / "backend/app/__version__.py").read_text())
    backend = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
    )
    package = json.loads((root / "frontend/package.json").read_text())
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    versions = {
        "backend": backend,
        "frontend": package["version"],
        "lockfile": lock["version"],
        "lockfile root package": lock["packages"][""]["version"],
    }
    if not all(
        isinstance(v, str) and re.fullmatch(r"\d+\.\d+\.\d+", v)
        for v in versions.values()
    ):
        raise ValueError("Release versions must be numeric major.minor.patch strings")
    if len(set(versions.values())) != 1:
        raise ValueError(f"Release version mismatch: {versions}")
    return versions


if __name__ == "__main__":
    try:
        versions = check_versions(ROOT)
    except (ValueError, KeyError, StopIteration) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Release versions agree: {versions['backend']}")
