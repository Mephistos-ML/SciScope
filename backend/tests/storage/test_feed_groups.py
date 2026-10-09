"""Publication immutability, ownership, and lifecycle against real persistence."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.models.persistence import PersistenceConflictError
from app.storage.auth.users import create_user, delete_user_account
from app.storage.feed.events import get_feed_event_for_user, mark_feed_event_read_for_user, upsert_feed_events
from app.storage.feed.groups import get_feed_update_group_for_user, publish_feed_update_groups
from app.storage.feed.retention import delete_feed_events_older_than
from tests.fixtures.database import build_test_database_url, migrate_test_database
from tests.fixtures.feed import feed_event, feed_group


@pytest.fixture
def database_url(tmp_path):
    url = build_test_database_url(tmp_path / "feed-groups.sqlite3")
    migrate_test_database(url)
    return url


def test_retry_keeps_publication_identity_timestamp_membership_and_read_state(database_url):
    events = (feed_event(), feed_event("commit:two"))
    group = feed_group(*events)
    publish_feed_update_groups(events, (group,), database_url=database_url)
    marked = mark_feed_event_read_for_user(group.user_id, events[0].event_id, database_url=database_url)
    publish_feed_update_groups(events, (replace(group, created_at=group.created_at + timedelta(hours=2)),), database_url=database_url)
    stored = get_feed_update_group_for_user(group.user_id, group.group_id, database_url=database_url)
    assert stored.created_at == group.created_at
    assert set(stored.event_ids) == set(group.event_ids)
    assert get_feed_event_for_user(group.user_id, events[0].event_id, database_url=database_url).read_at == marked.read_at
    assert get_feed_update_group_for_user("other-user", group.group_id, database_url=database_url) is None


def test_group_cannot_be_extended_and_failed_publication_rolls_back_new_events(database_url):
    original, added = feed_event(), feed_event("commit:later")
    group = feed_group(original)
    publish_feed_update_groups((original,), (group,), database_url=database_url)
    with pytest.raises(PersistenceConflictError):
        publish_feed_update_groups((added,), (replace(group, event_ids=(original.event_id, added.event_id)),), database_url=database_url)
    assert get_feed_event_for_user(group.user_id, added.event_id, database_url=database_url) is None
    assert get_feed_update_group_for_user(group.user_id, group.group_id, database_url=database_url).event_ids == (original.event_id,)


@pytest.mark.parametrize("scope", ["user_id", "subscription_id", "repository_id"])
def test_group_cannot_include_an_event_from_another_scope(database_url, scope):
    own, other = feed_event(), replace(feed_event("commit:other"), **{scope: "other"})
    upsert_feed_events((own, other), database_url=database_url)
    group = feed_group(own, other)
    with pytest.raises(PersistenceConflictError):
        publish_feed_update_groups((), (group,), database_url=database_url)
    assert get_feed_update_group_for_user(own.user_id, group.group_id, database_url=database_url) is None


def test_event_cannot_be_published_in_a_second_group(database_url):
    event = feed_event()
    first, second = feed_group(event), feed_group(event, publication_key="scan-2")
    publish_feed_update_groups((event,), (first,), database_url=database_url)
    with pytest.raises(PersistenceConflictError):
        publish_feed_update_groups((), (second,), database_url=database_url)
    assert get_feed_update_group_for_user(event.user_id, second.group_id, database_url=database_url) is None


def test_release_group_accepts_one_release_and_confirmed_commit_members(database_url):
    release, commit = feed_event("release:1", kind="release"), feed_event()
    group = feed_group(release, commit)
    publish_feed_update_groups((release, commit), (group,), database_url=database_url)
    assert set(get_feed_update_group_for_user(release.user_id, group.group_id, database_url=database_url).event_ids) == set(group.event_ids)


@pytest.mark.parametrize("kinds", [("release", "release"), ("commit", "release")])
def test_group_rejects_mismatched_event_kinds_atomically(database_url, kinds):
    events = tuple(feed_event(str(index), kind=kind) for index, kind in enumerate(kinds))
    group = feed_group(*events)
    with pytest.raises(PersistenceConflictError):
        publish_feed_update_groups(events, (group,), database_url=database_url)
    assert all(get_feed_event_for_user(event.user_id, event.event_id, database_url=database_url) is None for event in events)


def test_account_deletion_removes_its_groups_but_preserves_another_users_publication(database_url):
    create_user(user_id="user-1", email="one@example.com", display_name="One", database_url=database_url)
    own = feed_event()
    other = feed_event(user_id="user-2", subscription_id="sub-2")
    own_group, other_group = feed_group(own), feed_group(other)
    publish_feed_update_groups((own, other), (own_group, other_group), database_url=database_url)
    assert delete_user_account(own.user_id, database_url=database_url)
    assert get_feed_update_group_for_user(own.user_id, own_group.group_id, database_url=database_url) is None
    assert get_feed_update_group_for_user(other.user_id, other_group.group_id, database_url=database_url) is not None


def test_retention_removes_empty_groups_with_their_member_events(database_url):
    event = feed_event()
    group = feed_group(event)
    publish_feed_update_groups((event,), (group,), database_url=database_url)
    assert delete_feed_events_older_than(event.created_at + timedelta(days=1), database_url=database_url) == 1
    assert get_feed_update_group_for_user(event.user_id, group.group_id, database_url=database_url) is None


def test_retry_cannot_change_an_existing_groups_member_kind(database_url):
    event = feed_event()
    group = feed_group(event)
    publish_feed_update_groups((event,), (group,), database_url=database_url)
    with pytest.raises(PersistenceConflictError):
        publish_feed_update_groups((replace(event, kind="release"),), (group,), database_url=database_url)
    assert get_feed_event_for_user(event.user_id, event.event_id, database_url=database_url).kind == "commit"
