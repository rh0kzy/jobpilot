"""Remotive fast connector."""

from datetime import date

import httpx

from app.core.models import Job


async def fetch_jobs(limit: int = 50) -> list[Job]:
    url = "https://remotive.com/api/remote-jobs"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()
    jobs = []
    for item in data.get("jobs", [])[:limit]:
        pub = item.get("publication_date")
        try:
            posted = date.fromisoformat(pub[:10]) if pub else None
        except Exception:  # noqa: BLE001
            posted = None
        jobs.append(
            Job(
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                url=item.get("url", ""),
                source="remotive.com",
                posted_date=posted,
                work_mode="remote",
                employment_type=item.get("job_type"),
                country=None,
                page_text=item.get("description", ""),
            )
        )
    return jobs
