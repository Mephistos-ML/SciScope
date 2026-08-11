"""FastAPI application for the SciScope backend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.api.routes import auth as auth_routes
from app.api.routes import control as control_routes
from app.api.routes import dashboard as dashboard_routes
from app.api.routes import explore as explore_routes
from app.api.routes import signals as signal_routes
from app.api.routes import subscriptions as subscription_routes
from app.config import CORS_ORIGINS
from app.database.session import check_database_connection
from app.services.explore import ExploreSearchUnavailableError


class ExploreSearchRequest(BaseModel):
    """Request body for one topic-driven explore search."""

    topicDescription: str = ""
    profileQueryTerms: list[str] = Field(default_factory=list)


class CreateSubscriptionRequest(BaseModel):
    """Request body for one saved topic subscription."""

    topicDescription: str = ""
    profileQueryTerms: list[str] = Field(default_factory=list)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Fail fast if the configured database is unavailable at startup."""

    check_database_connection()
    yield


app = FastAPI(title="SciScope API", version="0.1.0", lifespan=lifespan)
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


@app.get("/")
def get_root() -> dict[str, object]:
    """Return a compact service description for the API root."""

    return dashboard_routes.get_root_payload()


@app.get("/health", response_class=PlainTextResponse)
def get_health() -> str:
    """Return a minimal liveness response."""

    return dashboard_routes.get_health_payload()


@app.get("/ready")
def get_ready() -> dict[str, str]:
    """Return readiness status after checking the database connection."""

    check_database_connection()
    return {"status": "ok"}


@app.get("/api/me")
def get_me(request: Request) -> dict[str, object]:
    """Return the current viewer projection."""

    return auth_routes.get_me_response(request)


@app.post("/api/logout")
def sign_out(request: Request, response: Response) -> dict[str, object]:
    """Clear the current user."""

    return auth_routes.logout_response(request, response)


@app.post("/api/start")
def start_scan() -> dict[str, object]:
    """Start monitoring and return the refreshed status payload."""

    return control_routes.start_scan_response()


@app.post("/api/stop")
def stop_scan() -> dict[str, object]:
    """Stop monitoring and return the refreshed status payload."""

    return control_routes.stop_scan_response()


@app.post("/api/explore/search")
def run_explore_search(payload: ExploreSearchRequest) -> dict[str, object]:
    """Run one manual explore search."""

    return explore_routes.search_explore_response(payload.model_dump())


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
def get_status() -> dict[str, object]:
    """Return the current dashboard status payload."""

    return signal_routes.get_status_response()


@app.get("/api/signals")
def get_signals() -> dict[str, object]:
    """Return the current signal list payload."""

    return signal_routes.get_signal_list_response()


@app.get("/api/signals/{item_id}")
def get_signal_detail(item_id: str) -> dict[str, object]:
    """Return detail payload for one signal if present."""

    payload = signal_routes.get_signal_detail_response(item_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signal not found",
        )
    return payload
