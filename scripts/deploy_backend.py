#!/usr/bin/env python3
"""Deploy the clean current checkout to Fly with its source SHA embedded."""

import argparse
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

def deployment_command(root: Path) -> list[str]:
    from app.composition.revision import source_revision

    revision = source_revision(root, require_clean=True)
    return [
        "fly",
        "deploy",
        "--config",
        "fly.toml",
        "--build-arg",
        f"APP_REVISION={revision}",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        command = deployment_command(ROOT)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    if args.dry_run:
        print(shlex.join(command))
        return 0
    return subprocess.run(command, cwd=ROOT, timeout=1800).returncode


if __name__ == "__main__":
    raise SystemExit(main())
