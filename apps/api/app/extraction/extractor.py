"""Extract job records from fetched HTML."""

import json
import re
from datetime import date
from urllib.parse import urlparse

from app.core.models import Job


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
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
        if isinstance(entry, list):
            entries = entry
        else:
            entries = [entry]
        for item in entries:
            if not isinstance(item, dict):
                continue
            types = item.get("@type")
            if isinstance(types, list):
                is_job = "JobPosting" in types
            else:
                is_job = types == "JobPosting"
            if not is_job:
                continue
            org = item.get("hiringOrganization") or {}
            company = org.get("name") if isinstance(org, dict) else None
            loc = item.get("jobLocation") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            address = loc.get("address", {}) if isinstance(loc, dict) else {}
            country = address.get("addressCountry") if isinstance(address, dict) else None
            title = item.get("title")
            if not title or not url:
                continue
            jobs.append(
                Job(
                    title=title,
                    company=company or "",
                    url=url,
                    source=_domain(url),
                    posted_date=_parse_date(item.get("datePosted")),
                    work_mode=_normalize_work_mode(item, str(item.get("description", ""))),
                    employment_type=_normalize_employment(item.get("employmentType")),
                    country=country,
                    page_text=item.get("description", "") or "",
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


def _normalize_work_mode(item: dict, text: str) -> str | None:
    text_l = (text or "").lower()
    if "remote" in text_l:
        return "remote"
    if "hybrid" in text_l:
        return "hybrid"
    if "on-site" in text_l or "onsite" in text_l:
        return "onsite"
    return None


def _normalize_employment(value) -> str | None:
    if not value:
        return None
    v = str(value).lower()
    if "full" in v:
        return "full_time"
    if "part" in v:
        return "part_time"
    if "contract" in v:
        return "contract"
    if "intern" in v:
        return "internship"
    return v


async def extract_jobs(html: str, url: str, provider=None) -> list[Job]:
    jobs = _from_jsonld(html, url)
    if jobs:
        return jobs
    # LLM fallback
    if provider is not None:
        prompt = (
            "Extract job postings from the following page text. "
            "Return ONLY a JSON array of objects with keys: title, company, url, posted_date (YYYY-MM-DD or null), "
            "work_mode, employment_type, country, description. "
            "Copy fields only; do not invent. Use the given URL for url.\n\n"
            f"URL: {url}\n\nTEXT:\n{html[:6000]}"
        )
        try:
            raw = await provider.complete(prompt)
            data = _parse_json(raw)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    title = item.get("title")
                    if not title:
                        continue
                    jobs.append(
                        Job(
                            title=title,
                            company=item.get("company") or "",
                            url=url,
                            source=_domain(url),
                            posted_date=_parse_date(item.get("posted_date")),
                            work_mode=item.get("work_mode"),
                            employment_type=item.get("employment_type"),
                            country=item.get("country"),
                            page_text=item.get("description", "") or "",
                        )
                    )
                if jobs:
                    return jobs
        except Exception:  # noqa: BLE001, S110
            pass
    # HTML heuristic: minimal title from <title>
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = m.group(1).strip() if m else None
    if title and len(title) < 120:
        jobs.append(Job(title=title, company="", url=url, source=_domain(url), page_text=html[:2000]))
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
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        return []
