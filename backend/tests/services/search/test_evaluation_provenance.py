# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

from dataclasses import replace

from app.services.search.explore import provenance
from app.services.search.ranking.models import PopularityBoostParameters


def test_fingerprint_is_stable_across_order_and_equivalent_numeric_representations(
    monkeypatch,
):
    original = provenance.build_evaluation_provenance(
        backend_revision="a" * 40,
        popularity_boost=PopularityBoostParameters(max_bonus=0),
        score_threshold=0,
    )
    monkeypatch.setattr(
        provenance,
        "LOCATION_WEIGHTS",
        dict(reversed(list(provenance.LOCATION_WEIGHTS.items()))),
    )
    reordered = provenance.build_evaluation_provenance(
        backend_revision="b" * 40,
        popularity_boost=PopularityBoostParameters(max_bonus=-0.0),
        score_threshold=-0.0,
    )
    assert (
        original["configuration_fingerprint"] == reordered["configuration_fingerprint"]
    )
    assert original["backend_revision"] != reordered["backend_revision"]
    assert original["ranking_configuration"]["schema_version"] == 1
    assert original["configuration_fingerprint"].startswith("sha256:")


def test_each_ranking_parameter_is_part_of_the_fingerprint(monkeypatch):
    parameters = PopularityBoostParameters()

    def fingerprint(boost=parameters, threshold=0):
        return provenance.build_evaluation_provenance(
            backend_revision="a" * 40,
            popularity_boost=boost,
            score_threshold=threshold,
        )["configuration_fingerprint"]

    baseline = fingerprint()
    assert fingerprint(replace(parameters, max_bonus=0.05)) != baseline
    assert fingerprint(replace(parameters, reference_stars=2000)) != baseline
    assert fingerprint(threshold=0.5) != baseline
    weights = dict(provenance.LOCATION_WEIGHTS)
    weights["name"] = 0.9
    monkeypatch.setattr(provenance, "LOCATION_WEIGHTS", weights)
    changed_weights = fingerprint()
    assert changed_weights != baseline
    monkeypatch.setattr(provenance, "RANKING_POLICY_VERSION", "future-policy")
    assert fingerprint() != changed_weights
