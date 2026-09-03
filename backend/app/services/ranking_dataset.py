"""Capture a labelled Explore beta job as an immutable ranking dataset run."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.models.ranking_dataset import RankingDatasetExample, RankingDatasetRun
from app.services.search.explore import get_explore_search_job
from app.storage.ranking_dataset import create_ranking_dataset_run

RANKING_POLICY_VERSION = "heuristic-v1"


def save_ranking_dataset_run(*, user_id: str, search_job_id: str, labels: dict[str, int], database_url: str) -> dict[str, object]:
    snapshot = get_explore_search_job(search_job_id)
    if snapshot is None:
        raise ValueError("Search job is no longer available. Run beta search again.")
    if snapshot.get("responseMode") != "beta" or snapshot.get("status") not in {"completed", "completed_partial"}:
        raise ValueError("Only a completed beta search can be saved as a dataset run.")
    if snapshot.get("ownerUserId") != user_id:
        raise ValueError("This beta search does not belong to the current user.")
    items = snapshot.get("items")
    if not isinstance(items, list):
        raise ValueError("Search job does not contain candidates.")
    candidates = [item for item in items if isinstance(item, dict) and isinstance(item.get("itemId"), str)]
    candidate_ids = {str(item["itemId"]) for item in candidates}
    if not labels or not set(labels).issubset(candidate_ids):
        raise ValueError("Labels must refer to candidates from this beta search.")
    if any(label not in {0, 1, 2} for label in labels.values()) or 2 not in labels.values():
        raise ValueError("Save at least one Golden label and use only 0, 1, or 2.")
    now = datetime.now(UTC)
    run_id = uuid4().hex
    plan = snapshot.get("aiSearchPlan")
    queries = tuple(str(query) for query in plan.get("queries", []) if isinstance(query, str)) if isinstance(plan, dict) else ()
    examples = tuple(_build_example(run_id, item, index + 1, labels.get(str(item["itemId"])), now) for index, item in enumerate(candidates))
    create_ranking_dataset_run(RankingDatasetRun(run_id, user_id, search_job_id, str(snapshot.get("topicDescription") or ""), queries, RANKING_POLICY_VERSION, len(examples), now), examples, database_url=database_url)
    return {"runId": run_id, "candidateCount": len(examples), "labeledCount": len(labels)}


def _build_example(run_id: str, item: dict[str, object], position: int, label: int | None, now: datetime) -> RankingDatasetExample:
    beta = item.get("beta") if isinstance(item.get("beta"), dict) else {}
    return RankingDatasetExample(run_id, str(item["itemId"]), str(item.get("source") or ""), str(item.get("fullName") or ""), str(item.get("url") or ""), position, float(item.get("score") or 0), {key: item.get(key) for key in ("description", "language", "stars", "providerUpdatedAt")}, dict(beta), label, now)
