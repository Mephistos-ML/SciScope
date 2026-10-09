"""Authenticated grouped Feed transport and explicit response schemas."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.services.feed.groups import (
    get_feed_group_detail_payload, get_feed_groups_payload, mark_feed_group_read_payload,
)


class FeedMemberResponse(BaseModel):
    eventId: str
    subscriptionId: str
    repositoryId: str
    repositoryFullName: str
    repositorySource: str
    repositoryUrl: str
    selectedQuery: str | None
    title: str
    summary: str
    source: str
    signalKind: str
    url: str
    publishedAt: datetime | None
    createdAt: datetime | None
    readAt: datetime | None


class FeedReleaseResponse(FeedMemberResponse):
    rawText: str
    normalizedText: str
    metadata: dict[str, object]


class FeedGroupResponse(BaseModel):
    groupId: str
    subscriptionId: str
    repositoryId: str
    repositoryFullName: str
    repositorySource: str
    repositoryUrl: str
    selectedQuery: str | None
    kind: Literal["release", "commits"]
    title: str
    summary: str
    url: str
    publishedAt: datetime | None
    createdAt: datetime
    eventCount: int
    commitCount: int
    unreadEventCount: int
    isRead: bool


class FeedGroupsResponse(BaseModel):
    items: list[FeedGroupResponse]
    nextCursor: str | None
    hasMore: bool
    unreadCount: int


class FeedGroupDetailResponse(FeedGroupResponse):
    release: FeedReleaseResponse | None
    commits: list[FeedMemberResponse]
    nextCursor: str | None
    hasMore: bool


router = APIRouter(prefix="/api/feed/groups", tags=["feed"])


def _user_id(request: Request) -> str:
    user = get_current_user(request, database_url=request.app.state.database_url)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user.user_id


@router.get("", response_model=FeedGroupsResponse)
def list_groups(
    request: Request, limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=2048),
    state: Literal["all", "unread"] = "all", subscription_id: str | None = None,
) -> dict[str, object]:
    user_id = _user_id(request)
    try:
        return get_feed_groups_payload(user_id, database_url=request.app.state.database_url,
                                       limit=limit, cursor=cursor, state=state, subscription_id=subscription_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{group_id}", response_model=FeedGroupDetailResponse)
def group_detail(
    request: Request, group_id: str, limit: int = Query(default=10, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=2048),
) -> dict[str, object]:
    user_id = _user_id(request)
    try:
        payload = get_feed_group_detail_payload(user_id, group_id, database_url=request.app.state.database_url,
                                                limit=limit, cursor=cursor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if payload is None:
        raise HTTPException(status_code=404, detail="Feed group not found")
    return payload


@router.patch("/{group_id}", response_model=FeedGroupResponse)
def read_group(request: Request, group_id: str) -> dict[str, object]:
    payload = mark_feed_group_read_payload(_user_id(request), group_id, database_url=request.app.state.database_url)
    if payload is None:
        raise HTTPException(status_code=404, detail="Feed group not found")
    return payload
