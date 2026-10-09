"""Seed authenticated Feed journeys through real publication and monitoring IO."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid5, NAMESPACE_URL

from app.config import AUTH_SESSION_COOKIE_NAME
from app.integrations.repositories.common.factories import build_repository_commit_signal, build_repository_release_signal
from app.integrations.repositories.common.models import RepositoryCommit, RepositoryRelease
from app.jobs.scan_subscriptions import run_repository_monitoring_scan
from app.models.monitoring import ReleaseCommitDetails, RepositoryActivity
from app.models.repository import Repository
from app.models.signal import Signal
from app.services.auth.service import create_authenticated_session
from app.services.feed.service import build_feed_event
from app.storage.auth.users import create_user
from app.storage.feed.groups import publish_feed_update_groups
from app.storage.repositories.repositories import upsert_repositories
from app.storage.subscriptions.subscriptions import create_subscription
from app.storage.subscriptions.watches import SubscriptionWatchRecord
from tests.fixtures.feed import feed_group


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
    def signal(name: str, *, kind: str = "commit", minutes: int = 0, profile: Repository = repository) -> Signal:
        published = now + timedelta(minutes=minutes)
        if kind == "release":
            return build_repository_release_signal(RepositoryRelease(
                "github", profile.full_name, name, name, f"{profile.url}/releases/tag/{name}",
                published, name, "Scientific software improvements",
            ))
        sha = f"{uuid5(NAMESPACE_URL, name).int:040x}"
        return build_repository_commit_signal(RepositoryCommit(
            "github", profile.full_name, sha, name, f"{profile.url}/commit/{sha}", published,
            branch="main", author_name="Researcher",
            body=f"{name}\n\nImprove numerical accuracy\nand simulation reproducibility.",
        ))
    # Closed older publications exceed the real 20-card list page without provider history IO.
    archive_watch = SubscriptionWatchRecord(archived.subscription_id, user.user_id, archive, "archive", archived.created_at)
    old_events = [replace(build_feed_event(signal(f"Archive update {index}", profile=archive, minutes=-(index + 1) * 1440),
                                           archive_watch), created_at=now - timedelta(days=index + 1))
                  for index in range(20)]
    publish_feed_update_groups(old_events, [feed_group(event, publication_key=event.event_id) for event in old_events],
                               database_url=database_url)

    confirmed = tuple(signal(f"Release commit {index:02d}") for index in range(23))
    partial = (signal("Partial commit 1"), signal("Partial commit 2"))
    unrelated = (signal("Independent commit 1", minutes=1), signal("Independent commit 2", minutes=1))
    releases = (signal("v2.0", kind="release", minutes=6), signal("v1.5", kind="release", minutes=4),
                signal("v1.0", kind="release", minutes=2))
    comparisons = {
        "v2.0": ReleaseCommitDetails("complete", confirmed, "b" * 40, confirmed[-1].payload["commit_sha"], 23),
        "v1.5": ReleaseCommitDetails("partial", partial, "c" * 40, "b" * 40, 5),
        "v1.0": ReleaseCommitDetails(),
    }

    class Monitor:
        def load_repository_activity(self, profile, **kwargs):
            return RepositoryActivity((*releases, *confirmed, *partial, *unrelated), True, True, unrelated[-1].payload["commit_sha"]) if profile.repository_id == repository.repository_id else RepositoryActivity((), True, True, old_events[0].metadata["commit_sha"])

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
