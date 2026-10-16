import asyncio

from app.core.models import Job
from app.discovery.fetcher import FetchResult
from app.extraction import url_verification


def test_verify_greenhouse_generic_company_domain_falls_back_to_board_url(monkeypatch):
    job = Job(
        title="Full Stack Engineer",
        company="Stripe",
        url="https://boards.greenhouse.io/stripe/jobs/123",
        original_url="https://stripe.com/jobs/search?gh_jid=123",
        source="greenhouse.io/stripe",
    )

    async def fake_fetch_detailed(url, timeout=30, cache_dir="./.cache"):
        if url == "https://stripe.com/jobs/search?gh_jid=123":
            return FetchResult(
                url=url,
                status="ok",
                html="<html><body>job search page</body></html>",
                final_url=url,
            )
        return FetchResult(
            url=url,
            status="ok",
            html="<html><body><h1>Full Stack Engineer</h1><a href=/apply>Apply now</a></body></html>",
            final_url=url,
        )

    async def fake_classify_page(html, url, provider=None):
        return "listing" if "search" in url else "single_job"

    monkeypatch.setattr(url_verification, "fetch_detailed", fake_fetch_detailed)
    monkeypatch.setattr(url_verification, "classify_page", fake_classify_page)

    async def run():
        return await url_verification.verify_jobs([job])

    verified, statuses = asyncio.run(run())
    assert verified == [job]
    assert job.url == "https://boards.greenhouse.io/stripe/jobs/123"
    assert job.url_verification_status == "redirected_to_not_specific_page_original;verified_canonical_or_main_url"
    assert statuses == {job.url_verification_status: 1}


def test_verify_prefers_company_domain_when_specific(monkeypatch):
    job = Job(
        title="Engineer",
        company="Company",
        url="https://boards.greenhouse.io/company/jobs/123",
        original_url="https://company.com/jobs/engineer-123",
        source="greenhouse.io/company",
    )

    async def fake_fetch_detailed(url, timeout=30, cache_dir="./.cache"):
        return FetchResult(
            url=url,
            status="ok",
            html="<html><body><h1>Engineer</h1><a href=/apply>Apply now</a></body></html>",
            final_url=url,
        )

    async def fake_classify_page(html, url, provider=None):
        return "single_job"

    monkeypatch.setattr(url_verification, "fetch_detailed", fake_fetch_detailed)
    monkeypatch.setattr(url_verification, "classify_page", fake_classify_page)

    verified, _ = asyncio.run(url_verification.verify_jobs([job]))
    assert verified == [job]
    assert job.url == "https://company.com/jobs/engineer-123"
    assert job.url_verification_status == "verified_company_domain"


def test_verify_drops_closed_page(monkeypatch):
    job = Job(title="Engineer", company="Company", url="u", source="s")

    async def fake_fetch_detailed(url, timeout=30, cache_dir="./.cache"):
        return FetchResult(
            url=url,
            status="ok",
            html="<html><body>This job is no longer available</body></html>",
            final_url=url,
        )

    monkeypatch.setattr(url_verification, "fetch_detailed", fake_fetch_detailed)
    verified, statuses = asyncio.run(url_verification.verify_jobs([job]))
    assert verified == []
    assert statuses == {"closed_or_expired;dropped_unverified_url": 1}