"""Arbeitnow fast connector."""

from datetime import datetime

import httpx

from app.core.models import Job


async def fetch_jobs(limit: int = 50) -> list[Job]:
    url = "https://arbeitnow.com/api/job-board-api"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for item in data.get("data", [])[:limit]:
        created = item.get("created_at")
        try:
            posted = datetime.fromtimestamp(created).date() if created else None
        except Exception:  # noqa: BLE001
            posted = None
        jobs.append(
            Job(
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                url=item.get("url", ""),
                source="arbeitnow.com",
                posted_date=posted,
                work_mode="remote" if item.get("remote") else None,
                country=None,
                page_text=item.get("description", ""),
            )
        )
    return jobs
