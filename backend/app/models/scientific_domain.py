"""Stable scientific disciplines supplied as optional search context."""

from enum import Enum


class ScientificDomain(str, Enum):
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    MATERIALS_SCIENCE = "materials_science"
    BIOLOGY_BIOINFORMATICS = "biology_bioinformatics"
    EARTH_ENVIRONMENTAL_SCIENCE = "earth_environmental_science"
    ASTRONOMY_SPACE_SCIENCE = "astronomy_space_science"
    MATHEMATICS_STATISTICS = "mathematics_statistics"
    COMPUTER_SCIENCE = "computer_science"


def parse_scientific_domain(value: object) -> ScientificDomain | None:
    """Missing context is null; empty, unknown and non-string values are invalid."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid scientific domain")
    return ScientificDomain(value)
