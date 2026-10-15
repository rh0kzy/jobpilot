"""RemoteOK fast connector."""

from datetime import date

import httpx

from app.core.models import Job


async def fetch_jobs(limit: int = 50) -> list[Job]:
    url = "https://remoteok.com/api"
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "JobPilot"}) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for item in data[1:] if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        if len(jobs) >= limit:
            break
        pub = item.get("date")
        try:
            posted = date.fromisoformat(pub[:10]) if pub else None
        except Exception:  # noqa: BLE001
            posted = None
        jobs.append(
            Job(
                title=item.get("position", ""),
                company=item.get("company", ""),
                url=item.get("url", ""),
                source="remoteok.com",
                posted_date=posted,
                work_mode="remote",
                country=None,
                page_text=item.get("description", ""),
            )
        )
    return jobs
