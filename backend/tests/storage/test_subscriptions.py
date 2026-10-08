"""Repeated watches preserve their query and remain scoped to one user."""

from app.models.repository import Repository
from app.storage.auth.users import create_user
from app.storage.repositories import upsert_repositories
from app.storage.subscriptions.subscriptions import create_subscription, list_subscriptions_for_user
from tests.conftest import build_test_database_url, migrate_test_database


def test_repeated_creation_preserves_query_and_users_have_independent_subscriptions(tmp_path):
    url = build_test_database_url(tmp_path / "subscriptions.sqlite3")
    migrate_test_database(url)
    for user_id in ("user", "other-user"):
        create_user(user_id=user_id, email=f"{user_id}@example.test", display_name=user_id, database_url=url)
    upsert_repositories((Repository(
        repository_id="github:repo:123", source="github", provider_repository_id="123",
        full_name="science/tool", url="https://github.com/science/tool",
    ),), database_url=url)
    results = [create_subscription(user_id="user", repository_id="github:repo:123",
                                   selected_query=query, database_url=url)
               for query in ("first query", "second query")]
    stored = list_subscriptions_for_user("user", database_url=url)
    assert len(stored) == 1
    assert results[0] == results[1] == stored[0]
    assert stored[0].selected_query == "first query"
    repeated = create_subscription(user_id="user", repository_id="github:repo:123", selected_query="replacement", database_url=url)
    assert repeated == stored[0]
    other = create_subscription(user_id="other-user", repository_id="github:repo:123", selected_query="other", database_url=url)
    assert other.subscription_id != stored[0].subscription_id
