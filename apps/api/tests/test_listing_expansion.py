from pathlib import Path

from app.extraction.classification import classify_page, extract_job_links_detailed


def test_listing_expansion_returns_posting_links():
    html = Path("tests/fixtures/classification_listing.html").read_text()
    links, reason = extract_job_links_detailed(html, "https://example.com/jobs/full-stack-developer", limit=10)
    assert reason == "ok"
    assert len(links) == 6
    assert all("/remote-jobs/" in link for link in links)


async def test_listing_links_classify_as_single_job():
    html = Path("tests/fixtures/classification_single.html").read_text()
    assert await classify_page(html, "https://example.com/jobs/123456") == "single_job"
