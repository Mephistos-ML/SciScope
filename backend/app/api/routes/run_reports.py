"""Internal HTTP transport for durable Explore run reports."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.auth.service import get_current_user
from app.services.features.access import has_feature
from app.services.search.run_reports import read_search_run_report


def get_search_run_report_response(request: Request, run_id: str) -> dict[str, object] | None:
    """Authorize access to one private durable search report."""

    user = get_current_user(request, database_url=request.app.state.database_url)
    if user is None or not has_feature(user.email, "search_diagnostics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Search diagnostics access is required.",
        )
    try:
        return read_search_run_report(
            run_id=run_id,
            user_id=user.user_id,
            database_url=request.app.state.database_url,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
