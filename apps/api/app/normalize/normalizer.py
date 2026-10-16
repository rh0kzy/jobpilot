"""Job normalization, deduplication and freshness marking."""

import re
import unicodedata
from datetime import date, timedelta

from app.core.models import Job


def _repair_mojibake(value):
    if not isinstance(value, str):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value



def _fold(text: str | None) -> str:
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()


_COUNTRY_ALIASES = {
    "CANADA": "CA",
    "COLOMBIA": "CO",
    "MEXICO": "MX",
    "BRAZIL": "BR",
    "BRASIL": "BR",
    "PORTUGAL": "PT",
    "SERBIA": "RS",
    "NORTH MACEDONIA": "MK",
    "MACEDONIA": "MK",
    "LATAM": None,
    "EMEA": None,
    "EU": None,
    "USA": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
    "ETATS UNIS": "US",
    "ESTADOS UNIDOS": "US",
    "ESTADOS UNIDOS DA AMERICA": "US",
    "ESTADOS UNIDOS DE AMERICA": "US",
    "FRANCE": "FR",
    "GERMANY": "DE",
    "DEUTSCHLAND": "DE",
    "ALGERIA": "DZ",
    "ALGERIE": "DZ",
    "ITALIA": "IT",
    "ITALY": "IT",
    "ESPANA": "ES",
    "ESPAÑA": "ES",
    "SPAIN": "ES",
    "POLSKA": "PL",
    "POLAND": "PL",
    "PERU": "PE",
    "PERÚ": "PE",
    "PEROU": "PE",
    "IRELAND": "IE",
    "EIRE": "IE",
    "UNITED KINGDOM": "GB",
    "UK": "GB",
    "GREAT BRITAIN": "GB",
    "INDIA": "IN",
    "BHARAT": "IN",
    "INDONESIA": "ID",
    "NETHERLANDS": "NL",
    "PAYS BAS": "NL",
    "BELGIUM": "BE",
    "BELGIQUE": "BE",
    "SWITZERLAND": "CH",
    "SUISSE": "CH",
    "AUSTRIA": "AT",
    "AUTRICHE": "AT",
    "MÉXICO": "MX",
    "ARGENTINA": "AR",
    "CHILE": "CL",
    "UNITED ARAB EMIRATES": "AE",
    "UAE": "AE",
    "EMIRATS ARABES UNIS": "AE",
    "SAUDI ARABIA": "SA",
    "ARABIE SAOUDITE": "SA",
    "EGYPT": "EG",
    "MOROCCO": "MA",
    "MAROC": "MA",
    "TUNISIA": "TN",
    "TUNISIE": "TN",
    "TURKEY": "TR",
    "TURQUIE": "TR",
    "UKRAINE": "UA",
    "RUSSIA": "RU",
    "ROSSIYA": "RU",
    "CHINA": "CN",
    "CHINE": "CN",
    "JAPAN": "JP",
    "JAPON": "JP",
    "KOREA": "KR",
    "SOUTH KOREA": "KR",
    "SINGAPORE": "SG",
    "AUSTRALIA": "AU",
    "NEW ZEALAND": "NZ",
    "SOUTH AFRICA": "ZA",
}

# Many non-Latin country names commonly seen in global postings.
_NON_LATIN_COUNTRY_ALIASES = {
    "دولة الإمارات العربية المتحدة": "AE",
    "المملكة العربية السعودية": "SA",
    "مصر": "EG",
    "المغرب": "MA",
    "تونس": "TN",
    "Türkiye": "TR",
    "Россия": "RU",
    "中国": "CN",
    "日本": "JP",
    "대한민국": "KR",
    "India": "IN",
}
_COUNTRY_ALIASES.update(_NON_LATIN_COUNTRY_ALIASES)

