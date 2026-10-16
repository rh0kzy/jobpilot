"""Jobicy fast connector (public remote-jobs API)."""

from datetime import date

import httpx

from app.connectors.prefilter import matches_role
from app.core.models import Job
from app.extraction.extractor import _extract_seniority


async def fetch_jobs(
    limit: int = 50,
    target_roles: list[str] | None = None,
    tag: str | None = None,
    count: int = 50,
) -> list[Job]:
    url = "https://jobicy.com/api/v2/remote-jobs"
    params = {"count": min(limit, count)}
    if tag:
        params["tag"] = tag
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "JobPilot"},
        follow_redirects=True,
    ) as client:
        response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    items = data.get("jobs", []) if isinstance(data, dict) else []
    jobs: list[Job] = []
    for item in items:
        if len(jobs) >= limit:
            break
        title = item.get("jobTitle", "")
        tags = item.get("jobIndustry", []) or []
        if not matches_role(title, tags, target_roles):
            continue
        pub = item.get("pubDate")
        try:
            posted = date.fromisoformat(str(pub)[:10]) if pub else None
        except Exception:  # noqa: BLE001
            posted = None
        location = item.get("jobGeo", "")
        jobs.append(
            Job(
                title=title,
                company=item.get("companyName", ""),
                url=item.get("url", ""),
                original_url=item.get("url", ""),
                source="jobicy.com",
                posted_date=posted,
                work_mode="remote",
                employment_type=item.get("jobType"),
                location=location or None,
                allowed_regions=location or None,
                seniority=_extract_seniority(title),
                country=None,
                page_text=item.get("jobExcerpt", "") or "",
            )
        )
    return jobs
