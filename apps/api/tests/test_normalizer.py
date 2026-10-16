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
    assert normalized.work_mode is None
    assert normalized.employment_type is None
    assert normalized.country is None


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