_CITY_COUNTRY = {
    "toronto": "CA",
    "vancouver": "CA",
    "montreal": "CA",
    "montréal": "CA",
    "ottawa": "CA",
    "waterloo": "CA",
    "calgary": "CA",
    "suitland": "US",
    "bengaluru": "IN",
    "bangalore": "IN",
    "berlin": "DE",
    "dublin": "IE",
    "london": "GB",
    "paris": "FR",
    "amsterdam": "NL",
    "brussels": "BE",
    "zurich": "CH",
    "vienna": "AT",
    "wien": "AT",
    "warsaw": "PL",
    "krakow": "PL",
    "kraków": "PL",
    "madrid": "ES",
    "barcelona": "ES",
    "rome": "IT",
    "roma": "IT",
    "milan": "IT",
    "milano": "IT",
    "munich": "DE",
    "münchen": "DE",
    "hamburg": "DE",
    "frankfurt": "DE",
    "new york": "US",
    "san francisco": "US",
    "seattle": "US",
    "chicago": "US",
    "boston": "US",
    "austin": "US",
    "denver": "US",
    "los angeles": "US",
    "miami": "US",
    "atlanta": "US",
    "dallas": "US",
    "houston": "US",
    "philadelphia": "US",
    "washington": "US",
    "remote": None,
    "united states": "US",
    "usa": "US",
    "canada": "CA",
    "india": "IN",
    "germany": "DE",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
    "poland": "PL",
    "peru": "PE",
    "perú": "PE",
    "portugal": "PT",
    "ireland": "IE",
    "united kingdom": "GB",
    "england": "GB",
    "scotland": "GB",
    "mexico": "MX",
    "brazil": "BR",
    "argentina": "AR",
    "colombia": "CO",
    "chile": "CL",
    "netherlands": "NL",
    "belgium": "BE",
    "switzerland": "CH",
    "austria": "AT",
}
_REGION_TERMS = {
    "emea": "EMEA",
    "europe, middle east and africa": "EMEA",
    "eu": "EU",
    "european union": "EU",
    "europe": "EU",
    "mena": "MENA",
    "middle east and north africa": "MENA",
    "middle east": "MENA",
    "latam": "LATAM",
    "latin america": "LATAM",
    "latin america and caribbean": "LATAM",
    "africa": "Africa",
    "apac": "APAC",
    "asia pacific": "APAC",
    "asia-pacific": "APAC",
    "north america": "North America",
    "americas": "North America",
}

_SINGLE_WORLDWIDE_TERMS = (
    "worldwide",
    "world wide",
    "anywhere",
    "global",
    "mondial",
    "mundial",
    "globalmente",
)
_COMPOSITE_WORLDWIDE_TERMS = (
    "anywhere in the world",
    "work from anywhere",
    "remote anywhere",
    "remote worldwide",
    "worldwide remote",
    "open to candidates worldwide",
    "open to applicants worldwide",
    "remote from anywhere",
    "any country",
    "tutto il mondo",
    "dans le monde entier",
    "partout dans le monde",
    "en todo el mundo",
    "en cualquier parte del mundo",
    "trabajo remoto en todo el mundo",
    "em todo o mundo",
    "em qualquer lugar do mundo",
    "trabalho remoto em qualquer lugar",
)
_WORLDWIDE_TERMS = _SINGLE_WORLDWIDE_TERMS + _COMPOSITE_WORLDWIDE_TERMS

_AUTH_TERMS = [
    "authorized to work",
    "authorised to work",
    "work authorization",
    "work authorisation",
    "right to work",
    "must be authorized",
    "must be authorised",
    "must reside",
    "must be located",
    "must be based",
    "citizen",
    "citizenship",
    "security clearance",
    "visa sponsorship",
    "visa status",
    "w2",
    "w-2",
    "eligible to work",
    "authorized to reside",
    "autorisé à travailler",
    "droit de travailler",
    "autorisé à résider",
    "citoyen",
    "habilitation de sécurité",
    "visa de travail",
    "doit résider",
    "autorizado a trabajar",
    "derecho a trabajar",
    "ciudadano",
    "autorización de trabajo",
    "debe residir",
    "autorizado a trabalhar",
    "direito de trabalhar",
    "cidadão",
    "autorização de trabalho",
    "deve residir",
]

# Exposed for Step 0.2 tests/reports.
AUTHORIZATION_PATTERNS = _AUTH_TERMS

# Exported alias for any code expecting a dedicated symbol.
scan_authorization_text_terms = _AUTH_TERMS


