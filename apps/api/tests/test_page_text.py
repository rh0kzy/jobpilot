from app.extraction.extractor import extract_jobs
from app.extraction.page_text import (
    has_meaningful_job_text,
    html_to_text,
    needs_js_render,
)


class CountingProvider:
    def __init__(self):
        self.calls = 0

    async def complete(self, prompt, system=None):
        self.calls += 1
        return '{"jobs":[]}'


def test_html_to_text_removes_scripts_and_tags():
    html = "<html><head><script>var x=1</script></head><body><h1>Backend Engineer</h1><p>Apply now</p></body></html>"
    text = html_to_text(html)
    assert "var x" not in text
    assert "Backend Engineer" in text


def test_meaningful_job_text_requires_keyword_and_length():
    assert has_meaningful_job_text(
        "<html><body>" + "Apply to this software engineer role. " * 8 + "</body></html>"
    )
    assert not has_meaningful_job_text("<html><body>Loading application shell</body></html>")


def test_needs_js_render_when_shell_is_empty():
    assert needs_js_render('<html><body><div id="root"></div></body></html>')
    assert not needs_js_render("<html><body>" + "Apply now to this long job posting " * 20 + "</body></html>")


async def test_llm_not_called_for_unmeaningful_page():
    provider = CountingProvider()
    jobs = await extract_jobs(
        "<html><body><div id='root'></div></body></html>", "https://example.com/jobs/1", provider
    )
    assert jobs == []
    assert provider.calls == 0


async def test_llm_called_with_meaningful_page_and_fields():
    html = (
        "<html><body><h1>Senior Backend Engineer</h1><p>Apply now. "
        + "Build APIs, work with requirements and systems. " * 12
        + "</p></body></html>"
    )
    text = html_to_text(html)

    class StubProvider:
        async def complete(self, prompt, system=None):
            return '{"jobs":[{"title":"Senior Backend Engineer","company":"Acme","url":"' + "x" + '"}]}'

    jobs = await extract_jobs(html, "https://example.com/jobs/2", StubProvider())
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Backend Engineer"
    assert job.url == "https://example.com/jobs/2"
    assert job.original_url == "https://example.com/jobs/2"
    assert job.seniority is not None
    assert text