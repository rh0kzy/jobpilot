"""Job normalization and deduplication."""

import re

from app.core.models import Job


def _norm_work_mode(value: str | None, text: str) -> str:
    haystack = f"{value or ''} {text or ''}".lower()
    if "hybrid" in haystack or "télétravail partiel" in haystack:
        return "hybrid"
    if (
        "remote" in haystack
        or "telecommute" in haystack
        or "work from home" in haystack
        or "à distance" in haystack
        or "a distance" in haystack
    ):
        return "remote"
    if "on-site" in haystack or "onsite" in haystack or "on site" in haystack or "présence" in haystack:
        return "onsite"
    v = (value or "").strip().lower()
    if v in {"remote", "hybrid", "onsite"}:
        return v
    return "unspecified"


def _contains(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) for term in terms)


def _norm_employment(value: str | None, text: str) -> str:
    haystack = f"{value or ''} {text or ''}".lower()
    if _contains(haystack, ("internship", "intern", "stage", "apprenticeship")):
        return "internship"
    if _contains(haystack, ("part time", "part-time", "mi-temps", "temps partiel")):
        return "part_time"
    if _contains(haystack, ("contract", "contrat", "freelance", "independent contractor", "temporary")):
        return "contract"
    if _contains(haystack, ("full time", "full-time", "cdi", "temps plein", "permanent")):
        return "full_time"
    return "unspecified"


def _norm_country(value: str | None) -> str:
    return (value or "").strip().upper() or "unspecified"


def normalize_job(job: Job) -> Job:
    title = (job.title or "").strip()
    company = (job.company or "").strip()
    text = f"{title} {job.page_text or ''}"
    return job.model_copy(
        update={
            "title": title,
            "company": company,
            "work_mode": _norm_work_mode(job.work_mode, text),
            "employment_type": _norm_employment(job.employment_type, text),
            "country": _norm_country(job.country),
        }
    )


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