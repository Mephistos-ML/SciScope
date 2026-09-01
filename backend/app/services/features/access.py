"""Configuration-backed feature access."""

from __future__ import annotations

from typing import Literal

from app.config import BETA_USER_EMAILS

FeatureName = Literal["explore_beta"]


def get_enabled_features(email: str | None) -> tuple[FeatureName, ...]:
    """Return feature flags enabled for one authenticated email address."""

    normalized_email = (email or "").strip().lower()
    if normalized_email and normalized_email in BETA_USER_EMAILS:
        return ("explore_beta",)
    return ()


def has_feature(email: str | None, feature: FeatureName) -> bool:
    """Return whether one email address is eligible for a feature."""

    return feature in get_enabled_features(email)
