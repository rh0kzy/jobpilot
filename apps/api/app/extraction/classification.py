"""Deterministic classification and one-level listing expansion."""

import re
from urllib.parse import urldefrag, urljoin, urlparse

from app.extraction.extractor import _from_jsonld

_LISTING_URL_RE = re.compile(
    r"/(?:jobs?|careers?|search|remote-jobs|openings?|categories|role|locations?)(?:/|$|#|\?)",
    re.IGNORECASE,
)
_SINGLE_URL_RE = re.compile(
    r"/(?:remote-jobs|jobs?|job-details?|openings?)/[^/]+/\d{3,}(?:/|$|#|\?)"
    r"|/(?:jobs?|openings?)/\d{3,}(?:/|$|#|\?)"
    r"|/[a-z0-9-]*job[a-z0-9-]*-\d{6,}(?:/|$|#|\?)"
    r"|/(?:remote-jobs|jobs?|job-details?|openings?)/[^/]+-\d{4,}(?:/|$|#|\?)"
    r"|/companies/[^/]+/jobs/[^/]+(?:/|$|#|\?)",
    re.IGNORECASE,
)
_EXCLUDE_URL_RE = re.compile(
    r"/(?:category|categories|search|filter|login|signup|register|about|blog)/|"
    r"[?#](?:q|query|page|search|category|location|sort)=",
    re.IGNORECASE,
)


def _anchors(html: str, base_url: str) -> list[tuple[str, str]]:
    anchors: list[tuple[str, str]] = []
    for match in re.finditer(
        r"<a\b[^>]*href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        href = match.group(1).strip()
        text = re.sub(r"<[^>]+>", " ", match.group(2))
        anchors.append((href, text.strip()))
    return anchors


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def _url_is_single_job(url: str) -> bool:
    return bool(_SINGLE_URL_RE.search(url))


def _url_is_listing(url: str) -> bool:
    return bool(_LISTING_URL_RE.search(url))


def extract_job_links(html: str, base_url: str, limit: int = 20) -> list[str]:
    base_host = _domain(base_url)
    links: list[str] = []
    for href, text in _anchors(html, base_url):
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urldefrag(urljoin(base_url, href))[0]
        if not url.startswith("http"):
            continue
        if _domain(url) != base_host:
            continue
        if _EXCLUDE_URL_RE.search(url):
            continue
        if not _url_is_single_job(url):
            continue
        if url not in links:
            links.append(url)
        if len(links) >= limit:
            break
    return links


def _looks_single_from_page_structure(html: str) -> bool:
    # A single job page usually has an Apply affordance.
    return bool(re.search(r"\b(apply\b|apply now|postuler|apply for this job\b)", html or "", re.IGNORECASE))


async def classify_page(html: str, url: str, provider=None) -> str:
    """Return "single_job", "listing" or "other"."""
    if not html:
        return "other"

    embedded = bool(_from_jsonld(html, url))
    links = extract_job_links(html, url)
    single_url = _url_is_single_job(url)
    listing_url = _url_is_listing(url)

    if (embedded or single_url or _looks_single_from_page_structure(html)) and len(links) < 5:
        return "single_job"
    if listing_url or len(links) >= 5:
        return "listing"

    if provider is not None:
        prompt = (
            "Classify this web page. Return ONLY one word: single_job, listing or other. "
            "single_job means one specific job posting; listing means search/category/careers page.\n"
            f"URL: {url}\n"
        )
        try:
            raw = (await provider.complete(prompt, system="You are a strict URL/page classifier.")).strip().lower()
            if raw.startswith("single_job"):
                return "single_job"
            if raw.startswith("listing"):
                return "listing"
        except Exception:  # noqa: BLE001, S110
            pass
    return "other"
