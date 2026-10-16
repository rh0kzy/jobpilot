"""Fetch individual postings from official ATS public endpoints."""

import re
from datetime import datetime
from urllib.parse import urlparse

import httpx

from app.core.models import Job
from app.extraction.extractor import (
    _clean,
    _extract_country,
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
                    "jobLocationType": item.get("workplaceType"),
                    "description": description,
                }
            ),
            employment_type=_extract_employment({"employmentType": cats.get("commitment")}),
            location=_clean(cats.get("location")),
            seniority=_extract_seniority(item.get("text")),
            page_text=description,
        )
    ]


def _ashby_board_name(url: str) -> str | None:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if parts else None


def _ashby_posting_key(url: str) -> str | None:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[1] if len(parts) > 1 else None


def _ashby_location(item: dict) -> str | None:
    direct = item.get("location")
    if isinstance(direct, str) and direct.strip():
        return _clean(direct)
    address = item.get("address")
    if isinstance(address, dict):
        postal = address.get("postalAddress")
        if not isinstance(postal, dict):
            postal = address
        parts = []
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            value = _clean(postal.get(key))
            if value and value not in parts:
                parts.append(value)
        if parts:
            return ", ".join(parts)
    return None


def _ashby_address_country(item: dict) -> str | None:
    address = item.get("address")
    if isinstance(address, dict):
        postal = address.get("postalAddress")
        if not isinstance(postal, dict):
            postal = address
        country = postal.get("addressCountry")
        if country:
            return _extract_country(country)
    return None


def _ashby_matches(item: dict, posting_key: str | None) -> bool:
    if not posting_key:
        return False
    for field in ("id", "jobId", "jobPostingId", "jobPostingID"):
        if str(item.get(field) or "") == posting_key:
            return True
    for field in ("jobUrl", "applyUrl", "url", "hostedUrl", "externalLink", "applyLink"):
        value = item.get(field)
        if isinstance(value, str) and posting_key in value:
            return True
    return False


async def _ashby_job(url: str) -> list[Job] | None:
    board = _ashby_board_name(url)
    if not board:
        return None
    posting_key = _ashby_posting_key(url)
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "JobPilot"}) as client:
        resp = await client.get(api_url)
    if resp.status_code >= 400:
        return None
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        return None
    items = data.get("jobs", []) if isinstance(data, dict) else []
    if not isinstance(items, list) or not items:
        return None

    chosen = None
    if posting_key:
        for item in items:
            if isinstance(item, dict) and _ashby_matches(item, posting_key):
                chosen = item
                break
    if chosen is None and posting_key is None and len(items) == 1:
        chosen = items[0] if isinstance(items[0], dict) else None
    if chosen is None and posting_key is not None and len(items) == 1:
        chosen = items[0] if isinstance(items[0], dict) else None
    if not isinstance(chosen, dict):
        return None

    title = _clean(chosen.get("title")) or ""
    if not title:
        return None
    is_remote = bool(chosen.get("isRemote"))
    workplace_type = chosen.get("workplaceType")
    work_mode = "remote" if is_remote else _extract_work_mode({"jobLocationType": workplace_type, "description": ""})
    description = chosen.get("descriptionPlain") or chosen.get("descriptionHtml") or ""
    description = _clean(description) or ""
    location = _ashby_location(chosen)
    company = _clean(
        chosen.get("organizationName") or chosen.get("organization") or board.replace("-", " ").replace("_", " ").title()
    )
    posted = _parse_date(chosen.get("publishedAt") or chosen.get("updatedAt"))
    employment_type = _extract_employment({"employmentType": chosen.get("employmentType")})
    country = _ashby_address_country(chosen)
    if country and not is_remote and not location:
        location = country
    job = Job(
        title=title,
        company=company or "",
        url=chosen.get("jobUrl") or chosen.get("applyUrl") or url,
        original_url=url,
        source=f"ashbyhq.com/{board}",
        posted_date=posted,
        work_mode=work_mode,
        employment_type=employment_type,
        location=location,
        country=country,
        remote_scope=None,
        allowed_regions=location if is_remote else None,
        seniority=_extract_seniority(title),
        page_text=re.sub(r"<[^>]+>", " ", description),
    )
    return [job]


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
