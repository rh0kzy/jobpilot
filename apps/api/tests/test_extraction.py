from pathlib import Path

from app.extraction.extractor import extract_jobs


def test_extruct_is_available():
    import extruct

    assert extruct is not None


async def test_jsonld_extraction_saved_real_fixture():
    html = Path("tests/fixtures/real_job_remotive.html").read_text()
    jobs = await extract_jobs(html, "https://remotive.com/remote-jobs/marketing/remote-office-assistant-1680495")
    assert len(jobs) == 1
    assert jobs[0].title
    assert jobs[0].company
    assert jobs[0].url.endswith("remote-office-assistant-1680495")
    assert jobs[0].posted_date


async def test_jsonld_extraction_minimal_fixture():
    html = Path("tests/fixtures/job_jsonld.html").read_text()
    jobs = await extract_jobs(html, "https://example.com/job/1")
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme"
    assert jobs[0].country == "DE"
    assert jobs[0].work_mode == "remote"