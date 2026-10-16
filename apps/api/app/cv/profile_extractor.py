"""Turn CV text into a structured Profile via the AI provider."""

import json
import re

from app.core.models import Education, Profile
from app.providers.base import AIProvider

_SYSTEM = (
    "You extract a structured candidate profile from CV text. "
    "Support English, French and Arabic. Return ONLY a JSON object with keys: "
    "name, skills, job_titles, years_experience, seniority, languages, education, location. "
    "education must be a list of objects with degree, field, institution, start_year, end_year. "
    "Do not invent information; use null or empty lists when unknown."
)


def _as_int(value) -> int | None:
    if value is None or value is True or value is False:
        return None
    if isinstance(value, int):
        return value
    text = str(value)
    match = re.search(r"\d{4}", text)
    if match:
        return int(match.group(0))
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _normalize_education(value) -> list[Education]:
    if value is None:
        return []
    if isinstance(value, str):
        return [Education(degree=value.strip())] if value.strip() else []
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            if isinstance(item, (list, tuple)):
                items.extend(_normalize_education(item))
            else:
                items.append(_normalize_education_item(item))
        return items
    return []


def _normalize_education_item(item) -> Education:
    if isinstance(item, str):
        return Education(degree=item.strip())
    if not isinstance(item, dict):
        return Education(degree=str(item).strip())
    degree = item.get("degree") or item.get("title") or item.get("diploma") or item.get("qualification")
    field = item.get("field") or item.get("major") or item.get("specialization") or item.get("domain")
    institution = (
        item.get("institution")
        or item.get("school")
        or item.get("university")
        or item.get("establishment")
    )
    start_year = _as_int(item.get("start_year") or item.get("start") or item.get("from") or item.get("from_year"))
    end_year = _as_int(item.get("end_year") or item.get("end") or item.get("to") or item.get("to_year"))
    years = item.get("years")
    if years and start_year is None and end_year is None:
        nums = re.findall(r"\d{4}", str(years))
        if len(nums) >= 2:
            start_year = int(nums[0])
            end_year = int(nums[1])
        elif len(nums) == 1:
            end_year = int(nums[0])
    return Education(
        degree=_clean(degree),
        field=_clean(field),
        institution=_clean(institution),
        start_year=start_year,
        end_year=end_year,
    )


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            if isinstance(item, dict):
                result.append(", ".join(f"{k}: {v}" for k, v in item.items() if v is not None))
            else:
                result.append(str(item).strip())
        return [x for x in result if x]
    return [str(value).strip()]


async def extract_profile(text: str, provider: AIProvider) -> Profile:
    raw = await provider.complete(text[:12000], system=_SYSTEM)
    data = _parse_json(raw)
    kwargs = {}
    for key, value in data.items():
        if key not in Profile.model_fields or key == "raw_text":
            continue
        if key == "education":
            if isinstance(value, dict):
                value = [value]
            if isinstance(value, (list, tuple)):
                value = [_normalize_education_item(v) for v in value]
            else:
                value = _normalize_education(value)
        elif key in {"skills", "job_titles", "languages"}:
            value = _normalize_list(value)
        elif key in {"years_experience"}:
            try:
                value = float(value) if value is not None else None
            except (TypeError, ValueError):
                value = None
        kwargs[key] = value
    kwargs["raw_text"] = text
    return Profile(**kwargs)


def _parse_json(raw: str) -> dict:
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
                return {}
        return {}