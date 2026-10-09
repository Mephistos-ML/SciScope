"""Seed authenticated Feed journeys through real publication and monitoring IO."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.config import AUTH_SESSION_COOKIE_NAME
from app.jobs.scan_subscriptions import run_repository_monitoring_scan
from app.models.monitoring import ReleaseCommitDetails, RepositoryActivity
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.auth.service import create_authenticated_session
from app.storage.auth.users import create_user
from app.storage.feed.groups import publish_feed_update_groups
from app.storage.repositories.repositories import upsert_repositories
from app.storage.subscriptions.subscriptions import create_subscription
from tests.fixtures.feed import feed_event, feed_group


def seed_feed(database_url: str) -> dict[str, str]:
    user = create_user(email="feed@example.com", display_name="Feed Reader", database_url=database_url)
    repository = Repository("github:repo:123", "github", "science/tool", "https://github.com/science/tool")
    archive = Repository("github:repo:456", "github", "science/archive", "https://github.com/science/archive")
    upsert_repositories((repository, archive), database_url=database_url)
    subscription = create_subscription(user_id=user.user_id, repository_id=repository.repository_id,
                                       selected_query="simulation", database_url=database_url)
    archived = create_subscription(user_id=user.user_id, repository_id=archive.repository_id,
                                   selected_query="archive", database_url=database_url)
    now = datetime.now(UTC) + timedelta(minutes=1)
    # Closed older publications exceed the real 20-card list page without provider history IO.
    old_events = [replace(feed_event(f"commit:archive-{index}", user_id=user.user_id, subscription_id=archived.subscription_id),
                          repository_id=archive.repository_id, repository_full_name=archive.full_name,
                          repository_url=archive.url, title=f"Archive update {index}",
                          published_at=now - timedelta(days=index + 1), created_at=now - timedelta(days=index + 1))
                  for index in range(20)]
    publish_feed_update_groups(old_events, [feed_group(event, publication_key=event.event_id) for event in old_events],
                               database_url=database_url)

    def signal(name: str, *, kind: str = "commit", minutes: int = 0) -> Signal:
        return Signal("github", kind, f"science/tool:{kind}:{name}", name,
                      f"{repository.url}/{'releases/tag' if kind == 'release' else 'commit'}/{name}",
                      now + timedelta(minutes=minutes), f"{name}\n\nScientific software improvements",
                      payload={"repo": repository.full_name, "tag_name": name} if kind == "release" else {"repo": repository.full_name})

    confirmed = tuple(signal(f"Release commit {index:02d}") for index in range(23))
    partial = (signal("Partial commit 1"), signal("Partial commit 2"))
    unrelated = (signal("Independent commit 1", minutes=1), signal("Independent commit 2", minutes=1))
    releases = (signal("v2.0", kind="release", minutes=6), signal("v1.5", kind="release", minutes=4),
                signal("v1.0", kind="release", minutes=2))
    comparisons = {
        "v2.0": ReleaseCommitDetails("complete", confirmed, "b" * 40, "a" * 40, 23),
        "v1.5": ReleaseCommitDetails("partial", partial, "c" * 40, "b" * 40, 5),
        "v1.0": ReleaseCommitDetails(),
    }

    class Monitor:
        def load_repository_activity(self, profile, **kwargs):
            return RepositoryActivity((*releases, *confirmed, *partial, *unrelated), True, True, "head") if profile.repository_id == repository.repository_id else RepositoryActivity((), True, True, "archive-head")

        def load_release_commit_details(self, profile, release, **kwargs):
            return comparisons[release.title]

        def refresh_repository_profile(self, profile):
            return profile

    run_repository_monitoring_scan(resolve_monitor=lambda _source: Monitor(), database_url=database_url)
    return {
        "cookieName": AUTH_SESSION_COOKIE_NAME,
        "sessionToken": create_authenticated_session(user.user_id, database_url=database_url, ttl_seconds=3600),
        "subscriptionId": subscription.subscription_id,
    }
