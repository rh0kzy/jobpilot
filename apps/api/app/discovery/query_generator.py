"""Build targeted search queries from a Profile + Preferences."""

import re

_EXCLUDED_ROLE_TERMS = ("founder", "co-founder", "owner", "ownership")
_ATS_DOMAINS = ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com")
_MAX_QUERIES = 15


def _split_terms(value: str) -> list[str]:
    parts = re.split(r"[,/|]| plus | and ", value)
    return [part.strip().lower() for part in parts if part.strip()]


def target_terms(profile) -> list[str]:
    roles = [r.strip() for r in getattr(profile, "job_titles", []) if r and r.strip()]
    roles = [r for r in roles if not any(term in r.lower() for term in _EXCLUDED_ROLE_TERMS)]
    if roles:
        return roles
    skills = [s.strip() for s in getattr(profile, "skills", []) if s and s.strip()]
    return skills[:2]


def _exclude_terms(exclude_terms: list[str]) -> list[str]:
    normalized = []
    for term in exclude_terms or []:
        t = str(term).strip().lower()
        if t:
            normalized.append(t.replace("_", " "))
    return normalized


def _mode_terms(work_modes) -> list[str]:
    modes = getattr(work_modes, "work_modes", work_modes)
    return [m.value if hasattr(m, "value") else str(m) for m in modes] or []


def _type_terms(employment_types) -> list[str]:
    types = getattr(employment_types, "employment_types", employment_types)
    return [t.value if hasattr(t, "value") else str(t) for t in types] or []


def _countries(preferences) -> list[str]:
    countries = getattr(preferences, "countries", []) or []
    return [str(c).upper() for c in countries] or ["WORLDWIDE"]


def _dedupe(queries: list[str]) -> list[str]:
    seen = set()
    unique = []
    for q in queries:
        q = re.sub(r"\s+", " ", q).strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            unique.append(q)
    return unique


def _build_query(role: str, *, seniority: str | None, mode: str | None, type_: str | None, country: str | None, exclude: list[str]) -> str:
    parts = [role, "jobs"]
    if seniority:
        parts.insert(0, seniority)
    if mode:
        parts.append(mode)
    if type_:
        parts.append(type_.replace("_", " "))
    if country:
        parts.append("worldwide" if country == "WORLDWIDE" else country)
    query = " ".join(part for part in parts if part)
    return query


def generate_queries(
    profile,
    preferences,
    *,
    seniority_override: str | None = None,
    exclude_terms: list[str] | None = None,
) -> list[str]:
    """Generate 8-15 de-duplicated search queries."""
    roles = target_terms(profile)
    skills = [s.strip() for s in getattr(profile, "skills", []) if s and s.strip()]
    modes = _mode_terms(preferences)
    types = _type_terms(preferences)
    countries = _countries(preferences)
    exclude = _exclude_terms(exclude_terms)

    seniority = seniority_override or getattr(preferences, "seniority_override", None) or getattr(
        profile, "seniority", None
    )
    mode = modes[0] if modes else None
    type_ = types[0] if types else None

    role_terms = roles[:2] or ["software engineer"]
    # a few target roles built from common backend/frontend stack splits
    lower_skills = {s.lower() for s in skills}
    if "frontend developer" not in [r.lower() for r in role_terms] and (
        "react" in lower_skills or "next.js" in lower_skills or "typescript" in lower_skills
    ):
        role_terms.append("frontend developer")
    if "backend developer" not in [r.lower() for r in role_terms] and (
        "python" in lower_skills or "fastapi" in lower_skills or "node.js" in lower_skills
    ):
        role_terms.append("backend developer")

    queries: list[str] = []
    for role in dict.fromkeys(role_terms):
        queries.append(
            _build_query(role, seniority=None, mode=mode, type_=type_, country=countries[0], exclude=exclude)
        )
        if seniority:
            queries.append(
                _build_query(
                    role,
                    seniority=str(seniority).lower(),
                    mode=mode,
                    type_=type_,
                    country=countries[0],
                    exclude=exclude,
                )
            )

    for domain in _ATS_DOMAINS:
        queries.append(f"site:{domain} '{role_terms[0]}'")

    if len(skills) >= 2:
        queries.append(f"{skills[0]} {skills[1]} jobs {mode or 'remote'}")
    if len(skills) >= 4:
        queries.append(f"{skills[2]} {skills[3]} {role_terms[0]}")
    if len(skills) >= 6:
        queries.append(f"{skills[4]} {skills[5]} jobs")

    for country in dict.fromkeys(countries):
        if country == "WORLDWIDE":
            continue
        queries.append(
            _build_query(
                role_terms[0],
                seniority=None,
                mode=mode,
                type_=type_,
                country=country,
                exclude=exclude,
            )
        )

    queries = _dedupe(queries)
    if exclude:
        suffix = " " + " ".join(f'- "{term}"' for term in exclude)
        queries = [q + suffix for q in queries]
    return queries[:_MAX_QUERIES]