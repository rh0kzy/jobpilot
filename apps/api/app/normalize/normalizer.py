"""Job normalization, deduplication and freshness marking."""

from datetime import date, timedelta

from app.core.models import Job


def _norm_enum(value: str | None, allowed: set[str]) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    v = str(value).strip().lower()
    aliases = {
        "full time": "full_time",
        "full-time": "full_time",
        "part time": "part_time",
        "part-time": "part_time",
        "on-site": "onsite",
    }
    v = aliases.get(v, v)
    return v if v in allowed else None


def _norm_country(value: str | None) -> str | None:
    country = (value or "").strip().upper()
    return country or None


def normalize_job(job: Job) -> Job:
    work_mode = _norm_enum(job.work_mode, {"remote", "hybrid", "onsite"})
    employment_type = _norm_enum(
        job.employment_type,
        {"full_time", "part_time", "contract", "internship"},
    )
    return job.model_copy(
        update={
            "title": (job.title or "").strip(),
            "company": (job.company or "").strip(),
            "work_mode": work_mode,
            "employment_type": employment_type,
            "location": (job.location or "").strip() or None,
            "remote_eligibility": (job.remote_eligibility or "").strip() or None,
            "seniority": (job.seniority or "").strip() or None,
            "country": _norm_country(job.country),
        }
    )


def mark_freshness(
    jobs: list[Job],
    max_age_days: int = 60,
    today: date | None = None,
) -> list[Job]:
    """Flag freshness without dropping stale/unknown jobs."""
    today = today or date.today()
    cutoff = today - timedelta(days=max_age_days)
    marked: list[Job] = []
    for job in jobs:
        if job.posted_date is None:
            status = "unknown"
        elif job.posted_date < cutoff:
            status = "stale"
        else:
            status = "current"
        marked.append(job.model_copy(update={"freshness_status": status}))
    return marked


def dedupe(jobs: list[Job]) -> list[Job]:
    seen: set[tuple] = set()
    unique: list[Job] = []
    for job in jobs:
        key = (job.company.lower().strip(), job.title.lower().strip(), (job.country or "").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique
