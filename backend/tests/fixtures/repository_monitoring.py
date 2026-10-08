"""Provider HTTP fixtures shared by commit adapter and monitoring integration tests."""


from urllib.parse import parse_qs, urlsplit

from app.integrations.repositories.common.models import JsonResponse
from app.integrations.repositories.common.source_status import RepositorySourceError
from app.integrations.repositories.github.monitor import GitHubRepositoryMonitor

OLD_DATE = "2010-01-01T00:00:00Z"


def commit(sha, date=OLD_DATE):
    return {"sha": sha, "id": sha, "title": "Scientific change", "message": "Scientific change",
            "committed_date": date, "created_at": date,
            "commit": {"author": {"date": OLD_DATE}, "committer": {"date": date}, "message": "Scientific change"}}



def fake_provider(adapter, monkeypatch, items, *, head="new-head", fail_page=None, diverged=False):
    calls = []
    def fetch(url):
        calls.append(url)
        query = parse_qs(urlsplit(url).query)
        if "/branches/" in url:
            return JsonResponse(payload={"commit": {"sha": head, "id": head}}, url=url)
        if "?" not in url:
            return JsonResponse(payload={"default_branch": "main"}, url=url)
        page = int(query.get("page", ["1"])[0])
        if page == fail_page:
            raise RepositorySourceError(source="github" if isinstance(adapter, GitHubRepositoryMonitor) else "gitlab",
                                        status="timed_out", public_message="Timed out")
        if "/compare/" in url:
            payload = {"status": "diverged" if diverged else "ahead", "merge_base_commit": {"sha": "old-head"},
                       "total_commits": len(items), "commits": items[(page-1)*100:page*100]}
        elif "/repository/compare?" in url:
            assert query["straight"] == ["true"]
            reverse = query["from"] == [head]
            payload = {"commit": {"id": "old-head" if reverse else head},
                       "commits": ([commit("old-head")] if diverged else []) if reverse else items,
                       "compare_timeout": True}
        else:
            assert query.get("sha", query.get("ref_name")) == [head]
            assert "since" in query
            payload = items[(page-1)*100:page*100]
        return JsonResponse(payload=payload, url=url)
    monkeypatch.setattr(adapter.client, "fetch_json", fetch)
    return calls
