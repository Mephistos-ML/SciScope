"""Configuration-backed feature access."""

from __future__ import annotations

from typing import Literal

from app.config import SEARCH_DIAGNOSTICS_USER_EMAILS

FeatureName = Literal["search_diagnostics"]


def get_enabled_features(email: str | None) -> tuple[FeatureName, ...]:
    """Return feature flags enabled for one authenticated email address."""

    normalized_email = (email or "").strip().lower()
    if normalized_email and normalized_email in SEARCH_DIAGNOSTICS_USER_EMAILS:
        return ("search_diagnostics",)
    return ()


def has_feature(email: str | None, feature: FeatureName) -> bool:
    """Return whether one email address is eligible for a feature."""

    return feature in get_enabled_features(email)
