# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Versioned evaluation metadata for durable ranking reports and experiments."""

from hashlib import sha256
import json
from math import isfinite

from app.services.search.ranking.models import (
    PopularityBoostParameters,
    RANKING_POLICY_VERSION,
)
from app.services.search.ranking.score import LOCATION_WEIGHTS


def build_evaluation_provenance(
    *,
    backend_revision: str,
    popularity_boost: PopularityBoostParameters,
    score_threshold: float,
) -> dict[str, object]:
    """Serialize the complete ranking/visibility configuration and hash its values.

    Source revision is separate from the configuration identity. Data, queries,
    retrieval budgets and model training history require their own manifests.
    """
    if not isfinite(score_threshold) or score_threshold < 0:
        raise ValueError("score_threshold must be finite and nonnegative")
    configuration = {
        "schema_version": 1,
        "ranking_policy_version": RANKING_POLICY_VERSION,
        "location_weights": {
            key: float(value) if value else 0.0
            for key, value in LOCATION_WEIGHTS.items()
        },
        "popularity": {
            "max_bonus": float(popularity_boost.max_bonus)
            if popularity_boost.max_bonus
            else 0.0,
            "reference_stars": popularity_boost.reference_stars,
        },
        "score_threshold": float(score_threshold) if score_threshold else 0.0,
    }
    encoded = json.dumps(
        configuration, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return {
        "backend_revision": backend_revision,
        "ranking_configuration": configuration,
        "configuration_fingerprint": "sha256:" + sha256(encoded).hexdigest(),
    }
