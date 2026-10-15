import asyncio
from urllib.parse import urlparse

import httpx

from app.discovery import fetcher


class FakeResponse:
    def __init__(self, status, text, url):
        self.status_code = status
        self.text = text
        self.url = url

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


def _reset():
    fetcher._last_request.clear()
    fetcher._locks.clear()


def test_blocklist(monkeypatch):
    _reset()
    monkeypatch.setattr(fetcher.httpx, "AsyncClient", lambda *a, **k: None)
    assert asyncio.run(fetcher.fetch("https://www.linkedin.com/jobs/1")) is None


def test_robots_denied(monkeypatch, tmp_path):
    _reset()

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nDisallow: /", url)
        return FakeResponse(200, "job page", url)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", make_client_factory(get_map, {}))
    result = asyncio.run(fetcher.fetch_detailed("https://example.com/job/1", cache_dir=str(tmp_path)))
    assert result.status == "blocked_by_robots"
    assert result.html is None


def test_cache_and_fetch(monkeypatch, tmp_path):
    _reset()

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nAllow: /", url)
        return FakeResponse(200, "<html>job body</html>", url)

    calls = {"count": 0}

    class CountingClient(FakeClient):
        async def get(self, url, *args, **kwargs):
            calls["count"] += 1
            return get_map(url)

    def factory(*a, **k):
        return CountingClient(get_map)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", factory)

    first = asyncio.run(fetcher.fetch("https://example.com/job/2", cache_dir=str(tmp_path)))
    second = asyncio.run(fetcher.fetch("https://example.com/job/2", cache_dir=str(tmp_path)))
    assert first == "<html>job body</html>"
    assert second == first
    # robots + page on first call only
    assert calls["count"] == 2


def test_http_status_outcome(monkeypatch, tmp_path):
    _reset()

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nAllow: /", url)
        return FakeResponse(404, "not found", url)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", make_client_factory(get_map, {}))
    result = asyncio.run(fetcher.fetch_detailed("https://example.com/missing", cache_dir=str(tmp_path)))
    assert result.status == "http_404"
    assert result.status_code == 404


def test_timeout_outcome(monkeypatch, tmp_path):
    _reset()

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nAllow: /", url)
        raise httpx.TimeoutException("Timed out", request=None)

    def factory(*args, **kwargs):
        return FakeClient(get_map)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", factory)
    result = asyncio.run(fetcher.fetch_detailed("https://example.com/slow", cache_dir=str(tmp_path)))
    assert result.status == "timeout"


def test_network_error_outcome(monkeypatch, tmp_path):
    _reset()

    request = httpx.Request("GET", "https://example.com/network")
    error = httpx.ConnectError("boom", request=request)

    def get_map(url):
        if url.endswith("/robots.txt"):
            return FakeResponse(200, "User-agent: *\nAllow: /", url)
        raise error

    def factory(*args, **kwargs):
        return FakeClient(get_map)

    monkeypatch.setattr(fetcher.httpx, "AsyncClient", factory)
    result = asyncio.run(fetcher.fetch_detailed("https://example.com/network", cache_dir=str(tmp_path)))
    assert result.status == "network_error"
    assert urlparse("https://example.com/network").netloc
