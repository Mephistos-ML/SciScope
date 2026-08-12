"""Local sandbox for previewing AI-generated repository queries."""

from __future__ import annotations

import argparse
import json

from app.services.ai_planner import build_ai_search_plan
from app.services.ai_search_plans import serialize_ai_search_plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview one AI-generated search plan for a topic description.",
    )
    parser.add_argument(
        "topic_description",
        help="One raw topic description to send into the planner.",
    )
    parser.add_argument(
        "--scope",
        choices=("repositories", "all"),
        default="repositories",
        help="Requested search scope. 'all' currently maps to repository planning only.",
    )
    args = parser.parse_args()

    plan = build_ai_search_plan(
        topic_description=args.topic_description,
        search_scope=args.scope,
    )
    print(json.dumps(serialize_ai_search_plan(plan), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
