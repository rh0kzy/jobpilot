"""Web search provider interface and implementations."""

import json
import os
import time
from pathlib import Path

import httpx

from app.core import settings as runtime_settings
from app.core.settings_store import load_saved


def _cache_dir() -> str:
    return os.getenv("CACHE_DIR", "./.cache")


def _cache_path() -> Path:
    root = Path(_cache_dir())
    root.mkdir(parents=True, exist_ok=True)
    return root / "search_cache.json"


def _read_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(data: dict) -> None:
    path = _cache_path()
    try:
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


_CACHE_TTL = 24 * 3600


class SearchProvider:
    async def search(self, query: str, limit: int = 10) -> list[str]:
        raise NotImplementedError


class TavilySearch(SearchProvider):
    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.last_cache_hit = False
        self.last_cache_hit = False

    async def search(self, query: str, limit: int = 10) -> list[str]:
        key = f"tavily::{query}::{limit}"
        cache = _read_cache()
        entry = cache.get(key)
        if entry and time.time() - entry.get("time", 0) < _CACHE_TTL:
            self.last_cache_hit = True
            return list(entry.get("urls", []))
        self.last_cache_hit = False
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": self.api_key, "query": query, "max_results": limit},
            )
        resp.raise_for_status()
        data = resp.json()
        urls = [r.get("url", "") for r in data.get("results", []) if r.get("url")]
        cache[key] = {"time": time.time(), "urls": urls}
        _write_cache(cache)
        return urls


class BraveSearch(SearchProvider):
    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.last_cache_hit = False
        self.last_cache_hit = False

    async def search(self, query: str, limit: int = 10) -> list[str]:
        key = f"brave::{query}::{limit}"
        cache = _read_cache()
        entry = cache.get(key)
        if entry and time.time() - entry.get("time", 0) < _CACHE_TTL:
            self.last_cache_hit = True
            return list(entry.get("urls", []))
        self.last_cache_hit = False
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": limit},
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            )
        resp.raise_for_status()
        data = resp.json()
        urls = []
        for item in data.get("web", {}).get("results", []):
            if item.get("url"):
                urls.append(item["url"])
        cache[key] = {"time": time.time(), "urls": urls}
        _write_cache(cache)
        return urls


def get_search_provider() -> SearchProvider:
    settings = runtime_settings.get_settings()
    saved = load_saved()
    provider = (saved.search_provider or settings.search_provider).lower()
    key = runtime_settings.resolve_search_key(settings, saved.search_provider, saved.search_api_key)
    if provider == "tavily":
        if not key:
            raise ValueError("Tavily API key missing")
        return TavilySearch(api_key=key, timeout=settings.request_timeout)
    if provider == "brave":
        if not key:
            raise ValueError("Brave API key missing")
        return BraveSearch(api_key=key, timeout=settings.request_timeout)
    raise ValueError(f"Unknown search provider: {provider}")
