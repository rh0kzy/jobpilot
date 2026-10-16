"""Job normalization, deduplication and freshness marking."""

from datetime import date, timedelta

from app.core.models import Job

_COUNTRY_ALIASES = {
    "CANADA": "CA",
    "COLOMBIA": "CO",
    "MEXICO": "MX",
    "BRAZIL": "BR",
    "BRASIL": "BR",
    "PORTUGAL": "PT",
    "SERBIA": "RS",
    "NORTH MACEDONIA": "MK",
    "MACEDONIA": "MK",
    "LATAM": "LATAM",
    "EMEA": "EMEA",
    "EU": "EU",
    "USA": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "FRANCE": "FR",
    "GERMANY": "DE",
    "ALGERIA": "DZ",
    "ALGERIE": "DZ",
    "WORLDWIDE": "WORLDWIDE",
}


def _to_iso(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    upper = text.upper()
    if upper in {"WORLDWIDE", "EMEA", "EU", "LATAM", "APAC"}:
        return upper
    if len(upper) == 2 and upper.isalpha():
        return upper
    return _COUNTRY_ALIASES.get(upper)

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
    code = _to_iso(value)
    if code is None:
        country = (value or "").strip().upper()
        if not country:
            return "unspecified"
        if country == "WORLDWIDE":
            return country
        return "unspecified"
    return code


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
        code = _to_iso(str(v)) or str(v).strip().upper()
        if not code:
            continue
        if len(code) > 2 and code not in {"WORLDWIDE", "EMEA", "EU", "LATAM", "APAC"}:
            continue
        if code not in out:
            out.append(code)
    return out


def normalize_job(job: Job) -> Job:
    title_text = (job.title or "").lower()
    work_mode = _norm_enum(
        job.work_mode, {"remote", "hybrid", "onsite", "unspecified"}, "unspecified"
    )
    employment_type = _norm_enum(
        job.employment_type,
        {"full_time", "part_time", "contract", "internship", "unspecified"},
        "unspecified",
    )
    if any(term in title_text for term in ("freelance", "contract", "consultant")):
        employment_type = "contract"
    seniority_text = (job.seniority or "").strip() or None
    seniority_level = job.seniority_level or _norm_seniority_level(
        " ".join(part for part in [seniority_text, job.title] if part)
    )
    if seniority_level not in _SENIORITY_LEVELS:
        seniority_level = _norm_seniority_level(seniority_level)

    # Derive ISO allowed countries from stated regions/locations when the source did not provide codes.
    explicit_worldwide = any(term in " / ".join(str(v) for v in [job.eligibility_evidence, job.allowed_regions, job.page_text, job.location] if v).lower() for term in ("worldwide", "anywhere in the world", "global", "anywhere"))
    derived_countries = list(job.allowed_countries or [])
    if not derived_countries and not explicit_worldwide:
        haystack = " / ".join(str(v) for v in [job.allowed_regions, job.location, job.eligibility_evidence, job.page_text] if v)
        for country_name, code in _COUNTRY_ALIASES.items():
            if code in derived_countries or code in {"WORLDWIDE", "LATAM", "EMEA", "EU", "APAC"}:
                continue
            if len(country_name) >= 4 and country_name.lower() in haystack.lower() and code not in derived_countries:
                derived_countries.append(code)
    job_allowed_countries = derived_countries if derived_countries else job.allowed_countries
    job = job.model_copy(update={"allowed_countries": job_allowed_countries})

    remote_scope = _norm_remote_scope(job.remote_scope)
    evidence_text = " / ".join(str(v) for v in [job.eligibility_evidence, job.allowed_regions, job.page_text] if v)
    lowered_evidence = evidence_text.lower()
    explicit_worldwide = any(term in lowered_evidence for term in ("worldwide", "anywhere in the world", "global", "anywhere"))
    # Never upgrade to worldwide unless evidence is explicit.
    if remote_scope == "worldwide" and not explicit_worldwide and job.remote_scope not in {"worldwide"}:
        remote_scope = "unclear"
    # If remote_scope lacks evidence, downgrade.
    if remote_scope == "worldwide" and not explicit_worldwide:
        remote_scope = "unclear"
    if remote_scope == "unclear":
        if any(term in evidence_text.lower() for term in ("worldwide", "global", "anywhere")):
            remote_scope = "worldwide"
        elif job.allowed_countries:
            remote_scope = "country_restricted"
        elif job.allowed_regions and job.allowed_regions.strip().lower() not in {"unspecified", ""}:
            remote_scope = "region_restricted"



    company = (job.company or "").strip()
    source = (job.source or "").strip()
    source_host = source.split("/", 1)[0].strip().lower()
    generic = company.lower() in {"", "unknown", "none", "n/a", "na", "company", "employer"} or company.lower() == source.lower()
    if not generic and source_host and source_host in company.lower().replace(" ", ""):
        generic = True
    if generic:
        company = "Unknown"
    confidence = job.confidence
    if generic:
        confidence = min(confidence if confidence is not None else 0.5, 0.4)

    eligibility_evidence = (job.eligibility_evidence or "").strip() or None
    if remote_scope == "worldwide":
        job = job.model_copy(update={"allowed_countries": []})
        if not (job.allowed_regions or "").strip():
            job = job.model_copy(update={"allowed_regions": "Worldwide"})
    if remote_scope != "unclear" and not eligibility_evidence:
        if remote_scope == "worldwide":
            eligibility_evidence = (evidence_text or "").strip()[:240] or None
        else:
            eligibility_evidence = (job.allowed_regions or job.location or job.timezone_restriction or "").strip() or None
    if remote_scope != "unclear" and not eligibility_evidence and job.allowed_countries:
        eligibility_evidence = ", ".join(job.allowed_countries)
    if remote_scope != "unclear" and not eligibility_evidence:
        remote_scope = "unclear"
    return job.model_copy(
        update={
            "title": (job.title or "").strip(),
            "company": company,
            "work_mode": work_mode,
            "employment_type": employment_type,
            "location": _clean_location(job.location),
            "country": _norm_country(job.country),
            "remote_scope": remote_scope,
            "allowed_countries": _clean_list(job.allowed_countries),
            "allowed_regions": (job.allowed_regions or "").strip() or None,
            "timezone_restriction": (job.timezone_restriction or "").strip() or None,
            "work_authorization_required": (job.work_authorization_required or "").strip() or None,
            "eligibility_evidence": eligibility_evidence,
            "confidence": confidence,
            "seniority": seniority_text,
            "seniority_level": seniority_level,
            "page_type": job.page_type,
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
