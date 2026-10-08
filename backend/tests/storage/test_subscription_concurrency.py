"""A watch's existing unique key makes concurrent creation idempotent."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.models.repository import Repository
from app.storage.auth.users import create_user
from app.storage.repositories import upsert_repositories
from app.storage.subscriptions.subscriptions import create_subscription, list_subscriptions_for_user
from tests.conftest import build_test_database_url, migrate_test_database


def test_parallel_creation_returns_one_committed_subscription(tmp_path):
    url = build_test_database_url(tmp_path / "subscriptions.sqlite3")
    migrate_test_database(url)
    for user_id in ("user", "other-user"):
        create_user(user_id=user_id, email=f"{user_id}@example.test", display_name=user_id, database_url=url)
    upsert_repositories((Repository(
        repository_id="github:repo:123", source="github", provider_repository_id="123",
        full_name="science/tool", url="https://github.com/science/tool",
    ),), database_url=url)
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
