"""Development auth stub with a single local user."""

from __future__ import annotations

from dataclasses import dataclass

from app.runtime.state import STATE


@dataclass(frozen=True)
class User:
    """Minimal user projection for API responses."""

    user_id: str
    email: str
    display_name: str


DEV_USER = User(
    user_id="local-dev-user",
    email="dev@sciscope.local",
    display_name="SciScope Demo User",
)


def get_current_user() -> User | None:
    """Return the active development user if signed in."""

    if STATE.current_user_id == DEV_USER.user_id:
        return DEV_USER
    return None


def sign_in_dev_user() -> User:
    """Activate the local development user."""

    STATE.current_user_id = DEV_USER.user_id
    return DEV_USER


def sign_out_current_user() -> None:
    """Clear the active development user."""

    STATE.current_user_id = None
