import asyncio


def test_tavily_search_cache_hit(monkeypatch, tmp_path):
    from app.discovery import search

    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    calls = {"count": 0}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"url": "https://example.com/job/1"}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            calls["count"] += 1
            return FakeResponse()

    def factory(*args, **kwargs):
        return FakeClient()

    monkeypatch.setattr("httpx.AsyncClient", factory)

    provider = search.TavilySearch(api_key="secret", timeout=5)
    first = asyncio.run(provider.search("remote python", limit=3))
    assert calls["count"] == 1
    assert provider.last_cache_hit is False

    second = asyncio.run(provider.search("remote python", limit=3))
    assert calls["count"] == 1
    assert provider.last_cache_hit is True
    assert second == first


def test_query_generator_caps_queries():
    from app.core.models import Preferences, Profile
    from app.discovery.query_generator import generate_queries_with_metadata

    profile = Profile(job_titles=["Python Developer"], skills=["python", "fastapi", "react", "sql", "docker"])
    prefs = Preferences(work_modes=[], employment_types=[], countries=["WORLDWIDE"])
    queries = generate_queries_with_metadata(profile, prefs)
    assert len(queries) <= 15
    assert len({q.text for q in queries}) == len(queries)
