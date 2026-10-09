"""Publication identities and immutable membership have domain-owned invariants."""

from dataclasses import replace

import pytest

from app.models.feed import build_feed_update_group_id
from tests.fixtures.feed import feed_event, feed_group


@pytest.mark.parametrize("event_ids", [(), ("",), ("one", "one")])
def test_group_rejects_empty_or_duplicate_members(event_ids):
    with pytest.raises(ValueError):
        replace(feed_group(feed_event()), event_ids=event_ids)


def test_group_requires_a_known_kind_owner_and_aware_timestamp():
    group = feed_group(feed_event())
    for change in ({"kind": "unknown"}, {"user_id": ""}, {"created_at": group.created_at.replace(tzinfo=None)}):
        with pytest.raises(ValueError):
            replace(group, **change)


def test_publication_identity_is_stable_and_scoped_to_subscription_kind_and_key():
    identity = build_feed_update_group_id("sub", "commits", "scan-1")
    assert identity == build_feed_update_group_id("sub", "commits", "scan-1")
    assert len({identity, build_feed_update_group_id("other", "commits", "scan-1"),
                build_feed_update_group_id("sub", "release", "scan-1"),
                build_feed_update_group_id("sub", "commits", "scan-2")}) == 4
