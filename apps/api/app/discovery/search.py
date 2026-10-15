"""Web search provider interface and implementations."""

import httpx

from app.core import settings as runtime_settings
from app.core.settings_store import load_saved


class SearchProvider:
    async def search(self, query: str, limit: int = 10) -> list[str]:
        raise NotImplementedError


class TavilySearch(SearchProvider):
    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def search(self, query: str, limit: int = 10) -> list[str]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": self.api_key, "query": query, "max_results": limit},
            )
        resp.raise_for_status()
        data = resp.json()
        return [r.get("url", "") for r in data.get("results", []) if r.get("url")]


class BraveSearch(SearchProvider):
    def __init__(self, api_key: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def search(self, query: str, limit: int = 10) -> list[str]:
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
