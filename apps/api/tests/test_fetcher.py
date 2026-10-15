import asyncio

from app.discovery import fetcher


class FakeResponse:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad status")


class FakeClient:
    def __init__(self, get_map):
        self.get_map = get_map
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, *args, **kwargs):
        self.calls += 1
        return self.get_map(url)


def make_client_factory(get_map, bucket):
    def factory(*args, **kwargs):
        client = FakeClient(get_map)
        bucket["client"] = client
        return client

    return factory


def test_blocklist(monkeypatch):
    fetcher._last_request.clear()
    fetcher._locks.clear()
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", lambda *a, **k: None)
    assert asyncio.run(fetcher.fetch("https://www.linkedin.com/jobs/1")) is None


def test_robots_denied(monkeypatch, tmp_path):
    fetcher._last_request.clear()
    fetcher._locks.clear()

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nDisallow: /")
        return FakeResponse(200, "job page")

    bucket = {}
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", make_client_factory(get_map, bucket))

    result = asyncio.run(fetcher.fetch("https://example.com/job/1", cache_dir=str(tmp_path)))
    assert result is None


def test_cache_and_fetch(monkeypatch, tmp_path):
    fetcher._last_request.clear()
    fetcher._locks.clear()

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nAllow: /")
        return FakeResponse(200, "<html>job body</html>")

    calls = {"count": 0}

    class CountingClient(FakeClient):
        async def get(self, url, *args, **kwargs):
            calls["count"] += 1
            if url.endswith("/robots.txt"):
                return FakeResponse(200, "User-agent: *\nAllow: /")
            return FakeResponse(200, "<html>job body</html>")

    def factory(*a, **k):
        return CountingClient({})

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", factory)

    first = asyncio.run(fetcher.fetch("https://example.com/job/2", cache_dir=str(tmp_path)))
    second = asyncio.run(fetcher.fetch("https://example.com/job/2", cache_dir=str(tmp_path)))
    assert first == "<html>job body</html>"
    assert second == first
    # robots + page on first call only
    assert calls["count"] == 2