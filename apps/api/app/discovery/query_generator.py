"""Build search queries from a Profile + Preferences."""

from app.core.models import Preferences, Profile


def generate_queries(profile: Profile, preferences: Preferences) -> list[str]:
    terms = profile.job_titles or profile.skills[:5] or ["jobs"]
    countries = preferences.countries or ["WORLDWIDE"]
    mode_words = [m.value.replace("_", " ") for m in preferences.work_modes]
    type_words = [t.value.replace("_", " ") for t in preferences.employment_types]
    queries = []
    for term in terms[:4]:
        for country in countries[:3]:
            location = "worldwide" if country == "WORLDWIDE" else country
            parts = [term, "jobs"]
            if mode_words:
                parts.append(" ".join(mode_words))
            if type_words:
                parts.append(" ".join(type_words))
            parts.append(location)
            queries.append(" ".join(parts))
    # deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    return unique
