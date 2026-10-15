"""HTTP fetcher with robots.txt, rate limiting, cache and fetch diagnostics."""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

BLOCKED_DOMAINS = {
    "linkedin.com",
    "www.linkedin.com",
    "indeed.com",
    "www.indeed.com",
    "glassdoor.com",
    "www.glassdoor.com",
}
_last_request: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


@dataclass
class FetchResult:
    url: str
    status: str
    html: str | None = None
    status_code: int | None = None
    cached: bool = False
    final_url: str = ""


def _cache_path(url: str, cache_dir: str) -> Path:
    return Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest() + ".html")


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


async def fetch_detailed(url: str, timeout: int = 30, cache_dir: str = "./.cache") -> FetchResult:
    domain = _domain(url)
    if domain in BLOCKED_DOMAINS:
        return FetchResult(url=url, status="blocked_by_blocklist", final_url=url)

    cached = _cache_path(url, cache_dir)
    if cached.exists():
        return FetchResult(
            url=url,
            status="ok",
            html=cached.read_text(encoding="utf-8", errors="ignore"),
            cached=True,
            final_url=url,
        )

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(robots_url)
        if response.status_code < 400:
            rp.parse(response.text.splitlines())
            if not rp.can_fetch("JobPilot", url):
                return FetchResult(url=url, status="blocked_by_robots", final_url=url)
    except httpx.TimeoutException:
        return FetchResult(url=url, status="robots_timeout", final_url=url)
    except Exception:  # noqa: BLE001, S110
        pass

    if domain in BLOCKED_DOMAINS:
        return FetchResult(url=url, status="blocked_by_blocklist", final_url=url)

    lock = _locks.setdefault(domain, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        if domain in _last_request and now - _last_request[domain] < 1.0:
            await asyncio.sleep(1.0 - (now - _last_request[domain]))
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers={"User-Agent": "JobPilot"},
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
        except httpx.TimeoutException:
            return FetchResult(url=url, status="timeout", final_url=url)
        except httpx.HTTPError as exc:
            status_response = getattr(exc, "response", None)
            return FetchResult(url=url, status="network_error", status_code=getattr(status_response, "status_code", None), final_url=url)
        _last_request[domain] = time.monotonic()

    final_domain = _domain(str(response.url))
    if final_domain in BLOCKED_DOMAINS:
        return FetchResult(url=url, status="redirected_to_blocked_domain", final_url=url)
    if response.status_code >= 400:
        return FetchResult(url=url, status=f"http_{response.status_code}", status_code=response.status_code, final_url=str(response.url))

    html = response.text
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cached.write_text(html, encoding="utf-8")
    return FetchResult(url=url, status="ok", html=html, status_code=response.status_code, final_url=str(response.url))


async def fetch(url: str, timeout: int = 30, cache_dir: str = "./.cache") -> str | None:
    result = await fetch_detailed(url, timeout=timeout, cache_dir=cache_dir)
    return result.html