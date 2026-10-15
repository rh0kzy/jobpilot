"""Turn CV text into a structured Profile via the AI provider."""

import json

from app.core.models import Profile
from app.providers.base import AIProvider

_SYSTEM = (
    "You extract a structured candidate profile from CV text. "
    "Support English, French and Arabic. Return ONLY a JSON object with keys: "
    "name, skills, job_titles, years_experience, seniority, languages, education, location. "
    "Do not invent information; use null or empty lists when unknown."
)


async def extract_profile(text: str, provider: AIProvider) -> Profile:
    raw = await provider.complete(text[:12000], system=_SYSTEM)
    data = _parse_json(raw)
    return Profile(raw_text=text, **{k: v for k, v in data.items() if k in Profile.model_fields})


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
            return json.loads(raw[start : end + 1])
        return {}
