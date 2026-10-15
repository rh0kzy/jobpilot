from pathlib import Path

from app.extraction.classification import classify_page, extract_job_links


def test_extract_job_links_from_listing():
    html = Path("tests/fixtures/classification_listing.html").read_text()
    links = extract_job_links(html, "https://example.com/jobs/full-stack-developer", limit=10)
    assert len(links) == 6
    assert all(link.startswith("https://example.com/remote-jobs/") for link in links)


async def test_jsonld_single_job_is_not_listing():
    html = Path("tests/fixtures/job_jsonld.html").read_text()
    assert await classify_page(html, "https://example.com/jobs/1") == "single_job"


async def test_listing_page_is_classified_listing():
    html = Path("tests/fixtures/classification_listing.html").read_text()
    assert await classify_page(html, "https://example.com/jobs/full-stack-developer") == "listing"


async def test_apply_page_is_single_job():
    html = Path("tests/fixtures/classification_single.html").read_text()
    assert await classify_page(html, "https://example.com/jobs/123456") == "single_job"


async def test_other_page():
    html = Path("tests/fixtures/classification_other.html").read_text()
    assert await classify_page(html, "https://example.com/about/policy") == "other"


async def test_provider_tie_breaker():
    class Provider:
        async def complete(self, prompt, system=None):
            return "single_job"

    html = Path("tests/fixtures/classification_other.html").read_text()
    assert await classify_page(html, "https://example.com/about/unknown", provider=Provider()) == "single_job"
