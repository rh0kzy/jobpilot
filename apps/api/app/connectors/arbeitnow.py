"""Arbeitnow fast connector."""

from datetime import datetime

import httpx

from app.connectors.prefilter import matches_role
from app.core.models import Job


def _as_date(created: object) -> object:
    try:
        if isinstance(created, (int, float)):
            return datetime.fromtimestamp(created).date()
        if isinstance(created, str) and created.isdigit():
            return datetime.fromtimestamp(int(created)).date()
    except Exception:  # noqa: BLE001
        return None
    return None


async def fetch_jobs(
    limit: int = 50,
    target_roles: list[str] | None = None,
    search: str | None = None,
) -> list[Job]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    params = {"search": search} if search else None
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "JobPilot"},
        follow_redirects=True,
    ) as client:
        response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    jobs: list[Job] = []
    for item in data.get("data", [])[:limit]:
        title = item.get("title", "")
        if not matches_role(title, item.get("tags"), target_roles):
            continue
        posted = _as_date(item.get("created_at"))
        jobs.append(
            Job(
                title=title,
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