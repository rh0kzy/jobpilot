from pathlib import Path

from app.extraction.extractor import extract_jobs


def test_jsonld_extraction():
    html = Path("tests/fixtures/job_jsonld.html").read_text()
    jobs = __import__("asyncio").run(extract_jobs(html, "https://example.com/job/1"))
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme"
    assert jobs[0].country == "DE"
    assert jobs[0].work_mode == "remote"