"""FastAPI application for the SciScope backend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.__version__ import __version__
from app.api.routes import auth as auth_routes
from app.api.routes import control as control_routes
from app.api.routes import dashboard as dashboard_routes
from app.api.routes import explore as explore_routes
from app.api.routes import signals as signal_routes
from app.api.routes import subscriptions as subscription_routes
from app.config import CORS_ORIGINS, DATABASE_URL
from app.database.session import check_database_connection
from app.services.search.access.errors import ExploreAccessDeniedError
from app.services.search.explore import (
    AiSearchPlanningError,
    ExploreSearchUnavailableError,
)


class ExploreSearchRequest(BaseModel):
    """Request body for one topic-driven explore search."""

    topicDescription: str = ""
    turnstileToken: str | None = None


class CreateSubscriptionRequest(BaseModel):
    """Request body for one direct repository subscription."""

    repository: dict[str, str] = Field(default_factory=dict)
    selectedQuery: str | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail fast if the configured database is unavailable at startup."""

    _app.state.database_url = DATABASE_URL
    check_database_connection(_app.state.database_url)
    yield


app = FastAPI(title="SciScope API", version=__version__, lifespan=lifespan)
app.state.database_url = DATABASE_URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.exception_handler(HTTPException)
async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return compact error payloads for expected API failures."""

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": str(exc.detail)},
    )


@app.exception_handler(ExploreSearchUnavailableError)
async def handle_explore_search_unavailable(
    _request: Request,
    exc: ExploreSearchUnavailableError,
) -> JSONResponse:
    """Return structured source diagnostics when every provider fails."""

    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": str(exc),
            "sourceStatuses": exc.source_statuses,
        },
    )


@app.exception_handler(AiSearchPlanningError)
async def handle_ai_search_planning_error(
    _request: Request,
    exc: AiSearchPlanningError,
) -> JSONResponse:
    """Return a compact error payload when AI planning is unavailable."""

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"error": str(exc)},
    )


@app.exception_handler(ExploreAccessDeniedError)
async def handle_explore_access_denied(
    _request: Request,
    exc: ExploreAccessDeniedError,
) -> JSONResponse:
    """Return structured rate-limit and access-denial payloads."""

    headers: dict[str, str] = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_payload(),
        headers=headers,
    )


@app.get("/")
def get_root() -> dict[str, object]:
    """Return a compact service description for the API root."""

    return dashboard_routes.get_root_payload()


@app.get("/health", response_class=PlainTextResponse)
def get_health() -> str:
    """Return a minimal liveness response."""

    return dashboard_routes.get_health_payload()


@app.get("/ready")
def get_ready(request: Request) -> dict[str, str]:
    """Return readiness status after checking the database connection."""

    check_database_connection(request.app.state.database_url)
    return {"status": "ok"}


@app.get("/api/me")
def get_me(request: Request) -> dict[str, object]:
    """Return the current viewer projection."""

    return auth_routes.get_me_response(request)


@app.get("/api/auth/google/start")
def start_google_auth() -> Response:
    """Start Google OAuth for one browser session."""

    return auth_routes.start_google_auth_response()


@app.get("/api/auth/google/callback")
def complete_google_auth(request: Request) -> Response:
    """Complete Google OAuth and create one first-party session."""

    return auth_routes.finish_google_auth_response(request)


@app.post("/api/logout")
def sign_out(request: Request, response: Response) -> dict[str, object]:
    """Clear the current user."""

    return auth_routes.logout_response(request, response)


@app.post("/api/start")
def start_scan(request: Request) -> dict[str, object]:
    """Start monitoring and return the refreshed status payload."""

    return control_routes.start_scan_response(request)


@app.post("/api/stop")
def stop_scan(request: Request) -> dict[str, object]:
    """Stop monitoring and return the refreshed status payload."""

    return control_routes.stop_scan_response(request)


@app.post("/api/explore/search")
def run_explore_search(
    request: Request,
    payload: ExploreSearchRequest,
) -> dict[str, object]:
    """Run one manual explore search."""

    return explore_routes.search_explore_response(request, payload.model_dump())


@app.post("/api/explore/search-jobs", status_code=status.HTTP_202_ACCEPTED)
def create_explore_search_job(
    request: Request,
    payload: ExploreSearchRequest,
) -> dict[str, object]:
    """Create one manual explore search job."""

    return explore_routes.create_explore_search_job_response(
        request,
        payload.model_dump(),
    )


@app.get("/api/explore/search-jobs/{job_id}")
def get_explore_search_job(job_id: str) -> dict[str, object]:
    """Return one manual explore search job snapshot."""

    payload = explore_routes.get_explore_search_job_response(job_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explore search job not found",
        )
    return payload


@app.get("/api/subscriptions")
def get_subscriptions(request: Request) -> dict[str, object]:
    """Return saved subscriptions for the current user."""

    payload = subscription_routes.get_subscription_list_response(request)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return payload


@app.post("/api/subscriptions", status_code=status.HTTP_201_CREATED)
def create_subscription(
    request: Request,
    payload: CreateSubscriptionRequest,
) -> dict[str, object]:
    """Create one subscription for the current user."""

    response_payload = subscription_routes.create_subscription_response(
        request,
        payload.model_dump(),
    )
    if response_payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return response_payload


@app.delete("/api/subscriptions/{subscription_id}")
def delete_subscription(request: Request, subscription_id: str) -> dict[str, bool]:
    """Delete one saved subscription for the current user."""

    deleted = subscription_routes.delete_subscription_response(request, subscription_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return {"deleted": True}


@app.get("/api/status")
def get_status(request: Request) -> dict[str, object]:
    """Return the current dashboard status payload."""

    return signal_routes.get_status_response(request)


@app.get("/api/signals")
def get_signals(request: Request) -> dict[str, object]:
    """Return the current signal list payload."""

    return signal_routes.get_signal_list_response(request)


@app.get("/api/signals/{item_id}")
def get_signal_detail(request: Request, item_id: str) -> dict[str, object]:
    """Return detail payload for one signal if present."""

    payload = signal_routes.get_signal_detail_response(request, item_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )
    return payload
