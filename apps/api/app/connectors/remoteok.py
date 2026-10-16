"""RemoteOK fast connector."""

from datetime import date

import httpx

from app.connectors.prefilter import matches_role
from app.core.models import Job
from app.extraction.extractor import _extract_seniority


async def fetch_jobs(
    limit: int = 50,
    target_roles: list[str] | None = None,
    tag: str | None = None,
    prefilter_stats: dict | None = None,
) -> list[Job]:
    url = "https://remoteok.com/api"
    params = {"tag": tag} if tag else None
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "JobPilot"},
        follow_redirects=True,
    ) as client:
        response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    jobs = []
    seen_count = 0
    passed_count = 0
    rejected_titles: list[str] = []
    for item in data[1:] if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        title = item.get("position", "")
        tags = item.get("tags") or []
        seen_count += 1
        if not matches_role(title, tags, target_roles):
            if len(rejected_titles) < 10:
                rejected_titles.append(title)
            continue
        passed_count += 1
        if len(jobs) >= limit:
            continue
        pub = item.get("date")
        try:
            posted = date.fromisoformat(pub[:10]) if pub else None
        except Exception:  # noqa: BLE001
            posted = None
        jobs.append(
            Job(
                title=title,
                company=item.get("company", ""),
                url=item.get("url", ""),
                original_url=item.get("url", ""),
                source="remoteok.com",
                posted_date=posted,
                work_mode="remote",
                employment_type=None,
                location=item.get("location"),
                allowed_regions=item.get("location"),
                seniority=_extract_seniority(title),
                country=None,
                page_text=item.get("description", ""),
            )
        )
    if prefilter_stats is not None:
        prefilter_stats.update({"source": "remoteok.com", "seen": seen_count, "passed_prefilter": passed_count, "returned": len(jobs), "rejected_sample": rejected_titles, "target_roles": target_roles or []})
    return jobs
