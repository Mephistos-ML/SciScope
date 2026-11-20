# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0


from app.services.search.explore import provenance


def test_fingerprint_is_stable_across_order_and_equivalent_numeric_representations(
    monkeypatch,
):
    original = provenance.build_evaluation_provenance(
        backend_revision="a" * 40,

        score_threshold=0,
    )
    monkeypatch.setattr(
        provenance,
        "LOCATION_WEIGHTS",
        dict(reversed(list(provenance.LOCATION_WEIGHTS.items()))),
    )
    reordered = provenance.build_evaluation_provenance(
        backend_revision="b" * 40,

        score_threshold=-0.0,
    )
    assert (
        original["configuration_fingerprint"] == reordered["configuration_fingerprint"]
    )
    assert original["backend_revision"] != reordered["backend_revision"]
    assert original["ranking_configuration"]["schema_version"] == 2
    assert original["configuration_fingerprint"].startswith("sha256:")


def test_each_ranking_parameter_is_part_of_the_fingerprint(monkeypatch):

    def fingerprint(threshold=0):
        return provenance.build_evaluation_provenance(
            backend_revision="a" * 40,

            score_threshold=threshold,
        )["configuration_fingerprint"]

    baseline = fingerprint()
    assert fingerprint(threshold=0.5) != baseline
    weights = dict(provenance.LOCATION_WEIGHTS)
    weights["name"] = 0.9
    monkeypatch.setattr(provenance, "LOCATION_WEIGHTS", weights)
    changed_weights = fingerprint()
    assert changed_weights != baseline
    monkeypatch.setattr(provenance, "RANKING_POLICY_VERSION", "future-policy")
    assert fingerprint() != changed_weights
