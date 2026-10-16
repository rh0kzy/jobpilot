"""Deterministic classification and one-level listing expansion."""

import re
from urllib.parse import urldefrag, urljoin, urlparse

from app.extraction.extractor import _from_jsonld, _regex_jsonld

_LISTING_URL_RE = re.compile(
    r"/(?:careers?|search)(?:/|$|#|\?)"
    r"|/(?:jobs?|remote-jobs|openings?)(?:/|$|#|\?)"
    r"|/(?:jobs?|remote-jobs|openings?)/(?:[^/]+/)?[^/]+/?$"
    r"|/categories/[^/]+/?$"
    r"|[?#](?:q|query|page|search|category|location|sort)=",
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



_NON_SINGLE_URL_PATTERNS = re.compile(
    r"/(?:job-tag|job-tags|category|categories|tag|tags|search|filter|hire|tags?)(?:/|$)"
    r"|/(?:remote-jobs|jobs?)/?$"
    r"|[?#](?:q|query|page|search|category|location|sort|tag)=",
    re.IGNORECASE,
)


def _extract_jsonld_urls(html: str, base_url: str) -> list[str]:
    urls: list[str] = []
    try:

        for entry in _regex_jsonld(html):
            entries = entry if isinstance(entry, list) else [entry]
            for item in entries:
                if not isinstance(item, dict):
                    continue
                if "url" in item and isinstance(item["url"], str) and urlparse(item["url"]).netloc and item["url"] not in urls:
                    urls.append(item["url"])
                for value in item.values():
                    if isinstance(value, list):
                        for nested in value:
                            if isinstance(nested, dict) and isinstance(nested.get("url"), str) and nested["url"] not in urls:
                                urls.append(nested["url"])
                    if isinstance(value, dict) and isinstance(value.get("url"), str) and value["url"] not in urls:
                        urls.append(value["url"])
    except Exception:  # noqa: BLE001, S110
        pass
    return urls


def _looks_like_posting_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path or ""
    if _NON_SINGLE_URL_PATTERNS.search(url):
        return False
    if _EXCLUDE_URL_RE.search(url):
        return False
    parts = [p for p in path.split("/") if p]
    if len(parts) < 1:
        return False
    last = parts[-1]
    if len(last) < 5:
        return False
    # Known single-posting-ish paths: a slug under a collection.
    if len(parts) >= 2 and any(tok in path.lower() for tok in ("job", "opening", "position", "posting")) and last not in {"jobs", "job", "openings", "positions"}:
        return True
    # Hyphenated slugs often identify postings.
    if "-" in last and len(last) >= 12 and not any(tok in last.lower() for tok in ("category", "tag", "page")):
        return True
    # Digits make it look like a posting id.
    return bool(any(ch.isdigit() for ch in last) and len(last) >= 8)


def extract_job_links_detailed(html: str, base_url: str, limit: int = 20) -> tuple[list[str], str]:
    base_host = _domain(base_url)
    anchors = _anchors(html, base_url)
    if not anchors:
        return [], "no_anchors"

    # First try explicit posting-like URLs.
    links: list[str] = []
    same_domain_found = False
    for href, text in anchors:
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        url = urldefrag(urljoin(base_url, href))[0]
        if not url.startswith("http"):
            continue
        if _domain(url) != base_host:
            continue
        same_domain_found = True
        if _EXCLUDE_URL_RE.search(url) or _NON_SINGLE_URL_PATTERNS.search(url):
            continue
        if not _looks_like_posting_url(url):
            continue
        if url not in links:
            links.append(url)
        if len(links) >= limit:
            break

    # JSON-LD ItemList fallback.
    if not links:
        for url in _extract_jsonld_urls(html, base_url):
            if _domain(url) != base_host:
                continue
            if _EXCLUDE_URL_RE.search(url) or _NON_SINGLE_URL_PATTERNS.search(url):
                continue
            if url not in links:
                links.append(url)
            if len(links) >= limit:
                break

    # Generic heuristic: job-card containers containing anchors.
    if not links:
        for href, text in anchors:
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            url = urldefrag(urljoin(base_url, href))[0]
            if not url.startswith("http") or _domain(url) != base_host:
                continue
            if _EXCLUDE_URL_RE.search(url) or _NON_SINGLE_URL_PATTERNS.search(url):
                continue
            # Accept anchors whose surrounding HTML looks like a job card.
            idx = html.find(href)
            context = html[max(0, idx - 500): idx + len(href)]
            if re.search(r'class="[^"]*(?:job|card|listing|posting|opening|vacancy)', context, re.IGNORECASE):
                if url not in links:
                    links.append(url)
                if len(links) >= limit:
                    break

    if not same_domain_found:
        return [], "no_same_domain_links"
    if links:
        return links, "ok"
    if re.search(r"<script", html, re.IGNORECASE) and len(anchors) < 5:
        return [], "javascript_rendered"
    return [], "no_posting_links"

def extract_job_links(html: str, base_url: str, limit: int = 20) -> list[str]:
    links, _ = extract_job_links_detailed(html, base_url, limit)
    return links


def _looks_single_from_page_structure(html: str) -> bool:
    # A single job page usually has an Apply affordance.
    return bool(re.search(r"\b(apply\b|apply now|postuler|apply for this job\b)", html or "", re.IGNORECASE))


def _page_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.IGNORECASE | re.DOTALL)
    return re.sub(r"<[^>]+>", " ", match.group(1)) if match else ""


