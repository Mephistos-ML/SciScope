"""Path-strength check helpers for admission."""

from __future__ import annotations

from app.services.search.admission.models import AdmissionPathStrength
from app.services.search.admission.terms.path import (
    DESCRIPTIVE_PATH_EXTENSIONS,
    DESCRIPTIVE_PATH_HINTS,
    STRONG_PATH_EXTENSIONS,
    STRONG_PATH_SEGMENT_HINTS,
    WEAK_PATH_HINTS,
)


def classify_path_strength(path: str) -> AdmissionPathStrength:
    """Classify the strength of one matched repository path."""

    if not path:
        return "none"
    if any(hint in path for hint in STRONG_PATH_SEGMENT_HINTS):
        return "strong"
    if path.endswith(STRONG_PATH_EXTENSIONS):
        return "strong"
    if any(hint in path for hint in DESCRIPTIVE_PATH_HINTS):
        return "descriptive"
    if path.endswith(DESCRIPTIVE_PATH_EXTENSIONS):
        return "descriptive"
    if any(hint in path for hint in WEAK_PATH_HINTS):
        return "weak"
    return "none"
