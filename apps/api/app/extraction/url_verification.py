"""Final URL verification for extracted/connector jobs."""

import random
import re
from urllib.parse import urlparse

from app.core.models import Job
from app.discovery.fetcher import fetch_detailed
from app.extraction.classification import _single_posting_signals, _url_is_single_job, classify_page
from app.filters.liveness import is_live

_NOT_FOUND_PHRASES = (
    "not found",
    "page not found",
    "job not found",
    "no longer available",
    "position has been filled",
    "this job is closed",
    "requisition not found",
)
_ERROR_PAGE_PHRASES = (
    "something went wrong",
    "we could not find",
    "unable to load",
    "access denied",
    "page cannot be found",
    "error 404",
    "404 not found",
)
_ERROR_QUERY_KEYS = {"error", "err", "not_found", "status", "code"}


def _normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip(" ,;:.-")


def _title_matches(title: str, text: str) -> bool:
    title_tokens = [
        token for token in re.findall(r"[a-z0-9]+", str(title or "").lower()) if len(token) > 2
    ]
    if not title_tokens:
        return False
    page_tokens = set(re.findall(r"[a-z0-9]+", str(text or "").lower()))
    if all(token in page_tokens for token in title_tokens):
        return True
    normalized_title = " ".join(title_tokens)
    return normalized_title in _normalize_text(text)


def _company_matches(job: Job, text: str, final_url: str) -> bool:
    company_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", str(job.company or "").lower())
        if len(token) > 2
    ]
    if not company_tokens:
        # Fall back to board token embedded in the candidate/canonical URL.
        company_tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", urlparse(job.url).path.lower())
            if len(token) > 2
        ]
    haystack = f"{text} {final_url}".lower()
    return any(token in haystack for token in company_tokens)


def _has_error_query(url: str) -> bool:
    parsed = urlparse(url)
    for key in (parsed.query or "").split("&"):
        if "=" in key:
            name = key.split("=", 1)[0].strip().lower()
            if name in _ERROR_QUERY_KEYS:
                return True
    return False


async def _verify_candidate(
    job: Job, url: str, *, cache_dir: str, timeout: int
) -> tuple[str, str | None]:
    result = await fetch_detailed(url, timeout=timeout, cache_dir=cache_dir)
    if result.status != "ok" or result.html is None:
        return f"fetch_failed_{result.status}", None

    final_url = result.final_url or url
    text = result.html
    lower_text = text.lower()

    if _has_error_query(final_url):
        return "error_query_parameter", None
    if not is_live(text):
        return "closed_or_expired", None
    if any(phrase in lower_text for phrase in _NOT_FOUND_PHRASES):
        return "not_found", None
    if any(phrase in lower_text for phrase in _ERROR_PAGE_PHRASES):
        return "http_200_error_page", None

    page_type = await classify_page(text, final_url)
    if not _url_is_single_job(final_url) and page_type != "single_job":
        redirected = final_url.rstrip("/") != url.rstrip("/")
        if redirected and ("search" in final_url.lower() or "q=" in final_url.lower()):
            return "redirected_to_search_page", None
        if redirected and not _url_is_single_job(final_url):
            return "redirected_to_board_root", None
        return "redirected_to_not_specific_page", None
    if page_type != "single_job":
        return "redirected_to_not_specific_page", None

    if not _title_matches(job.title, text) or not _company_matches(job, text, final_url):
        return "content_mismatch", None

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
                job, candidate, cache_dir=cache_dir, timeout=timeout
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
        statuses[job.url_verification_status] = statuses.get(job.url_verification_status, 0) + 1
        verified_jobs.append(job)
    return verified_jobs, statuses


async def audit_verification(
    jobs: list[Job],
    *,
    sample_size: int = 10,
    cache_dir: str = "./.cache",
    timeout: int = 30,
) -> dict[str, int]:
    if not jobs:
        return {"sampled": 0, "passed": 0}
    sample = random.sample(jobs, min(sample_size, len(jobs)))
    passed = 0
    for job in sample:
        temp_job = job.model_copy()
        from app.discovery.fetcher import fetch_detailed as _fetch

        result = await _fetch(temp_job.url, timeout=timeout, cache_dir=cache_dir)
        single_signal, signal_confidence = _single_posting_signals(result.html or "", temp_job.url) if result.html else (False, 0.0)
        company_ok = _company_matches(temp_job, result.html or "", result.final_url or temp_job.url)
        title_ok = _title_matches(temp_job.title, result.html or "") if result.html else False
        live = bool(result.html and is_live(result.html))
        if result.status == "ok" and result.html is not None and live and title_ok and company_ok and single_signal:
            passed += 1
        temp_job.page_type = "single_job" if single_signal else temp_job.page_type
        temp_job.confidence = max(temp_job.confidence or 0.0, signal_confidence)
    return {"sampled": len(sample), "passed": passed}