def _single_posting_signals(html: str, url: str) -> tuple[bool, float]:
    embedded = bool(_from_jsonld(html, url))
    single_url = _url_is_single_job(url)
    non_single = bool(_NON_SINGLE_URL_PATTERNS.search(url))
    links, _ = extract_job_links_detailed(html, url)
    has_jobposting_jsonld = "jobposting" in (html or "").lower()
    has_apply = bool(re.search(r"\bapply(?:\s+now|\s+for\s+this\s+job)?\b", html or "", re.IGNORECASE))
    dominant_heading = bool(re.search(r"<h1[^>]*>.{5,120}</h1>", html or "", re.IGNORECASE | re.DOTALL))
    signals = 0
    if embedded or has_jobposting_jsonld:
        signals += 3
    if single_url:
        signals += 2
    if dominant_heading and has_apply:
        signals += 2
    if len(links) == 0:
        # Single pages often have no outgoing posting links.
        signals += 1
    if non_single:
        signals -= 4
    confidence = min(1.0, max(0.0, 0.2 + signals * 0.18))
    return signals >= 3 and not non_single, confidence


def _repeated_job_cards(html: str) -> int:
    return len(re.findall(r"class=\"[^\"]*(?:job|card|listing|posting|opening|vacancy)[^\"]*\"", html or "", re.IGNORECASE))


async def classify_page(html: str, url: str, provider=None, confidence_out: dict | None = None) -> str:
    """Return "single_job", "listing" or "other"."""
    if not html:
        if confidence_out is not None:
            confidence_out["confidence"] = 0.0
        return "other"

    embedded = bool(_from_jsonld(html, url))
    links, link_reason = extract_job_links_detailed(html, url)
    single_url = _url_is_single_job(url)
    listing_url = _url_is_listing(url)
    non_single_url = bool(_NON_SINGLE_URL_PATTERNS.search(url))
    title = _page_title(html)
    repeated_cards = _repeated_job_cards(html)
    has_many_links = len(links) >= 5
    jobs_in_title = bool(re.search(r"\b\d{1,5}\s+(?:remote\s+)?jobs\b", title, re.IGNORECASE))

    single_signals, single_confidence = _single_posting_signals(html, url)

    is_listing = False
    if non_single_url:
        is_listing = True
    if listing_url:
        is_listing = True
    if repeated_cards >= 6 or has_many_links or jobs_in_title:
        is_listing = True
    if link_reason in {"no_posting_links", "javascript_rendered"} and repeated_cards >= 3:
        is_listing = True

    if embedded or (single_url and single_signals):
        result = "single_job"
        confidence = max(single_confidence, 0.75 if single_url else 0.6)
    elif is_listing:
        result = "listing"
        confidence = 0.8
    elif single_signals:
        result = "single_job"
        confidence = single_confidence
    elif _looks_single_from_page_structure(html):
        result = "single_job"
        confidence = 0.55
    else:
        result = "other"
        confidence = 0.3
        if provider is not None:
            prompt = (
                "Classify this web page. Return ONLY one word: single_job, listing or other. "
                "single_job means one specific job posting; listing means search/category/careers page.\n"
                f"URL: {url}\n"
            )
            try:
                raw = (await provider.complete(prompt, system="You are a strict URL/page classifier.")).strip().lower()
                if raw.startswith("single_job"):
                    result = "single_job"
                    confidence = 0.55
                elif raw.startswith("listing"):
                    result = "listing"
                    confidence = 0.7
            except Exception:  # noqa: BLE001, S110
                pass

    if confidence_out is not None:
        confidence_out["confidence"] = confidence
        confidence_out["page_type"] = result
    return result
