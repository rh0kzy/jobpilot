from app.core.models import Education, EmploymentType, Preferences, Profile, WorkMode
from app.discovery.query_generator import (
    generate_queries_with_metadata,
    target_prefilter_terms,
    target_terms,
)


def _profile():
    return Profile(
        job_titles=["Full-Stack Developer", "Co-Founder"],
        skills=["JavaScript", "TypeScript", "Python", "React", "RAG pipelines"],
        education=[
            Education(
                degree="Computer Engineering",
                field="AI Engineering",
                institution="USTHB",
                start_year=2023,
                end_year=2028,
            )
        ],
        seniority="Mid-Level",
    )


def _prefs(countries=None):
    return Preferences(
        work_modes=[WorkMode.remote],
        employment_types=[EmploymentType.full_time],
        countries=countries or ["WORLDWIDE"],
    )


def test_excludes_founder_and_query_count():
    queries = generate_queries_with_metadata(_profile(), _prefs())
    assert 8 <= len(queries) <= 15
    assert not any("co-founder" in q.text.lower() for q in queries)


def test_no_skill_only_queries():
    queries = generate_queries_with_metadata(_profile(), _prefs())
    for query in queries:
        tokens = query.text.lower().replace("'", "").split()
        if query.kind != "ats":
            assert "jobs" in tokens
        assert (
            "full-stack" in tokens
            or "developer" in tokens
            or "engineer" in tokens
            or query.kind == "ats"
        )
    assert not any(q.text.lower().startswith("javascript typescript jobs") for q in queries)


def test_adjacent_ai_roles_marked_adjacent():
    queries = generate_queries_with_metadata(_profile(), _prefs())
    adjacent = [q for q in queries if q.kind == "adjacent"]
    assert adjacent
    assert any("AI Engineer" in q.text for q in adjacent)


def test_seniority_override_and_exclusions():
    queries = generate_queries_with_metadata(
        _profile(),
        _prefs(),
        seniority_override="Senior",
        exclude_terms=["unpaid"],
    )
    assert any("senior" in q.text.lower() for q in queries)
    assert all('- "unpaid"' in q.text for q in queries)


def test_country_specific_queries_include_country():
    queries = generate_queries_with_metadata(_profile(), _prefs(countries=["FR", "US"]))
    assert any(" FR " in f" {q.text} " for q in queries)
    assert any(" US " in f" {q.text} " for q in queries)


def test_ats_domains_present_and_deduplicated():
    queries = generate_queries_with_metadata(_profile(), _prefs())
    assert any(q.kind == "ats" and "boards.greenhouse.io" in q.text for q in queries)
    texts = [q.text.lower() for q in queries]
    assert len(texts) == len(set(texts))

def test_canonicalizes_french_roles_and_skips_internship():
    profile = Profile(job_titles=["Développeur Fullstack indépendant", "Stagiaire Développeur"], skills=["NestJS"])
    prefs = _prefs()
    roles = target_terms(profile, prefs)
    assert roles == ["Full-Stack Developer"]
    assert target_prefilter_terms(profile, prefs) == ["Full-Stack Developer", "NestJS"]


def test_canonicalizes_english_roles():
    profile = Profile(job_titles=["Back-End Software Engineer", "Frontend Developer"], skills=["React"])
    roles = target_terms(profile, _prefs())
    assert roles == ["Backend Developer", "Frontend Developer"]
