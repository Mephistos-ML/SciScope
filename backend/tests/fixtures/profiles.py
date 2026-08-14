"""Static subscription query-profile fixtures for backend tests."""

from __future__ import annotations

from app.models.subscription import SubscriptionQueryProfile


PNMR_PROFILE = SubscriptionQueryProfile(
    subscription_id="pnmr",
    topic_description=(
        "Paramagnetic NMR methods, susceptibility tensor fitting, PCS/PRE "
        "analysis, assignment workflows, and related scientific software."
    ),
    query_terms=(
        "paramagnetic nmr",
        "pseudocontact shift",
        "susceptibility tensor",
        "lanthanide assignment",
        "structure refinement",
    ),
)
