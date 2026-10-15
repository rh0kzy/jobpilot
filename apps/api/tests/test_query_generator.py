from app.core.models import EmploymentType, Preferences, Profile, WorkMode
from app.discovery.query_generator import generate_queries


def _profile():
    return Profile(
        job_titles=["Full-Stack Developer", "Co-Founder"],
        skills=["JavaScript", "TypeScript", "Python", "React", "Next.js", "FastAPI", "PostgreSQL", "Docker"],
        seniority="Mid-Level",
    )


def _prefs(countries=None):
    return Preferences(
        work_modes=[WorkMode.remote],
        employment_types=[EmploymentType.full_time],
        countries=countries or ["WORLDWIDE"],
    )


def test_excludes_founder_and_queries_between_8_and_15():
    queries = generate_queries(_profile(), _prefs())
    assert 8 <= len(queries) <= 15
    assert not any("co-founder" in q.lower() or "founder jobs" in q.lower() for q in queries)


def test_seniority_override_and_exclusions():
    queries = generate_queries(
        _profile(),
        _prefs(),
        seniority_override="Senior",
        exclude_terms=["unpaid"],
    )
    assert any("senior" in q.lower() for q in queries)
    assert any('- "unpaid"' in q for q in queries)


def test_country_specific_queries_include_country():
    queries = generate_queries(_profile(), _prefs(countries=["fr", "US"]))
    assert any(" FR " in f" {q} " for q in queries)
    assert any(" US " in f" {q} " for q in queries)


def test_deduplicates():
    queries = generate_queries(_profile(), _prefs())
    assert len(queries) == len({q.lower() for q in queries})