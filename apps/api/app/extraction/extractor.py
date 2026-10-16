"""Extract job records from fetched HTML."""

import json
import re
from datetime import date
from urllib.parse import urlparse

from app.core.models import Job
from app.extraction.page_text import has_meaningful_job_text, html_to_text

_REMOTE_ELIGIBLE_TERMS = (
    "US",
    "U.S.",
    "USA",
    "EMEA",
    "EU",
    "APAC",
    "LATAM",
    "North America",
    "South America",
    "Canada",
    "Worldwide",
    "Global",
)
_SENIORITY_TERMS = (
    "principal",
    "distinguished",
    "staff",
    "lead",
    "senior",
    "sr.",
    "mid-level",
    "middle",
    "junior",
    "jr.",
    "entry-level",
    "graduate",
)


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _norm_work_mode(value) -> str | None:
    if not value:
        return None
    v = str(value).strip().lower()
    if v in {"remote", "telecommute", "télétravail"}:
        return "remote"
    if v in {"hybrid"}:
        return "hybrid"
    if v in {"onsite", "on-site", "sur site"}:
        return "onsite"
    return None


def _norm_employment(value) -> str | None:
    if not value:
        return None
    v = str(value).strip().lower()
    if "full" in v:
        return "full_time"
    if "part" in v:
        return "part_time"
    if "contract" in v or "freelance" in v:
        return "contract"
    if "intern" in v or "stage" in v:
        return "internship"
    return v


def _clean(value) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip(" •,;|")
    return text or None


def _extract_country(value) -> str | None:
    country = _clean(value)
    return country.upper() if country else None


def _extract_work_mode(item: dict) -> str | None:
    mode = _norm_work_mode(item.get("jobLocationType"))
    if mode:
        return mode
    text = " ".join(str(item.get("description", "")).split()).lower()
    if re.search(r"\b(remote|telecommute|à distance|a distance)\b", text):
        return "remote"
    if re.search(r"\bhybrid\b", text):
        return "hybrid"
    if re.search(r"\b(on-site|onsite)\b", text):
        return "onsite"
    return None


def _extract_employment(item: dict) -> str | None:
    return _norm_employment(item.get("employmentType"))


def _extract_location(item: dict) -> str | None:
    raw = item.get("jobLocation")
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    parts: list[str] = []
    if isinstance(raw, dict):
        address = raw.get("address") if isinstance(raw.get("address"), dict) else raw
        for key in ("addressLocality", "addressRegion", "postalCode", "addressCountry"):
            value = _clean(address.get(key))
            if value and value not in parts:
                parts.append(value)
        name = _clean(raw.get("name"))
        if name and not parts:
            parts.append(name)
    elif isinstance(raw, str):
        value = _clean(raw)
        if value:
            parts.append(value)
    return ", ".join(parts) if parts else None


def _extract_country_from_item(item: dict) -> str | None:
    raw = item.get("jobLocation")
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if isinstance(raw, dict):
        address = raw.get("address") if isinstance(raw.get("address"), dict) else raw
        return _extract_country(address.get("addressCountry"))
    return None


def _extract_remote_eligibility(item: dict) -> str | None:
    raw = item.get("applicantLocationRequirements")
    values: list[str] = []
    if isinstance(raw, dict):
        address = raw.get("address", {}) if isinstance(raw.get("address"), dict) else {}
        for value in [address.get("addressCountry"), address.get("addressLocality"), raw.get("name")]:
            cleaned = _clean(value)
            if cleaned and cleaned not in values:
                values.append(cleaned)
    elif isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict):
                address = entry.get("address", {}) if isinstance(entry.get("address"), dict) else {}
                cleaned = _clean(address.get("addressCountry") or address.get("addressLocality") or entry.get("name"))
                if cleaned and cleaned not in values:
                    values.append(cleaned)
    if values:
        return " / ".join(values)

    text = f"{item.get('title', '')} {item.get('description', '')}"
    for term in _REMOTE_ELIGIBLE_TERMS:
        pattern = rf"\b{re.escape(term)}\b[^\n.]{{0,30}}\b(only|based|remote|residents?)\b"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return term
    return None


def _extract_seniority(*texts: str | None) -> str | None:
    text = " ".join(str(t) for t in texts if t)
    for term in _SENIORITY_TERMS:
        match = re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def _from_jsonld(html: str, url: str) -> list[Job]:
    try:
        import extruct

        data = extruct.extract(html, syntaxes=["json-ld"])
        items = data.get("json-ld", [])
    except Exception:  # noqa: BLE001
        items = _regex_jsonld(html)

    jobs = []
    for entry in items:
        entries = entry if isinstance(entry, list) else [entry]
        for item in entries:
            if not isinstance(item, dict):
                continue
            types = item.get("@type")
            is_job = "JobPosting" in types if isinstance(types, list) else types == "JobPosting"
            if not is_job:
                continue
            org = item.get("hiringOrganization") or {}
            company = org.get("name") if isinstance(org, dict) else None
            title = item.get("title")
            if not title or not url:
                continue
            description = item.get("description", "") or ""
            jobs.append(
                Job(
                    title=title,
                    company=_clean(company) or "",
                    url=url,
                    original_url=url,
                    source=_domain(url),
                    posted_date=_parse_date(item.get("datePosted")),
                    work_mode=_extract_work_mode(item),
                    employment_type=_extract_employment(item),
                    location=_extract_location(item),
                    country=_extract_country_from_item(item),
                    remote_eligibility=_extract_remote_eligibility(item),
                    seniority=_extract_seniority(title),
                    page_text=description,
                )
            )
    return jobs


def _regex_jsonld(html: str) -> list[dict]:
    results = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            results.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return results


async def extract_jobs(html: str, url: str, provider=None, max_chars: int = 8000) -> list[Job]:
    jobs = _from_jsonld(html, url)
    if jobs:
        return jobs

    text = html_to_text(html)
    if provider is None or not has_meaningful_job_text(html, text):
        return []

    prompt = (
        "Extract at most one job posting from the following visible page text. "
        "If this page is not one specific job posting, return {\"jobs\":[]}. "
        "Copy fields only; do not invent values. Use the given URL exactly. "
        "Return ONLY JSON with: jobs[{title, company, url, posted_date, work_mode, employment_type, "
        "location, country, remote_eligibility, seniority, description}].\n\n"
        f"URL: {url}\n\nTEXT:\n{text[:max_chars]}"
    )
    try:
        raw = await provider.complete(prompt)
        data = _parse_json(raw)
        items = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            if not title:
                continue
            jobs.append(
                Job(
                    title=_clean(title) or "",
                    company=_clean(item.get("company")) or "",
                    url=url,
                    original_url=url,
                    source=_domain(url),
                    posted_date=_parse_date(item.get("posted_date")),
                    work_mode=_norm_work_mode(item.get("work_mode")),
                    employment_type=_norm_employment(item.get("employment_type")),
                    location=_clean(item.get("location")),
                    country=_extract_country(item.get("country")),
                    remote_eligibility=_clean(item.get("remote_eligibility")),
                    seniority=_extract_seniority(title),
                    page_text=item.get("description", "") or "",
                )
            )
    except Exception:  # noqa: BLE001, S110
        pass
    return jobs


def _parse_json(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if "\n" in raw:
            raw = raw.split("\n", 1)[1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return []
        return []
