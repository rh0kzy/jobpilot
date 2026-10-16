"""Build targeted search queries from a Profile + Preferences."""

import re
import unicodedata
from dataclasses import dataclass

_EXCLUDED_ROLE_TERMS = ("founder", "co-founder", "owner", "ownership")
_ATS_DOMAINS = ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com")
_MAX_QUERIES = 15
_AI_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "deep learning",
    "rag",
    "llm",
    "computer vision",
    "data science",
)


@dataclass(frozen=True)
class SearchQuery:
    text: str
    kind: str



_ROLE_RULES = (
    ("full stack", "Full-Stack Developer"),
    ("fullstack", "Full-Stack Developer"),
    ("full-stack", "Full-Stack Developer"),
    ("back end", "Backend Developer"),
    ("backend", "Backend Developer"),
    ("back-end", "Backend Developer"),
    ("front end", "Frontend Developer"),
    ("frontend", "Frontend Developer"),
    ("front-end", "Frontend Developer"),
    ("machine learning", "Machine Learning Engineer"),
    ("ml engineer", "Machine Learning Engineer"),
    ("artificial intelligence", "AI Engineer"),
    ("ai engineer", "AI Engineer"),
    ("software engineer", "Software Engineer"),
    ("software developer", "Software Engineer"),
    ("developer", "Software Engineer"),
    ("engineer", "Software Engineer"),
    ("intern", None),
    ("stage", None),
    ("stagiaire", None),
)


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii").lower()


def canonical_role(value: str) -> str | None:
    folded = _fold(value)
    for needle, canonical in _ROLE_RULES:
        if needle in folded:
            return canonical
    return None


