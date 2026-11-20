"""Explicit scientific context is confined to planner input."""

import pytest

from app.models.scientific_domain import ScientificDomain
from app.services.ai.search_plans import format_search_plan_topic


@pytest.mark.parametrize("domain,label", [
    (ScientificDomain.PHYSICS, "Physics"),
    (ScientificDomain.CHEMISTRY, "Chemistry"),
    (ScientificDomain.MATERIALS_SCIENCE, "Materials Science"),
    (ScientificDomain.BIOLOGY_BIOINFORMATICS, "Biology & Bioinformatics"),
    (ScientificDomain.EARTH_ENVIRONMENTAL_SCIENCE, "Earth & Environmental Science"),
    (ScientificDomain.ASTRONOMY_SPACE_SCIENCE, "Astronomy & Space Science"),
    (ScientificDomain.MATHEMATICS_STATISTICS, "Mathematics & Statistics"),
    (ScientificDomain.COMPUTER_SCIENCE, "Computer Science"),
])
def test_domain_is_explicit_context_not_a_query_suffix(domain, label):
    question = "Which method should I use?"
    assert format_search_plan_topic(topic_description=question, scientific_domain=domain) == (
        f"Scientific domain: {label}\n\n{question}"
    )


def test_missing_context_preserves_existing_planner_input():
    question = "  Scientific question\nwith original whitespace  "
    assert format_search_plan_topic(topic_description=question) == question


@pytest.mark.parametrize("domain", ["unknown", "", 1, True])
def test_invalid_context_is_not_silently_ignored(domain):
    with pytest.raises(ValueError):
        format_search_plan_topic(topic_description="question", scientific_domain=domain)
