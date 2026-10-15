"""Liveness checks for job pages."""

import httpx

CLOSED_PHRASES = [
    "no longer accepting",
    "position has been filled",
    "job is closed",
    "this job is no longer available",
    "application is closed",
]


def is_live(html: str) -> bool:
    text = (html or "").lower()
    return not any(phrase in text for phrase in CLOSED_PHRASES)


async def check_url(url: str, timeout: int = 30) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
    except Exception:  # noqa: BLE001
        return False
    if resp.status_code >= 400:
        return False
    return is_live(resp.text)
