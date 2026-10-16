"""Job normalization, deduplication and freshness marking."""

from datetime import date, timedelta

from app.core.models import Job

_REMOTE_SCOPE_VALUES = {"worldwide", "region_restricted", "country_restricted", "unclear"}
_SENIORITY_LEVELS = {"junior", "mid", "senior", "lead", "unspecified"}


def _norm_enum(value: str | None, allowed: set[str], unspecified: str) -> str:
    if value is None or str(value).strip() == "":
        return unspecified
    v = str(value).strip().lower()
    aliases = {
        "full time": "full_time",
        "full-time": "full_time",
        "part time": "part_time",
        "part-time": "part_time",
        "on-site": "onsite",
        "on site": "onsite",
        "telecommute": "remote",
    }
    v = aliases.get(v, v)
    if v not in allowed:
        return unspecified
    return v


def _norm_country(value: str | None) -> str:
    country = (value or "").strip().upper()
    if not country:
        return "unspecified"
    if country == "WORLDWIDE":
        return country
    if len(country) != 2 or not country.isalpha():
        return "unspecified"
    return country


def _clean_location(value: str | None) -> str | None:
    if value is None:
        return None
    parts = [p.strip() for p in str(value).split(",")]
    deduped: list[str] = []
    for part in parts:
        if part and part not in deduped:
            deduped.append(part)
    text = ", ".join(deduped).strip(" ,")
    return text or None


def _norm_seniority_level(text: str | None) -> str:
    lowered = str(text or "").lower()
    if any(term in lowered for term in ("principal", "staff", "distinguished", "lead")):
        return "lead"
    if "senior" in lowered or "sr." in lowered or "sr " in lowered:
        return "senior"
    if any(term in lowered for term in ("junior", "jr.", "entry", "graduate", "intern")):
        return "junior"
    if any(term in lowered for term in ("mid", "middle")):
        return "mid"
    return "unspecified"


def _norm_remote_scope(value: str | None) -> str:
    v = str(value or "").strip().lower()
    if v in _REMOTE_SCOPE_VALUES:
        return v
    return "unclear"


def _clean_list(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for v in values:
        code = str(v).strip().upper()
        if code and code not in out:
            out.append(code)
    return out


def normalize_job(job: Job) -> Job:
    work_mode = _norm_enum(
        job.work_mode, {"remote", "hybrid", "onsite", "unspecified"}, "unspecified"
    )
    employment_type = _norm_enum(
        job.employment_type,
        {"full_time", "part_time", "contract", "internship", "unspecified"},
        "unspecified",
    )
    seniority_text = (job.seniority or "").strip() or None
    seniority_level = job.seniority_level or _norm_seniority_level(
        " ".join(part for part in [seniority_text, job.title] if part)
    )
    if seniority_level not in _SENIORITY_LEVELS:
        seniority_level = _norm_seniority_level(seniority_level)

    remote_scope = _norm_remote_scope(job.remote_scope)
    # Infer a coarse scope from evidence text when the source did not set one.
    if remote_scope == "unclear":
        text = " ".join(
            str(v) for v in [job.allowed_regions, job.timezone_restriction, job.page_text] if v
        ).lower()
        if any(term in text for term in ("worldwide", "global", "anywhere")):
            remote_scope = "worldwide"
        elif job.allowed_countries:
            remote_scope = "country_restricted"
        elif job.allowed_regions:
            remote_scope = "region_restricted"

    return job.model_copy(
        update={
            "title": (job.title or "").strip(),
            "company": (job.company or "").strip(),
            "work_mode": work_mode,
            "employment_type": employment_type,
            "location": _clean_location(job.location),
            "country": _norm_country(job.country),
            "remote_scope": remote_scope,
            "allowed_countries": _clean_list(job.allowed_countries),
            "allowed_regions": (job.allowed_regions or "").strip() or None,
            "timezone_restriction": (job.timezone_restriction or "").strip() or None,
            "work_authorization_required": (job.work_authorization_required or "").strip() or None,
            "eligibility_evidence": (job.eligibility_evidence or "").strip() or None,
            "seniority": seniority_text,
            "seniority_level": seniority_level,
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
