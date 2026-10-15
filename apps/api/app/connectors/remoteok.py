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
    for item in data[1:] if isinstance(data, list) else []:
        if not isinstance(item, dict):
            continue
        title = item.get("position", "")
        tags = item.get("tags") or []
        if not matches_role(title, tags, target_roles):
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
                title=title,
                company=item.get("company", ""),
                url=item.get("url", ""),
                original_url=item.get("url", ""),
                source="remoteok.com",
                posted_date=posted,
                work_mode="remote",
                employment_type=None,
                location=item.get("location"),
                remote_eligibility=item.get("location"),
                seniority=_extract_seniority(title),
                country=None,
                page_text=item.get("description", ""),
            )
        )
    return jobs
