"""Research topic to research profile generation lives here.

Architectural contract:

- this module builds one ``ResearchProfile`` from one ``ResearchTopic``
- it does not own active profiles in the system
- it does not store profile state
- it should stay source-agnostic
"""

from __future__ import annotations

from app.models.topic import ResearchProfile, ResearchTopic


def build_profile(topic: ResearchTopic) -> ResearchProfile:
    """Build one research profile from one topic.

    V0 keeps this unimplemented because active profiles still come from the seed
    layer. Once user-defined topics arrive, this becomes the source-agnostic
    transformation point.
    """

    raise NotImplementedError("Profile building from arbitrary topics is not implemented yet.")