def _listify(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def target_terms(profile, preferences=None) -> list[str]:
    raw_roles = getattr(profile, "job_titles", [])
    if isinstance(raw_roles, str):
        raw_roles = raw_roles.split(",")
    canonical: list[str] = []
    for role in raw_roles or []:
        role = str(role).strip()
        if not role:
            continue
        if any(term in _fold(role) for term in _EXCLUDED_ROLE_TERMS):
            continue
        mapped = canonical_role(role)
        if mapped is None:
            continue
        # Drop internship roles unless the user explicitly asked for internships.
        internship_requested = False
        if preferences is not None:
            employment_types = getattr(preferences, "employment_types", None) or []
            values = [str(v.value if hasattr(v, "value") else v).lower() for v in employment_types]
            internship_requested = "internship" in values
        if mapped and any(term in _fold(role) for term in ("intern", "stage", "stagiaire")) and not internship_requested:
            continue
        if mapped and mapped not in canonical:
            canonical.append(mapped)
    roles = canonical[:3] if canonical else []
    if not roles:
        skills = _listify(getattr(profile, "skills", []))
        roles = skills[:2]
    return roles


def target_prefilter_terms(profile, preferences=None) -> list[str]:
    roles = target_terms(profile, preferences=preferences)
    # Include adjacent engineering roles so recall covers backend/frontend/mobile/AI.
    for role in _adjacent_roles(profile, roles):
        if role not in roles:
            roles.append(role)
    skills = _listify(getattr(profile, "skills", []))
    for skill in skills[:6]:
        if skill not in roles:
            roles.append(skill)
    return roles[:16]


def _exclude_terms(exclude_terms: list[str] | None) -> list[str]:
    return [str(term).strip().lower().replace("_", " ") for term in exclude_terms or [] if str(term).strip()]


def _modes(preferences) -> list[str]:
    modes = getattr(preferences, "work_modes", preferences)
    return [m.value if hasattr(m, "value") else str(m) for m in modes] or []


def _employment_types(preferences) -> list[str]:
    types = getattr(preferences, "employment_types", preferences)
    return [t.value if hasattr(t, "value") else str(t) for t in types] or []


def _countries(preferences) -> list[str]:
    countries = [str(c).upper() for c in _listify(getattr(preferences, "countries", []))]
    return countries or ["WORLDWIDE"]


def _dedupe(queries: list[SearchQuery]) -> list[SearchQuery]:
    seen: set[str] = set()
    unique: list[SearchQuery] = []
    for query in queries:
        text = re.sub(r"\s+", " ", query.text).strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        unique.append(SearchQuery(text=text, kind=query.kind))
    return unique


def _role_text(role: str, *, mode: str | None, type_: str | None, country: str | None, seniority: str | None = None) -> str:
    parts = []
    if seniority:
        parts.append(str(seniority).lower())
    parts.append(role)
    parts.append("jobs")
    if mode:
        parts.append(mode)
    if type_:
        parts.append(type_.replace("_", " "))
    if country:
        parts.append("worldwide" if country == "WORLDWIDE" else country)
    return " ".join(p for p in parts if p)


def _adjacent_roles(profile, primary_roles: list[str]) -> list[str]:
    lower_skills = {s.lower() for s in _listify(getattr(profile, "skills", []))}
    education_text = " ".join(
        " ".join(str(v) for v in edu.model_dump().values() if v)
        for edu in getattr(profile, "education", [])
    ).lower()
    base = " ".join(sorted(lower_skills)) + " " + education_text

    adjacent: list[str] = []
    if any(k in lower_skills or k in education_text for k in ("ai", "mistral ai", "computer vision", "machine learning", "rag", "chromadb")):
        adjacent.extend(["AI Engineer", "Machine Learning Engineer"])
    if "data science" in base or "pandas" in lower_skills:
        adjacent.append("Data Scientist")
    if any(s in lower_skills for s in ("react", "next.js", "typescript")):
        adjacent.append("Frontend Developer")
    if any(s in lower_skills for s in ("python", "fastapi", "node.js", "spring boot", "sql")):
        adjacent.append("Backend Developer")
    if "flutter" in lower_skills:
        adjacent.append("Flutter Developer")

    primary = {r.lower() for r in primary_roles}
    deduped: list[str] = []
    for role in adjacent:
        if role.lower() not in primary and role not in deduped:
            deduped.append(role)
    return deduped


def generate_queries_with_metadata(
    profile,
    preferences,
    *,
    seniority_override: str | None = None,
    exclude_terms: list[str] | None = None,
) -> list[SearchQuery]:
    primary = target_terms(profile, preferences=preferences)
    skill_terms = _listify(getattr(profile, "skills", []))
    modes = _modes(preferences)
    types = _employment_types(preferences)
    countries = _countries(preferences)
    exclude = _exclude_terms(exclude_terms)
    seniority = seniority_override or getattr(preferences, "seniority_override", None) or getattr(
        profile, "seniority", None
    )
    mode = modes[0] if modes else None
    employment_type = types[0] if types else None

    queries: list[SearchQuery] = []
    for role in primary[:2] or ["Software Engineer"]:
        queries.append(
            SearchQuery(text=_role_text(role, mode=mode, type_=employment_type, country=countries[0]), kind="role")
        )
        if seniority:
            queries.append(
                SearchQuery(
                    text=_role_text(
                        role,
                        seniority=seniority,
                        mode=mode,
                        type_=employment_type,
                        country=countries[0],
                    ),
                    kind="seniority",
                )
            )

    adjacent_roles = _adjacent_roles(profile, primary)
    for role in adjacent_roles[:3]:
        queries.append(
            SearchQuery(
                text=_role_text(role, mode=mode, type_=employment_type, country=countries[0]),
                kind="adjacent",
            )
        )

    primary_role = (primary[:2] or ["Software Engineer"])[0]
    if len(skill_terms) >= 2:
        queries.append(
            SearchQuery(
                text=f"{primary_role} with {skill_terms[0]} {skill_terms[1]} jobs {mode or 'remote'}",
                kind="skill_role",
            )
        )
    if len(skill_terms) >= 4:
        queries.append(
            SearchQuery(
                text=f"{primary_role} with {skill_terms[2]} {skill_terms[3]} {employment_type or 'full time'} jobs",
                kind="skill_role",
            )
        )

    for domain in _ATS_DOMAINS:
        queries.append(SearchQuery(text=f"site:{domain} '{primary_role}'", kind="ats"))

    for country in dict.fromkeys(countries):
        if country == "WORLDWIDE":
            continue
        queries.append(
            SearchQuery(
                text=_role_text(
                    primary_role,
                    mode=mode,
                    type_=employment_type,
                    country=country,
                ),
                kind="country",
            )
        )

    queries = _dedupe(queries)
    if exclude:
        suffix = " " + " ".join(f'- "{term}"' for term in exclude)
        queries = [SearchQuery(text=q.text + suffix, kind=q.kind) for q in queries]
    return queries[:_MAX_QUERIES]


def generate_queries(
    profile,
    preferences,
    *,
    seniority_override: str | None = None,
    exclude_terms: list[str] | None = None,
) -> list[str]:
    return [
        q.text
        for q in generate_queries_with_metadata(
            profile,
            preferences,
            seniority_override=seniority_override,
            exclude_terms=exclude_terms,
        )
    ]
