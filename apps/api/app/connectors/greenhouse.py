"""Greenhouse public boards connector (board tokens from a curated file)."""

import asyncio
import re
from datetime import datetime
from pathlib import Path

import httpx

from app.connectors.prefilter import matches_role
from app.core.models import Job
from app.extraction.classification import _url_is_single_job
from app.extraction.extractor import _extract_remote_eligibility, _extract_seniority


def _location_name(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    if value is None:
        return None
    return str(value).strip() or None

_BOARDS_FILE = Path(__file__).with_name("greenhouse_boards.txt")
_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


def _load_board_tokens() -> list[str]:
    if not _BOARDS_FILE.exists():
        return []
    return [line.strip() for line in _BOARDS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _company_from_token(token: str) -> str:
    return token.replace("-", " ").replace("_", " ").strip().title()


async def fetch_jobs(
    limit: int = 50,
    target_roles: list[str] | None = None,
    content: bool = True,
) -> list[Job]:
    jobs: list[Job] = []
    tokens = _load_board_tokens()
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "JobPilot"},
        follow_redirects=True,
    ) as client:
        for token in tokens:
            params = {"content": "true"} if content else None
            try:
                response = await client.get(f"{_BASE_URL}/{token}/jobs", params=params)
                response.raise_for_status()
            except Exception:  # noqa: BLE001, S112
                continue
            for item in response.json().get("jobs", []):
                if len(jobs) >= limit:
                    break
                title = item.get("title", "")
                if not matches_role(title, item.get("tags"), target_roles):
                    continue
                updated = item.get("updated_at")
                try:
                    posted = datetime.fromisoformat(updated).date() if updated else None
                except Exception:  # noqa: BLE001
                    posted = None
                text = re.sub(r"<[^>]+>", " ", item.get("content", "") or "")
                location = _location_name(item.get("location"))
                company_domain = item.get("absolute_url", "")
                job_id = item.get("id")
                canonical_url = f"https://boards.greenhouse.io/{token}/jobs/{job_id}"
                url = company_domain if _url_is_single_job(company_domain) else canonical_url
                jobs.append(
                    Job(
                        title=title,
                        company=item.get("company_name") or _company_from_token(token),
                        url=url,
                        original_url=company_domain if company_domain != url else None,
                        source=f"greenhouse.io/{token}",
                        posted_date=posted,
                        work_mode=None,
                        employment_type=None,
                        location=location,
                        remote_eligibility=_extract_remote_eligibility(
                            {"title": title, "description": text}
                        ),
                        seniority=_extract_seniority(title),
                        country=None,
                        page_text=text,
                    )
                )
            # small delay between board requests, below Greenhouse public crawl limits
            await asyncio.sleep(0.2)
    return jobs