"""Remotive fast connector (respects published fetch limits)."""

import asyncio
import json
import os
import time
from datetime import date, datetime
from pathlib import Path

import httpx

from app.connectors.prefilter import matches_role
from app.core.models import Job
from app.extraction.extractor import _extract_seniority

DAILY_LIMIT = int(os.getenv("REMOTIVE_DAILY_LIMIT", "4"))
MIN_INTERVAL_SECONDS = int(os.getenv("REMOTIVE_MIN_INTERVAL_SECONDS", "30"))
CACHE_TTL_SECONDS = int(os.getenv("REMOTIVE_CACHE_TTL_SECONDS", str(6 * 3600)))


def _cache_dir() -> str:
    return os.getenv("CACHE_DIR", "./.cache")


def _paths(cache_dir: str) -> tuple[Path, Path]:
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root / "remotive_jobs.json", root / "remotive_meta.json"


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_jobs(raw: list) -> list[Job]:
    jobs = []
    for item in raw or []:
        try:
            jobs.append(Job(**item))
        except Exception:  # noqa: BLE001, S112
            continue
    return jobs


def _dump_jobs(jobs: list[Job]) -> list[dict]:
    return [job.model_dump(mode="json") for job in jobs]


def _should_refresh(meta: dict | None, now: float, jobs_cache: list[Job] | None) -> bool:
    if meta is None or jobs_cache is None:
        return True
    fetched_at = meta.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return True
    return (now - float(fetched_at)) >= CACHE_TTL_SECONDS


async def fetch_jobs(
    limit: int = 50,
    target_roles: list[str] | None = None,
    category: str | None = "software-dev",
    prefilter_stats: dict | None = None,
) -> list[Job]:
    cache_dir = _cache_dir()
    jobs_path, meta_path = _paths(cache_dir)
    now = time.time()
    today = datetime.now().date().isoformat()
    meta = _load_json(meta_path)
    cached_raw = _load_json(jobs_path)
    cached_jobs = _parse_jobs(cached_raw) if isinstance(cached_raw, list) else None

    if cached_jobs is not None and not _should_refresh(meta, now, cached_jobs):
        if prefilter_stats is not None:
            prefilter_stats.update({"source": "remotive.com", "seen": len(cached_jobs), "passed_prefilter": len(cached_jobs), "returned": len(cached_jobs[:limit]), "rejected_sample": [], "target_roles": target_roles or [], "cache_hit": True})
        return cached_jobs[:limit]

    if meta and meta.get("date") == today and int(meta.get("count", 0)) >= DAILY_LIMIT:
        # Keep attribution/link by returning the last cached result set.
        if prefilter_stats is not None:
            prefilter_stats.update({"source": "remotive.com", "seen": len(cached_jobs or []), "passed_prefilter": len(cached_jobs or []), "returned": len((cached_jobs or [])[:limit]), "rejected_sample": [], "target_roles": target_roles or [], "cache_hit": True})
        return (cached_jobs or [])[:limit]

    last_fetch = meta.get("last_fetch") if isinstance(meta, dict) else None
    if isinstance(last_fetch, (int, float)) and now - float(last_fetch) < MIN_INTERVAL_SECONDS:
        await asyncio.sleep(MIN_INTERVAL_SECONDS - (now - float(last_fetch)))

    url = "https://remotive.com/api/remote-jobs"
    params = {"category": category} if category else None
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
    for item in data.get("jobs", []):
        if len(jobs) >= limit:
            # Still account for remaining items in the feed totals.
            title = item.get("title", "")
            seen_count += 1
            if not matches_role(title, item.get("tags"), target_roles):
                if len(rejected_titles) < 10:
                    rejected_titles.append(title)
            else:
                passed_count += 1
            continue
        title = item.get("title", "")
        seen_count += 1
        if not matches_role(title, item.get("tags"), target_roles):
            if len(rejected_titles) < 10:
                rejected_titles.append(title)
            continue
        passed_count += 1
        pub = item.get("publication_date")
        try:
            posted = date.fromisoformat(pub[:10]) if pub else None
        except Exception:  # noqa: BLE001
            posted = None
        jobs.append(
            Job(
                title=title,
                company=item.get("company_name", ""),
                url=item.get("url", ""),
                original_url=item.get("url", ""),
                source="remotive.com",
                posted_date=posted,
                work_mode="remote",
                employment_type=item.get("job_type"),
                location=item.get("candidate_required_location"),
                allowed_regions=item.get("candidate_required_location"),
                seniority=_extract_seniority(title),
                country=None,
                page_text=item.get("description", ""),
            )
        )

    jobs_path.write_text(json.dumps(_dump_jobs(jobs), indent=2), encoding="utf-8")
    new_count = 1
    if meta and meta.get("date") == today:
        new_count = int(meta.get("count", 0)) + 1
    meta_path.write_text(
        json.dumps(
            {
                "date": today,
                "count": new_count,
                "last_fetch": time.time(),
                "fetched_at": time.time(),
            }
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(jobs_path, 0o600)
        os.chmod(meta_path, 0o600)
    except OSError:
        pass
    if prefilter_stats is not None:
        prefilter_stats.update(
            {
                "source": "remotive.com",
                "seen": seen_count,
                "passed_prefilter": passed_count,
                "returned": len(jobs),
                "rejected_sample": rejected_titles,
                "target_roles": target_roles or [],
            }
        )
    return jobs
