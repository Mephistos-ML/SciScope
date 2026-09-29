"""Authorized read access to private durable search run reports."""

from __future__ import annotations

from app.storage.search_runs import get_search_run_report


def read_search_run_report(
    *,
    run_id: str,
    user_id: str,
    database_url: str,
) -> dict[str, object] | None:
    """Return a private report only to the owning internal user."""

    report = get_search_run_report(run_id, database_url=database_url)
    if report is None:
        return None
    run = report["run"]
    if not isinstance(run, dict) or run.get("ownerUserId") != user_id:
        raise PermissionError("This search run does not belong to the current user.")
    return report