def _to_iso(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    upper = text.upper()
    if upper in {"EMEA", "EU", "LATAM", "APAC", "AFRICA", "MENA", "NORTH AMERICA"}:
        return None
    if upper == "WORLDWIDE":
        return None
    if len(upper) == 2 and upper.isalpha():
        return upper
    alias = _COUNTRY_ALIASES.get(upper)
    if alias:
        return alias
    city = _CITY_COUNTRY.get(text.strip().lower())
    if city:
        return city
    # Try alias by folded representation for accent-insensitive names.
    folded = _fold(text).upper()
    if folded != upper:
        alias = _COUNTRY_ALIASES.get(folded)
        if alias:
            return alias
        city = _CITY_COUNTRY.get(_fold(text))
        if city:
            return city
    return None


def scan_authorization_text(text: str | None) -> list[str]:
    folded = _fold(text)
    found: list[str] = []
    for term in _AUTH_TERMS:
        term_folded = _fold(term)
        if term_folded and re.search(rf"(?<![a-z0-9]){re.escape(term_folded)}(?![a-z0-9])", folded) and term_folded not in found:
            found.append(term_folded)
    return found


_AUTH_REQUIREMENT_PHRASES = (
    "must be",
    "required",
    "eligible to work",
    "authorized to work",
    "authorised to work",
    "authorized to reside",
    "authorised to reside",
    "citizens only",
    "citizenship required",
    "clearance required",
    "work authorization required",
    "work authorisation required",
    "right to work",
    "must reside",
    "must be located",
    "must be based",
    "doit être",
    "requis",
    "autorisé à travailler",
    "autorisé à résider",
    "citoyens seulement",
    "habilitation requise",
    "droit de travailler",
    "debe ser",
    "requerido",
    "autorizado a trabajar",
    "autorizado a residir",
    "ciudadanos solamente",
    "autorización de trabajo requerida",
    "deve ser",
    "obrigatório",
    "autorizado a trabalhar",
    "autorizado a residir",
    "cidadãos somente",
    "autorização de trabalho requerida",
)
_EEO_TERMS = (
    "equal opportunity",
    "equal-opportunity",
    "discrimination",
    "diversity",
    "minority",
    "protected veteran",
    "disability",
    "eeo",
)


def _split_sentences(text: str | None) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", str(text))
    return [p.strip() for p in parts if p.strip()]


def scan_authorization_requirements(text: str | None) -> list[str]:
    found: list[str] = []
    for sentence in _split_sentences(text):
        lowered = _fold(sentence)
        if any(term in lowered for term in _EEO_TERMS):
            continue
        if any(term in lowered for term in _AUTH_REQUIREMENT_PHRASES) and sentence not in found:
            found.append(sentence)
    return found


def extract_work_authorization(text: str | None) -> str | None:
    sentences = scan_authorization_requirements(text)
    if sentences:
        return " ".join(sentences)[:500]
    return None


def _region_label_from_text(value: str | None) -> str | None:
    if not value:
        return None
    lower = _fold(value)
    found: list[str] = []
    for needle, label in _REGION_TERMS.items():
        if re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", lower) and label not in found:
            found.append(label)
    return " / ".join(found) if found else None


def _is_explicit_worldwide(text: str | None, allow_single: bool = True) -> bool:
    lower = _fold(text)
    terms = _WORLDWIDE_TERMS if allow_single else _COMPOSITE_WORLDWIDE_TERMS
    return any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lower) for term in terms)


def _extract_regions(*texts: str | None) -> list[str]:
    combined = " / ".join(str(t) for t in texts if t)
    lower = _fold(combined)
    found: list[str] = []
    for needle, label in _REGION_TERMS.items():
        if re.search(rf"(?<![a-z]){re.escape(needle)}(?![a-z])", lower) and label not in found:
            found.append(label)
    return found


