from app.core.models import Job
from app.normalize.normalizer import dedupe, normalize_job


def test_normalize_infers_work_mode_and_employment_type():
    job = Job(
        title="Senior Python Developer",
        company="Acme",
        url="https://example.com/jobs/1",
        source="example.com",
        page_text="Full-time, remote role. CDI.",
    )
    normalized = normalize_job(job)
    assert normalized.work_mode == "remote"
    assert normalized.employment_type == "full_time"
    assert normalized.country == "unspecified"


def test_normalize_does_not_match_international_as_internship():
    job = Job(title="Engineer", company="Example", url="u", source="s", page_text="International remote team")
    assert normalize_job(job).employment_type != "internship"


def test_normalize_fills_unknown_fields():
    job = Job(title="Mystery", company="Example", url="https://example.com/jobs/2", source="example.com", page_text="")
    normalized = normalize_job(job)
    assert normalized.work_mode == "unspecified"
    assert normalized.employment_type == "unspecified"


def test_dedupe_by_company_title_country():
    job = Job(title="Engineer", company="Acme", url="u1", source="s", page_text="Remote full time", country="DE")
    duplicate = Job(title="Engineer", company="Acme", url="u2", source="s", page_text="Remote full time", country="de")
    assert len(dedupe([normalize_job(job), normalize_job(duplicate)])) == 1