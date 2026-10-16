from datetime import date, timedelta

from app.core.models import Job
from app.normalize.normalizer import dedupe, mark_freshness, normalize_job


def test_normalize_validates_and_leaves_unspecified():
    job = Job(
        title="Senior Python Developer",
        company="Acme",
        url="https://example.com/jobs/1",
        source="example.com",
        page_text="Full-time, remote role. CDI.",
    )
    normalized = normalize_job(job)
    assert normalized.work_mode == "unspecified"
    assert normalized.employment_type == "unspecified"
    assert normalized.country == "unspecified"


def test_normalize_keeps_explicit_values():
    job = Job(
        title="Senior Python Developer",
        company="Acme",
        url="https://example.com/jobs/1",
        source="example.com",
        work_mode="Remote",
        employment_type="Full Time",
        country="fr",
        location="Paris",
    )
    normalized = normalize_job(job)
    assert normalized.work_mode == "remote"
    assert normalized.employment_type == "full_time"
    assert normalized.country == "FR"


def test_freshness_flags_stale_and_unknown_without_dropping():
    today = date(2026, 10, 15)
    old = Job(
        title="Old job",
        company="A",
        url="u",
        source="s",
        posted_date=today - timedelta(days=90),
    )
    unknown = Job(title="Unknown date", company="B", url="u2", source="s")
    current = Job(title="Current", company="C", url="u3", source="s", posted_date=today)
    marked = mark_freshness([old, unknown, current], max_age_days=60, today=today)
    assert [j.freshness_status for j in marked] == ["stale", "unknown", "current"]


def test_dedupe_by_company_title_country():
    job = Job(title="Engineer", company="Acme", url="u1", source="s", page_text="", country="DE")
    duplicate = Job(title="Engineer", company="Acme", url="u2", source="s", page_text="", country="de")
    assert len(dedupe([normalize_job(job), normalize_job(duplicate)])) == 1

def test_normalize_country_iso_validation():
    for raw, expected in [("fr", "FR"), ("US", "US"), ("worldwide", "WORLDWIDE"), (None, "unspecified"), ("NotACountry", "unspecified")]:
        job = Job(title="Engineer", company="Acme", url="u", source="s", country=raw)
        assert normalize_job(job).country == expected


def test_normalize_location_deduplicates_segments():
    job = Job(title="Engineer", company="Acme", url="u", source="s", location="Berlin, Berlin, DE")
    assert normalize_job(job).location == "Berlin, DE"


def test_normalize_remote_scope_inference():
    job = Job(title="Engineer", company="Acme", url="u", source="s", allowed_countries=["DE"], remote_scope=None)
    assert normalize_job(job).remote_scope == "country_restricted"
    job2 = Job(title="Engineer", company="Acme", url="u", source="s", page_text="Open worldwide", remote_scope=None)
    assert normalize_job(job2).remote_scope == "worldwide"


def test_clara_locations_become_countries():
    job = Job(title="Senior Fullstack Engineer", company="Clara", url="u", source="greenhouse.io/clara",
              location="Bogota / CUN / Colombia; Mexico City / CDMX / Mexico; Sao Paulo / SP / Brazil",
              allowed_regions="Bogota / CUN / Colombia; Mexico City / CDMX / Mexico; Sao Paulo / SP / Brazil",
              remote_scope=None)
    normalized = normalize_job(job)
    assert normalized.remote_scope == "country_restricted"
    assert normalized.allowed_countries == ["CO", "MX", "BR"]
    assert normalized.eligibility_evidence


def test_northbeam_canada():
    job = Job(title="Senior Fullstack Engineer", company="Northbeam", url="u", source="greenhouse.io/northbeam",
              location="Remote - Canada", allowed_regions="Remote - Canada", remote_scope=None)
    normalized = normalize_job(job)
    assert normalized.remote_scope == "country_restricted"
    assert normalized.allowed_countries == ["CA"]


def test_worldwide_only_explicit():
    job = Job(title="Backend Developer", company="Acme", url="u", source="s", page_text="Remote anywhere in the world", remote_scope=None)
    job2 = Job(title="Backend Developer", company="Acme", url="u", source="s", location="Ukraine", remote_scope=None)
    assert normalize_job(job).remote_scope == "worldwide"
    assert normalize_job(job2).remote_scope == "unclear"
