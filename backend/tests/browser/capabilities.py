"""Deterministic external capabilities with an explicitly released IO boundary."""

from collections.abc import Sequence
import os
from time import monotonic
from urllib.parse import urlencode
from urllib.request import urlopen

from app.models.ai import AiPlannerIdentity, AiSearchPlan
from app.models.signal import Signal
from app.services.ai.planner import AiSearchPlanner
from app.services.search.explore.dependencies import ExploreDependencies
from app.services.search.retrieval.models import RetrievalLane

QUERIES = ("protein folding", "molecular docking", "genome analysis")


def plan(*, topic_description: str) -> AiSearchPlan:
    return AiSearchPlan(status="ready", queries=QUERIES)


def discover(
    queries: Sequence[str], *, deadline_monotonic: float | None
) -> list[Signal]:
    """Wait at test provider IO, respecting the caller's retrieval deadline."""
    assert len(queries) == 1
    query = queries[0]
    timeout = (
        20.0
        if deadline_monotonic is None
        else max(0.1, min(20.0, deadline_monotonic - monotonic()))
    )
    url = (
        os.environ["SCISCOPE_E2E_PROVIDER_URL"]
        + "/retrieve?"
        + urlencode({"query": query})
    )
    with urlopen(url, timeout=timeout) as response:
        response.read()
    index = QUERIES.index(query) + 1
    return [
        Signal(
            source="github",
            kind="repository",
            item_id=f"github:repo:{index}",
            title=f"science/{query.replace(' ', '-')}",
            url=f"https://github.com/science/{query.replace(' ', '-')}",
            published_at=None,
            raw_text=f"Repository: science/{query.replace(' ', '-')}\nDescription: {query} simulation software\nLanguage: Python",
            payload={
                "repo": f"science/{query.replace(' ', '-')}",
                "provider_repository_id": str(index),
                "author": "science",
                "description": f"{query} simulation software",
                "language": "Python",
                "stars": 100,
                "topics": [query],
                "query": query,
            },
        )
    ]


def dependencies() -> ExploreDependencies:
    return ExploreDependencies(
        planner=AiSearchPlanner(plan, AiPlannerIdentity("browser-fixture", None, None)),
        lanes=(RetrievalLane("github", "repository_search", discover),),
        embeddings=None,
    )


def provider_stage(query: str) -> str:
    return "initial" if query == QUERIES[0] else "expansion"
