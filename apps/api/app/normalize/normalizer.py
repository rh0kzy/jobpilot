"""Job normalization and deduplication."""

from app.core.models import Job


def normalize_job(job: Job) -> Job:
    return job.model_copy(
        update={
            "work_mode": _norm_work_mode(job.work_mode, job.page_text),
            "employment_type": _norm_employment(job.employment_type),
            "country": (job.country or "").upper() or None,
        }
    )


def _norm_work_mode(value, text) -> str | None:
    v = (value or "").lower()
    text_l = (text or "").lower()
    if v in {"remote", "hybrid", "onsite", "on-site", "on site"}:
        return v.replace(" ", "_").replace("-", "_").replace("on_site", "onsite")
    if "remote" in text_l:
        return "remote"
    if "hybrid" in text_l:
        return "hybrid"
    if "on-site" in text_l or "onsite" in text_l:
        return "onsite"
    return value


def _norm_employment(value) -> str | None:
    if not value:
        return None
    v = str(value).lower().replace(" ", "_").replace("-", "_")
    if "full" in v:
        return "full_time"
    if "part" in v:
        return "part_time"
    if "contract" in v:
        return "contract"
    if "intern" in v:
        return "internship"
    return v


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
