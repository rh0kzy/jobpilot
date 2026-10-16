"""Final URL verification for extracted/connector jobs."""

from app.core.models import Job
from app.discovery.fetcher import fetch_detailed
from app.extraction.classification import classify_page
from app.filters.liveness import is_live


async def _verify_candidate(url: str, *, cache_dir: str, timeout: int) -> tuple[str, str | None]:
    result = await fetch_detailed(url, timeout=timeout, cache_dir=cache_dir)
    if result.status != "ok" or result.html is None:
        return f"fetch_failed_{result.status}", None
    final_url = result.final_url or url
    if not is_live(result.html):
        return "closed_or_expired", None
    page_type = await classify_page(result.html, final_url)
    if page_type != "single_job":
        return "redirected_to_not_specific_page", None
    return "verified", final_url


async def verify_jobs(
    jobs: list[Job],
    *,
    cache_dir: str = "./.cache",
    timeout: int = 30,
) -> tuple[list[Job], dict[str, int]]:
    """Verify URLs and drop jobs whose final URL is not a specific live job."""
    verified_jobs: list[Job] = []
    statuses: dict[str, int] = {}
    for job in jobs:
        if job.url_verified:
            verified_jobs.append(job)
            statuses[job.url_verification_status or "verified"] = (
                statuses.get(job.url_verification_status or "verified", 0) + 1
            )
            continue

        candidates: list[tuple[str, str]] = []
        if job.original_url and job.original_url != job.url:
            candidates.append(("original", job.original_url))
            candidates.append(("fallback", job.url))
        else:
            candidates.append(("main", job.url))

        attempts: list[str] = []
        verified_final: str | None = None
        for kind, candidate in candidates:
            status, final_url = await _verify_candidate(
                candidate, cache_dir=cache_dir, timeout=timeout
            )
            if status == "verified" and final_url:
                verified_final = final_url
                if kind == "original":
                    attempts.append("verified_company_domain")
                else:
                    attempts.append("verified_canonical_or_main_url")
                break
            attempts.append(f"{status}_{kind}" if kind in {"original", "fallback"} else status)

        if verified_final is None:
            attempts.append("dropped_unverified_url")
            status = ";".join(attempts)
            statuses[status] = statuses.get(status, 0) + 1
            job.url_verified = False
            job.url_verification_status = status
            continue

        job.url = verified_final
        job.url_verified = True
        job.url_verification_status = ";".join(attempts)
        statuses[job.url_verification_status] = (
            statuses.get(job.url_verification_status, 0) + 1
        )
        verified_jobs.append(job)
    return verified_jobs, statuses
