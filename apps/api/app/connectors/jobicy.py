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
    prefilter_stats: dict | None = None,
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
        response.encoding = "utf-8"
    response.raise_for_status()
    data = response.json()

    items = data.get("jobs", []) if isinstance(data, dict) else []
    jobs: list[Job] = []
    seen_count = 0
    passed_count = 0
    rejected_titles: list[str] = []
    for item in items:
        title = item.get("jobTitle", "")
        tags = item.get("jobIndustry", []) or []
        seen_count += 1
        if not matches_role(title, tags, target_roles):
            if len(rejected_titles) < 10:
                rejected_titles.append(title)
            continue
        passed_count += 1
        if len(jobs) >= limit:
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
                employment_type=(item.get("jobType") or [None])[0] if isinstance(item.get("jobType"), list) else item.get("jobType"),
                location=location or None,
                allowed_regions=location or None,
                seniority=_extract_seniority(title),
                country=None,
                page_text=item.get("jobExcerpt", "") or "",
            )
        )
    if prefilter_stats is not None:
        prefilter_stats.update({"source": "jobicy.com", "seen": seen_count, "passed_prefilter": passed_count, "returned": len(jobs), "rejected_sample": rejected_titles, "target_roles": target_roles or []})
    return jobs
