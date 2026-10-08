"""A watch's existing unique key makes concurrent creation idempotent."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.storage.subscriptions.subscriptions import create_subscription, list_subscriptions_for_user
from tests.conftest import build_test_database_url, migrate_test_database


def test_parallel_creation_returns_one_committed_subscription(tmp_path):
    url = build_test_database_url(tmp_path / "subscriptions.sqlite3")
    migrate_test_database(url)
    ready = Barrier(2)
    def create(query):
        ready.wait(timeout=5)
        return create_subscription(user_id="user", repository_id="github:repo:123", selected_query=query, database_url=url)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ("first query", "second query")))
    stored = list_subscriptions_for_user("user", database_url=url)
    assert len(stored) == 1
    assert results[0] == results[1] == stored[0]
    # Subsequent requests retain the winning watch and its original selected query.
    repeated = create_subscription(user_id="user", repository_id="github:repo:123", selected_query="replacement", database_url=url)
    assert repeated == stored[0]
    other = create_subscription(user_id="other-user", repository_id="github:repo:123", selected_query="other", database_url=url)
    assert other.subscription_id != stored[0].subscription_id
