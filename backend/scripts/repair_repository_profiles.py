"""Preview or apply conditional provider refreshes for damaged catalog profiles."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json

from app.config import DATABASE_URL
from app.services.repositories import repair_repository_profiles
from app.composition.repositories import build_repository_adapters


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only (the default).")
    mode.add_argument("--apply", action="store_true", help="Write provider-confirmed profile changes.")
    parser.add_argument("--repository-id", action="append", default=[], help="Select a catalog ID; repeat to select several.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of provider lookups (default: 100).")
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    reports = repair_repository_profiles(
        load_repository_profile=build_repository_adapters().load_repository_profile,
        database_url=DATABASE_URL,
        apply=args.apply,
        repository_ids=args.repository_id,
        limit=args.limit,
    )
    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "profiles": [asdict(report) for report in reports],
    }, indent=2, default=_json_value))
    return 1 if any(report.status in {"failed", "skipped_changed"} for report in reports) else 0


def _json_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot encode {type(value).__name__}")


if __name__ == "__main__":
    raise SystemExit(main())
