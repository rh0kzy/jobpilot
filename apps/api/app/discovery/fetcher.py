"""HTTP fetcher with robots.txt, rate limiting, cache and blocklist."""

import asyncio
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

BLOCKED_DOMAINS = {"linkedin.com", "www.linkedin.com", "indeed.com", "www.indeed.com", "glassdoor.com", "www.glassdoor.com"}
_last_request: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}


def _cache_path(url: str, cache_dir: str) -> Path:
    return Path(cache_dir) / (hashlib.sha256(url.encode()).hexdigest() + ".html")


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


async def fetch(url: str, cache_dir: str = "./.cache", timeout: int = 30) -> str | None:
    domain = _domain(url)
    if domain in BLOCKED_DOMAINS:
        return None

    cached = _cache_path(url, cache_dir)
    if cached.exists():
        return cached.read_text(encoding="utf-8", errors="ignore")

    # robots.txt
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(robots_url)
        if r.status_code < 400:
            rp.parse(r.text.splitlines())
            if not rp.can_fetch("JobPilot", url):
                return None
    except Exception:  # noqa: BLE001, S110
        pass

    # per-domain rate limit
    lock = _locks.setdefault(domain, asyncio.Lock())
    async with lock:
        import time

        now = time.monotonic()
        if domain in _last_request and now - _last_request[domain] < 1.0:
            await asyncio.sleep(1.0 - (now - _last_request[domain]))
        async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "JobPilot"}) as client:
            resp = await client.get(url)
        _last_request[domain] = __import__("time").monotonic()
        if resp.status_code >= 400:
            return None
        html = resp.text

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cached.write_text(html, encoding="utf-8")
    return html
