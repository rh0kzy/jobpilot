"""Arbeitnow fast connector."""

from datetime import datetime

import httpx

from app.connectors.prefilter import matches_role
from app.core.models import Job
from app.extraction.extractor import _extract_seniority


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
    prefilter_stats: dict | None = None,
) -> list[Job]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    params = {"search": search} if search else None
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "JobPilot"},
        follow_redirects=True,
    ) as client:
        response = await client.get(url, params=params)
        response.encoding = "utf-8"
    response.raise_for_status()
    data = response.json()

    jobs: list[Job] = []
    seen_count = 0
    passed_count = 0
    rejected_titles: list[str] = []
    for item in data.get("data", []):
        title = item.get("title", "")
        seen_count += 1
        if not matches_role(title, item.get("tags"), target_roles):
            if len(rejected_titles) < 10:
                rejected_titles.append(title)
            continue
        passed_count += 1
        if len(jobs) >= limit:
            continue
        posted = _as_date(item.get("created_at"))
        jobs.append(
            Job(
                title=title,
                company=item.get("company_name", ""),
                url=item.get("url", ""),
                original_url=item.get("url", ""),
                source="arbeitnow.com",
                posted_date=posted,
                work_mode="remote" if item.get("remote") else None,
                employment_type=(item.get("job_types") or [None])[0]
                if isinstance(item.get("job_types"), list)
                else item.get("job_types"),
                location=item.get("location"),
                allowed_regions=item.get("location") if item.get("remote") else None,
                seniority=_extract_seniority(title),
                country=None,
                page_text=item.get("description", ""),
            )
        )
    if prefilter_stats is not None:
        prefilter_stats.update({"source": "arbeitnow.com", "seen": seen_count, "passed_prefilter": passed_count, "returned": len(jobs), "rejected_sample": rejected_titles, "target_roles": target_roles or []})
    return jobs
