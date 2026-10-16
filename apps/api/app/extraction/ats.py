"""Fetch individual postings from official ATS public endpoints."""

import re
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.core.models import Job
from app.extraction.extractor import (
    _clean,
    _extract_employment,
    _extract_seniority,
    _extract_work_mode,
    _parse_date,
)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def detect_ats(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if "greenhouse" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    return None


async def _greenhouse_job(url: str) -> list[Job]:
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    # expected: {board}/jobs/{id}
    if len(path_parts) < 3 or path_parts[-2] != "jobs":
        return []
    board = path_parts[-3] if len(path_parts) >= 3 else path_parts[0]
    job_id = path_parts[-1]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "JobPilot"}) as client:
        resp = await client.get(api_url)
    if resp.status_code >= 400:
        return []
    item = resp.json()
    text = re.sub(r"<[^>]+>", " ", item.get("content", "") or "")
    posted = None
    try:
        posted = (
            datetime.fromisoformat(item.get("updated_at")).date()
            if item.get("updated_at")
            else None
        )
    except Exception:  # noqa: BLE001
        posted = None
    location = _location_name(item.get("location"))
    company_name = (
        item.get("company_name") or board.replace("-", " ").replace("_", " ").strip().title()
    )
    job = Job(
        title=_clean(item.get("title")) or "",
        company=_clean(company_name) or "",
        url=url,
        original_url=url,
        source=f"greenhouse.io/{board}",
        posted_date=posted,
        work_mode=_extract_work_mode({"description": text}),
        employment_type=_extract_employment(item),
        location=location,
        country=None,
        page_text=text,
        seniority=_extract_seniority(item.get("title")),
    )
    return [job]


def _location_name(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _lever_job(url: str) -> list[Job]:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return []
    site = parts[0]
    posting_id = parts[1]
    api_url = f"https://api.lever.co/v0/postings/{site}/{posting_id}"
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "JobPilot"}) as client:
        resp = await client.get(api_url)
    if resp.status_code >= 400:
        return []
    item = resp.json()
    if not isinstance(item, dict):
        return []
    description = item.get("descriptionPlain") or item.get("description") or ""
    created = item.get("createdAt")
    posted = None
    if created:
        try:
            posted = datetime.fromtimestamp(created / 1000).date()
        except Exception:  # noqa: BLE001
            posted = _parse_date(created)
    cats = item.get("categories") or {}
    return [
        Job(
            title=_clean(item.get("text")) or "",
            company=_clean(site.replace("-", " ").title()) or "",
            url=item.get("hostedUrl") or url,
            original_url=url,
            source="jobs.lever.co",
            posted_date=posted,
            work_mode=_extract_work_mode(
                {
                    "jobLocationType": cats.get("commitment") and "remote" or None,
                    "description": description,
                }
            ),
            employment_type=_extract_employment({"employmentType": cats.get("commitment")}),
            location=_clean(cats.get("location")),
            seniority=_extract_seniority(item.get("text")),
            page_text=description,
        )
    ]


async def _ashby_job(url: str) -> list[Job] | None:
    # No documented per-posting public endpoint in this lightweight adapter;
    # return None to use the normal fetch/extraction path.
    return None


async def fetch_ats_job(url: str) -> list[Job] | None:
    ats = detect_ats(url)
    if ats == "greenhouse":
        try:
            return await _greenhouse_job(url)
        except Exception:  # noqa: BLE001
            return None
    if ats == "lever":
        try:
            return await _lever_job(url)
        except Exception:  # noqa: BLE001
            return None
    if ats == "ashby":
        try:
            return await _ashby_job(url)
        except Exception:  # noqa: BLE001
            return None
    return None
