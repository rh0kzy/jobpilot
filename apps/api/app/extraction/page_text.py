"""HTML-to-text helpers and optional Playwright rendering."""

import asyncio
import re
from html import unescape

_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_text(html: str) -> str:
    """Return visible text with script/style noise removed."""
    text = _SCRIPT_RE.sub(" ", html or "")
    text = unescape(text)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


_JOB_TEXT_KEYWORDS = (
    "apply",
    "job",
    "role",
    "responsibilit",
    "requirement",
    "qualification",
    "experience",
    "salary",
    "postuler",
    "emploi",
    "وظيفة",
)


def has_meaningful_job_text(html: str, text: str | None = None, min_chars: int = 240) -> bool:
    """Cheap check before spending an AI call."""
    text = text if text is not None else html_to_text(html)
    if len(text) < min_chars:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in _JOB_TEXT_KEYWORDS)


_JS_MARKERS = (
    "enable javascript",
    "please enable js",
    "javascript is required",
    "loading...",
    "__next_data__",
    'id="root"',
    'id="app"',
)


def needs_js_render(html: str, text: str | None = None, min_chars: int = 240) -> bool:
    text = text if text is not None else html_to_text(html)
    if len(text) >= min_chars:
        return False
    low = (html or "").lower()
    return any(marker in low for marker in _JS_MARKERS)


async def render_with_playwright(url: str, timeout: int = 30) -> dict[str, str | None]:
    """Render a JS page with Playwright when installed.

    Returns a dict with either ``html`` or an ``error`` reason.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception:  # noqa: BLE001
        return {"error": "playwright_not_installed"}

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(args=["--no-sandbox"])
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
                await page.wait_for_timeout(500)
                content = await page.content()
            finally:
                await browser.close()
        return {"html": content}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"playwright_error: {exc.__class__.__name__}"}


def render_with_playwright_sync(url: str, timeout: int = 30) -> dict[str, str | None]:
    """Sync helper used by offline tests and command-line debugging."""
    try:
        return asyncio.run(render_with_playwright(url, timeout=timeout))
    except RuntimeError:  # already-running loop or disabled loop
        return {"error": "event_loop_unavailable"}
