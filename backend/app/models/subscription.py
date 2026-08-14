"""Repository watch subscription models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Subscription:
    """One user-owned watch on one repository."""

    subscription_id: str
    user_id: str
    repository_id: str
    selected_query: str | None = None
    created_at: str | None = None
