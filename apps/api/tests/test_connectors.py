import asyncio

from app.connectors import arbeitnow, remoteok


def test_arbeitnow_follows_redirects_and_prefilters(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {
                        "slug": "full-stack-developer",
                        "title": "Full Stack Developer",
                        "company_name": "Example",
                        "url": "https://www.arbeitnow.com/job/full-stack-developer",
                        "remote": True,
                        "created_at": 0,
                        "tags": ["react"],
                        "description": "Build software",
                    },
                    {
                        "slug": "marketing-manager",
                        "title": "Marketing Manager",
                        "company_name": "Other",
                        "url": "https://www.arbeitnow.com/job/marketing-manager",
                        "remote": True,
                        "created_at": 0,
                        "tags": ["marketing"],
                        "description": "Marketing",
                    },
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params
            return FakeResponse()

    def factory(*args, **kwargs):
        captured["follow_redirects"] = kwargs.get("follow_redirects", False)
        return FakeClient()

    async def run():
        return await arbeitnow.fetch_jobs(
            limit=10, target_roles=["Full-Stack Developer"], search="Full-Stack Developer"
        )

    monkeypatch.setattr("httpx.AsyncClient", factory)
    jobs = asyncio.run(run())
    assert captured["url"].startswith("https://www.arbeitnow.com/api/job-board-api")
    assert captured["params"] == {"search": "Full-Stack Developer"}
    assert captured["follow_redirects"] is True
    assert [j.title for j in jobs] == ["Full Stack Developer"]


def test_remoteok_tag_parameter_passes(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return [
                {"legal": "link back to remoteok.com"},
                {
                    "slug": "dev",
                    "position": "Backend Engineer",
                    "company": "Example",
                    "url": "https://remoteok.com/remote-jobs/dev",
                    "tags": ["python"],
                    "date": "2026-10-15",
                    "description": "",
                },
                {
                    "slug": "support",
                    "position": "Support Specialist",
                    "company": "Other",
                    "url": "https://remoteok.com/remote-jobs/support",
                    "tags": ["support"],
                    "date": "2026-10-15",
                    "description": "",
                },
            ]

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params
            return FakeResponse()

    def factory(*args, **kwargs):
        captured["follow_redirects"] = kwargs.get("follow_redirects", False)
        return FakeClient()

    async def run():
        return await remoteok.fetch_jobs(limit=10, target_roles=["Backend Developer"], tag="python")

    monkeypatch.setattr("httpx.AsyncClient", factory)
    jobs = asyncio.run(run())
    assert captured["url"] == "https://remoteok.com/api"
    assert captured["params"] == {"tag": "python"}
    assert captured["follow_redirects"] is True
    assert [j.title for j in jobs] == ["Backend Engineer"]


def test_greenhouse_falls_back_to_individual_board_url(monkeypatch):
    import asyncio

    from app.connectors import greenhouse

    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "jobs": [
                    {
                        "id": 1234567,
                        "title": "Full Stack Engineer",
                        "absolute_url": "https://example.com/jobs/search?gh_jid=1234567",
                        "updated_at": "2026-10-01",
                        "content": "Remote full-time opportunity",
                        "tags": [],
                    }
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            return FakeResponse()

    def factory(*args, **kwargs):
        return FakeClient()

    monkeypatch.setattr(greenhouse, "_load_board_tokens", lambda: ["stripe"])
    monkeypatch.setattr("httpx.AsyncClient", factory)

    async def run():
        return await greenhouse.fetch_jobs(limit=10, target_roles=["Full-Stack Developer"])

    jobs = asyncio.run(run())
    assert captured["url"].endswith("/boards/stripe/jobs")
    assert jobs[0].url == "https://boards.greenhouse.io/stripe/jobs/1234567"


def test_greenhouse_board_file_has_at_least_20_boards():
    from pathlib import Path

    boards = [
        line
        for line in (Path("app/connectors/greenhouse_boards.txt")).read_text().splitlines()
        if line.strip()
    ]
    assert len(boards) >= 20