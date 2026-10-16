import asyncio

from app.extraction import ats


def _patch_client(monkeypatch, payload):
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            return FakeResponse()

    def factory(*args, **kwargs):
        return FakeClient()

    monkeypatch.setattr("httpx.AsyncClient", factory)


def test_detect_ats_platforms():
    assert ats.detect_ats("https://boards.greenhouse.io/x/jobs/1") == "greenhouse"
    assert ats.detect_ats("https://jobs.lever.co/x/1") == "lever"
    assert ats.detect_ats("https://jobs.ashbyhq.com/x/1") == "ashby"
    assert ats.detect_ats("https://example.com/jobs/1") is None


def test_greenhouse_adapter_extracts_job(monkeypatch):
    payload = {
        "title": "Senior Backend Engineer",
        "company_name": "Acme",
        "content": "<p>Remote full-time role</p>",
        "location": {"name": "Berlin, DE"},
        "updated_at": "2026-10-01T00:00:00",
    }
    _patch_client(monkeypatch, payload)

    jobs = asyncio.run(ats._greenhouse_job("https://boards.greenhouse.io/acme/jobs/123"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Acme"
    assert job.location == "Berlin, DE"
    assert job.url == "https://boards.greenhouse.io/acme/jobs/123"


def test_lever_adapter_extracts_job(monkeypatch):
    payload = {
        "text": "Platform Engineer",
        "descriptionPlain": "Remote full-time platform role",
        "hostedUrl": "https://jobs.lever.co/acme/abc",
        "createdAt": 1727740800000,
        "categories": {
            "location": "Paris, FR",
            "commitment": "Full-time",
        },
        "workplaceType": "remote",
    }
    _patch_client(monkeypatch, payload)

    jobs = asyncio.run(ats._lever_job("https://jobs.lever.co/acme/abc"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Platform Engineer"
    assert job.location == "Paris, FR"
    assert job.employment_type == "full_time"
    assert job.work_mode == "remote"


def test_ashby_adapter_extracts_job(monkeypatch):
    payload = {
        "jobs": [
            {
                "id": "abc123",
                "title": "ML Engineer",
                "jobUrl": "https://jobs.ashbyhq.com/acme/abc123",
                "publishedAt": "2026-10-01T00:00:00.000Z",
                "employmentType": "FullTime",
                "isRemote": True,
                "location": "Worldwide",
                "descriptionPlain": "Remote ML role",
                "organizationName": "Acme",
            }
        ]
    }
    _patch_client(monkeypatch, payload)

    jobs = asyncio.run(ats._ashby_job("https://jobs.ashbyhq.com/acme/abc123"))
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "ML Engineer"
    assert job.company == "Acme"
    assert job.work_mode == "remote"


def test_fetch_ats_job_returns_none_for_unknown_url(monkeypatch):
    assert asyncio.run(ats.fetch_ats_job("https://example.com/jobs/1")) is None