def _extract_stated_countries(*texts: str | None) -> list[str]:
    combined = " / ".join(str(t) for t in texts if t)
    lower = _fold(combined)
    found: list[str] = []
    # Country aliases.
    aliases_items = sorted(_COUNTRY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    for name, code in aliases_items:
        if not code:
            continue
        if re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", lower) and code not in found:
            found.append(code)
    # City-to-country map.
    cities_items = sorted(_CITY_COUNTRY.items(), key=lambda x: len(x[0]), reverse=True)
    for city, code in cities_items:
        if not code:
            continue
        if re.search(rf"(?<![a-z]){re.escape(city.lower())}(?![a-z])", lower) and code not in found:
            found.append(code)
    return found


def _norm_enum(value: str | None, allowed: set[str], unspecified: str) -> str:
    if value is None or str(value).strip() == "":
        return unspecified
    v = str(value).strip().lower()
    aliases = {
        "full time": "full_time",
        "full-time": "full_time",
        "part time": "part_time",
        "part-time": "part_time",
        "on-site": "onsite",
        "on site": "onsite",
        "telecommute": "remote",
        "remote": "remote",
    }
    v = aliases.get(v, v)
    if v not in allowed:
        return unspecified
    return v


def _norm_country(value: str | None) -> str:
    code = _to_iso(value)
    if code is None:
        country = (value or "").strip().upper()
        if not country:
            return "unspecified"
        if country == "WORLDWIDE":
            return "unspecified"
        return "unspecified"
    if code == "WORLDWIDE":
        return "unspecified"
    return code


def _clean_location(value: str | None) -> str | None:
    if value is None:
        return None
    parts = [p.strip() for p in str(value).split(",")]
    deduped: list[str] = []
    for part in parts:
        if part and part not in deduped:
            deduped.append(part)
    text = ", ".join(deduped).strip(" ,")
    return text or None


def _norm_seniority_level(text: str | None) -> str:
    lowered = str(text or "").lower()
    if any(term in lowered for term in ("principal", "staff", "distinguished", "lead")):
        return "lead"
    if "senior" in lowered or "sr." in lowered or "sr " in lowered:
        return "senior"
    if any(term in lowered for term in ("junior", "jr.", "entry", "graduate", "intern")):
        return "junior"
    if any(term in lowered for term in ("mid", "middle")):
        return "mid"
    return "unspecified"


def _norm_remote_scope(value: str | None) -> str:
    v = str(value or "").strip().lower()
    if v in {"worldwide", "region_restricted", "country_restricted", "unclear"}:
        return v
    return "unclear"


def _clean_list(values) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for v in values:
        code = _to_iso(str(v))
        code = code if code else str(v).strip().upper()
        if not code:
            continue
        if code == "WORLDWIDE":
            continue
        if len(code) > 2 and code not in {"EMEA", "EU", "LATAM", "APAC", "AFRICA", "MENA", "NORTH AMERICA"}:
            continue
        # Drop region labels stored as ISO-like values for allowed_countries.
        if code in {"EMEA", "EU", "LATAM", "APAC", "AFRICA", "MENA", "NORTH AMERICA"}:
            continue
        if code not in out:
            out.append(code)
    return out


def normalize_job(job: Job) -> Job:
    # Repair common mojibake before any eligibility inference.
    job = job.model_copy(
        update={
            "title": _repair_mojibake(job.title),
            "company": _repair_mojibake(job.company),
            "location": _repair_mojibake(job.location),
            "allowed_regions": _repair_mojibake(job.allowed_regions),
            "eligibility_evidence": _repair_mojibake(job.eligibility_evidence),
            "page_text": _repair_mojibake(job.page_text),
            "work_authorization_required": _repair_mojibake(job.work_authorization_required),
        }
    )

    title_text = (job.title or "").lower()
    work_mode = _norm_enum(
        job.work_mode, {"remote", "hybrid", "onsite", "unspecified"}, "unspecified"
    )
    employment_type = _norm_enum(
        job.employment_type,
        {"full_time", "part_time", "contract", "internship", "unspecified"},
        "unspecified",
    )
    if any(term in title_text for term in ("freelance", "contract", "consultant")):
        employment_type = "contract"
    seniority_text = (job.seniority or "").strip() or None
    seniority_level = job.seniority_level or _norm_seniority_level(
        " ".join(part for part in [seniority_text, job.title] if part)
    )
    if seniority_level not in {"junior", "mid", "senior", "lead", "unspecified"}:
        seniority_level = _norm_seniority_level(seniority_level)

    location_text = str(job.location or "").strip()
    allowed_regions_text = str(job.allowed_regions or "").strip()
    evidence_seed = str(job.eligibility_evidence or "").strip()
    country_seed = str(job.country or "").strip()
    page_text = str(job.page_text or "")
    folded_location = _fold(location_text)

    text_all = " / ".join(
        v for v in [location_text, allowed_regions_text, evidence_seed, country_seed, page_text] if v
    )
    location_worldwide_text = " / ".join(
        v for v in [location_text, allowed_regions_text, evidence_seed, country_seed] if v
    )
    explicit_worldwide = _is_explicit_worldwide(location_worldwide_text, allow_single=True) or _is_explicit_worldwide(
        page_text, allow_single=False
    )

    # Trusted structured applicant locations.
    source_countries: list[str] = []
    for v in job.allowed_countries or []:
        iso = _to_iso(str(v))
        if iso and iso not in source_countries:
            source_countries.append(iso)

    # Explicit applicant wording means the location describes who may apply,
    # not merely where the company or role is based.
    applicant_markers = ("remote", "anywhere", "worldwide", "must be located", "must reside", "authorized to work", "eligible to work")
    location_explicit_applicant = any(marker in folded_location for marker in applicant_markers)

    stated_countries: list[str] = []
    # Structured fields are trusted applicant-location data even when the
    # visible location is only a city/country.
    for code in _extract_stated_countries(allowed_regions_text, evidence_seed, country_seed):
        if code not in stated_countries:
            stated_countries.append(code)
    for code in source_countries:
        if code not in stated_countries:
            stated_countries.append(code)
    if location_explicit_applicant:
        for code in _extract_stated_countries(location_text):
            if code not in stated_countries:
                stated_countries.append(code)

    # Regions only when explicitly stated as EMEA/EU/MENA/LATAM/APAC/Africa/North America.
    regions: list[str] = []
    for region in _extract_regions(location_text, allowed_regions_text, evidence_seed):
        if region not in regions:
            regions.append(region)

    location_country = _to_iso(location_text.split(",")[0].strip()) if location_text else None
    if not location_country and location_text:
        location_country = _to_iso(location_text)

    structural_onsite = work_mode in {"onsite", "hybrid"}
    page_onsite_markers = ("on-site", "onsite", "hybrid", "in office", "on site")
    page_implies_onsite = any(marker in _fold(page_text) for marker in page_onsite_markers) and work_mode != "remote"

    # Decide remote_scope.
    if explicit_worldwide:
        remote_scope = "worldwide"
    elif regions:
        remote_scope = "region_restricted"
    elif stated_countries:
        remote_scope = "country_restricted"
    elif structural_onsite or (page_implies_onsite and location_country):
        remote_scope = "location_bound"
    elif location_explicit_applicant and stated_countries:
        remote_scope = "country_restricted"
    else:
        remote_scope = "unclear"

    allowed_countries = list(stated_countries) if remote_scope in {"country_restricted", "region_restricted"} and remote_scope == "country_restricted" else []
    if remote_scope == "country_restricted":
        allowed_countries = list(stated_countries)
    else:
        allowed_countries = []

    if remote_scope == "region_restricted":
        allowed_regions_value = " / ".join(regions) if regions else None
    elif remote_scope == "worldwide":
        allowed_regions_value = (allowed_regions_text or None) if allowed_regions_text.lower() in {"worldwide"} else "Worldwide"
        if not allowed_regions_value:
            allowed_regions_value = "Worldwide"
    else:
        allowed_regions_value = None

    # Dedupe region segments.
    if allowed_regions_value and allowed_regions_value != "Worldwide":
        segments = [seg.strip() for seg in allowed_regions_value.replace(" / ", ",").split(",")]
        deduped = []
        for seg in segments:
            if seg and seg not in deduped:
                deduped.append(seg)
        allowed_regions_value = " / ".join(deduped) if deduped else None

    # Country field: always ISO if location states one.
    country_final = _to_iso(country_seed) or location_country
    if remote_scope in {"country_restricted", "region_restricted"} and stated_countries:
        country_final = stated_countries[0]
    if remote_scope == "worldwide":
        country_final = None
    country_norm = _norm_country(country_final)

    location_hint = None
    if remote_scope == "unclear" and location_country:
        location_hint = location_country

    company = (job.company or "").strip()
    source = (job.source or "").strip()
    source_host = source.split("/", 1)[0].strip().lower()
    generic_values = {
        "",
        "unknown",
        "none",
        "n/a",
        "na",
        "company",
        "employer",
        "digital",
    }
    generic = company.lower() in generic_values or company.lower() == source.lower()
    if not generic and source_host and " " not in company and company and company.lower() == source_host.split(".")[0]:
        generic = True
    if generic:
        company = "Unknown"
    confidence = job.confidence
    if generic:
        confidence = min(confidence if confidence is not None else 0.5, 0.4)

    auth_text = " / ".join(
        str(v) for v in [job.work_authorization_required, page_text, location_text, evidence_seed] if v
    )
    authorization = (job.work_authorization_required or "").strip() or None
    if not authorization:
        authorization = extract_work_authorization(auth_text)

    # Evidence: quoted/structured snippet, never bare ISO codes.
    if remote_scope == "worldwide":
        eligibility_evidence = evidence_seed or location_text or "Worldwide"
        if eligibility_evidence.lower() not in text_all.lower():
            eligibility_evidence = "Worldwide"
    elif remote_scope == "region_restricted":
        eligibility_evidence = allowed_regions_text or evidence_seed or location_text
        if eligibility_evidence.lower() not in text_all.lower() and allowed_regions_text:
            eligibility_evidence = allowed_regions_text
    elif remote_scope == "country_restricted":
        eligibility_evidence = location_text or evidence_seed or ", ".join(stated_countries)
        # Keep exact location text; if sourcing from structured field, keep field/value style.
        if job.allowed_countries and location_explicit_applicant is False and stated_countries == source_countries:
            eligibility_evidence = f"applicantLocationRequirements: {', '.join(stated_countries)}"
        if len(eligibility_evidence) > 200:
            eligibility_evidence = eligibility_evidence[:200].rstrip()
    elif remote_scope == "location_bound":
        eligibility_evidence = location_text or evidence_seed
        if len(eligibility_evidence) > 200:
            eligibility_evidence = eligibility_evidence[:200].rstrip()
    else:
        eligibility_evidence = evidence_seed or None

    if remote_scope == "unclear":
        eligibility_evidence = None
    if remote_scope != "unclear" and not eligibility_evidence and location_text:
        eligibility_evidence = location_text[:200].rstrip()
    if remote_scope != "unclear" and not eligibility_evidence:
        remote_scope = "unclear"
        location_hint = location_country
        eligibility_evidence = None

    if remote_scope == "worldwide":
        job = job.model_copy(update={"allowed_countries": []})

    return job.model_copy(
        update={
            "title": " ".join(str(job.title or "").split()),
            "company": company,
            "work_mode": work_mode,
            "employment_type": employment_type,
            "location": _clean_location(job.location),
            "country": country_norm,
            "remote_scope": remote_scope,
            "location_hint": location_hint,
            "allowed_countries": _clean_list(allowed_countries) if remote_scope != "worldwide" else [],
            "allowed_regions": allowed_regions_value,
            "timezone_restriction": (job.timezone_restriction or "").strip() or None,
            "work_authorization_required": authorization,
            "eligibility_evidence": eligibility_evidence,
            "confidence": confidence,
            "seniority": seniority_text,
            "seniority_level": seniority_level,
            "page_type": job.page_type,
        }
    )
def mark_freshness(
    jobs: list[Job],
    max_age_days: int = 60,
    today: date | None = None,
) -> list[Job]:
    """Flag freshness without dropping stale/unknown jobs."""
    today = today or date.today()
    cutoff = today - timedelta(days=max_age_days)
    marked: list[Job] = []
    for job in jobs:
        if job.posted_date is None:
            status = "unknown"
        elif job.posted_date < cutoff:
            status = "stale"
        else:
            status = "current"
        marked.append(job.model_copy(update={"freshness_status": status}))
    return marked


def dedupe(jobs: list[Job]) -> list[Job]:
    seen: set[tuple] = set()
    unique: list[Job] = []
    for job in jobs:
        key = (job.company.lower().strip(), job.title.lower().strip(), (job.country or "").lower())
        unique.append(job)
        seen.add(key)
    # Preserve previous dedup semantics: drop duplicates.
    # Recompute properly because above appended all.
    seen = set()
    unique = []
    for job in jobs:
        key = (job.company.lower().strip(), job.title.lower().strip(), (job.country or "").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique
