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
    url = "https://example.com/job/1"
    jobs = await extract_jobs(html, url)
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Acme"
    assert job.country == "DE"
    assert job.location == "Berlin, DE"
    assert job.work_mode == "remote"
    assert job.employment_type == "full_time"
    assert job.allowed_countries == ["US"]
    assert job.seniority == "Senior"
    assert job.url == url
    assert job.original_url == url


async def test_unmeaningful_page_returns_no_llm_call():
    class Provider:
        def __init__(self):
            self.calls = 0

        async def complete(self, prompt, system=None):
            self.calls += 1
            return "[]"

    provider = Provider()
    jobs = await extract_jobs("<html><body></body></html>", "https://example.com/job/2", provider)
    assert jobs == []
    assert provider.calls == 0

def test_iso_country_detection():
    from app.extraction.extractor import _is_iso_country

    assert _is_iso_country("US") is True
    assert _is_iso_country("usa") is False
    assert _is_iso_country("X") is False


def test_applicant_locations_iso_and_region_extraction():
    from app.extraction.extractor import _extract_applicant_locations

    item = {
        "applicantLocationRequirements": [
            {"address": {"addressCountry": "US"}},
            {"address": {"addressCountry": "EMEA"}},
        ]
    }
    values = _extract_applicant_locations(item)
    assert values == ["US", "EMEA"]


def test_jsonld_eligibility_fields():
    from pathlib import Path

    html = Path("tests/fixtures/job_jsonld.html").read_text()
    import asyncio
    jobs = asyncio.run(__import__("app.extraction.extractor", fromlist=["extract_jobs"]).extract_jobs(html, "https://example.com/job/1"))
    # fixture's applicantLocationRequirements produces allowed_countries US; evidence remains ISO.
    assert jobs[0].allowed_countries == ["US"]
    assert jobs[0].eligibility_evidence == "US"
