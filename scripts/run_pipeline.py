#!/usr/bin/env python3
"""Developer command: run the full Phase 1 pipeline from a CV file."""

import argparse
import asyncio
import time
from collections import Counter
from pathlib import Path

from app.connectors import arbeitnow, greenhouse, remoteok, remotive
from app.core.models import EmploymentType, Job, Preferences, Profile, WorkMode
from app.cv.parser import extract_text
from app.cv.profile_extractor import extract_profile
from app.discovery.fetcher import fetch_detailed
from app.discovery.query_generator import generate_queries_with_metadata, target_terms
from app.discovery.search import get_search_provider
from app.extraction.classification import classify_page, extract_job_links
from app.extraction.extractor import _from_jsonld
from app.extraction.page_text import (
    has_meaningful_job_text,
    html_to_text,
    needs_js_render,
    render_with_playwright,
)
from app.extraction.url_verification import verify_jobs
from app.filters.liveness import is_live
from app.normalize.normalizer import dedupe, mark_freshness, normalize_job
from app.providers.factory import get_provider


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--cv", required=True)
    p.add_argument("--work-mode", action="append", default=[])
    p.add_argument("--employment-type", action="append", default=[])
    p.add_argument("--country", action="append", default=[])
    p.add_argument("--seniority", default=None)
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--search-limit", type=int, default=3)
    p.add_argument("--listing-limit", type=int, default=20)
    p.add_argument("--child-limit", type=int, default=20)
    p.add_argument("--freshness-days", type=int, default=60)
    p.add_argument("--llm-max-chars", type=int, default=8000)
    p.add_argument("--no-playwright", action="store_true", help="do not try optional JS rendering")
    p.add_argument("--all", action="store_true", help="print all final jobs, not top 10")
    return p.parse_args()


def _display(value) -> str:
    return "unspecified" if value is None or str(value).strip() == "" else str(value)


async def run_pipeline(
    profile: Profile,
    prefs: Preferences,
    provider,
    *,
    search_limit: int,
    listing_limit: int,
    child_limit: int,
    cache_dir: str,
    timeout: int,
    exclude_terms: list[str] | None,
    freshness_days: int,
    llm_max_chars: int,
    use_playwright: bool,
):
    started = time.monotonic()
    search = get_search_provider()
    query_meta = generate_queries_with_metadata(
        profile, prefs, seniority_override=None, exclude_terms=exclude_terms
    )
    queries = [q.text for q in query_meta]
    urls: list[str] = []
    search_calls = 0
    for query in queries:
        try:
            search_calls += 1
            urls.extend(await search.search(query, limit=search_limit))
        except Exception as exc:  # noqa: BLE001
            print(f"search failed for {query!r}: {exc}")

    candidate_urls = list(dict.fromkeys(urls))
    visited: set[str] = set()
    fetch_counts: Counter[str] = Counter()
    classification_counts: Counter[str] = Counter()
    extraction_counts: Counter[str] = Counter()
    skip_reason_counts: Counter[str] = Counter()
    fetch_failures: list[tuple[str, str]] = []
    playwright_messages: list[str] = []
    jobs: list[Job] = []

    def attach_fetch(job: Job, final_url: str) -> None:
        job.original_url = job.original_url or job.url
        job.url = final_url or job.url
        job.url_verified = True
        job.url_verification_status = "verified_from_fetched_page"

    async def process_single_page(url: str, html: str, final_url: str) -> None:
        if url in visited:
            return
        visited.add(url)
        if not is_live(html):
            skip_reason_counts["closed_or_expired"] += 1
            return

        jsonld_jobs = _from_jsonld(html, url)
        if jsonld_jobs:
            extraction_counts["jsonld"] += len(jsonld_jobs)
            for job in jsonld_jobs:
                attach_fetch(job, final_url)
                jobs.append(job)
            return

        page_html = html
        text = html_to_text(page_html)
        if use_playwright and needs_js_render(page_html, text):
            rendered = await render_with_playwright(url)
            if rendered.get("html"):
                page_html = rendered["html"]
                text = html_to_text(page_html)
                rendered_jobs = _from_jsonld(page_html, url)
                method = "jsonld"
                if not rendered_jobs and has_meaningful_job_text(page_html, text):
                    rendered_jobs = await extract_jobs_with_provider(
                        page_html, url, provider, llm_max_chars
                    )
                    method = "llm_fallback"
                if rendered_jobs:
                    extraction_counts[method] += len(rendered_jobs)
                    for job in rendered_jobs:
                        attach_fetch(job, final_url)
                        jobs.append(job)
                    return
            else:
                reason = str(rendered.get("error") or "playwright_unavailable")
                skip_reason_counts[f"javascript_rendered_no_content_{reason}"] += 1
                if reason not in playwright_messages:
                    playwright_messages.append(reason)
                return

        if not has_meaningful_job_text(page_html, text):
            skip_reason_counts["no_meaningful_job_text"] += 1
            return

        extracted = await extract_jobs_with_provider(page_html, url, provider, llm_max_chars)
        if extracted:
            extraction_counts["llm_fallback"] += len(extracted)
            for job in extracted:
                attach_fetch(job, final_url)
                jobs.append(job)
        else:
            skip_reason_counts["extraction_returned_empty"] += 1

    async def visit(url: str, depth: int, *, count_page: bool) -> None:
        if url in visited:
            return
        result = await fetch_detailed(url, cache_dir=cache_dir, timeout=timeout)
        fetch_counts[result.status] += 1
        if result.html is None:
            if count_page:
                skip_reason_counts[result.status] += 1
            fetch_failures.append((url, result.status))
            return

        page_type = await classify_page(result.html, url, provider)
        if count_page:
            classification_counts[page_type] += 1
        if page_type == "single_job":
            await process_single_page(url, result.html, result.final_url or url)
        elif page_type == "listing" and depth < 1:
            links = extract_job_links(result.html, url, limit=listing_limit)
            for child in links[:child_limit]:
                await visit(child, depth + 1, count_page=True)
        elif page_type == "listing":
            visited.add(url)

    for url in candidate_urls:
        await visit(url, 0, count_page=True)

    target_roles = target_terms(profile)
    lower_roles = " ".join(target_roles).lower()
    connector_inputs = {
        "remotive": {
            "category": "software-dev" if ("developer" in lower_roles or "engineer" in lower_roles) else None,
        },
        "arbeitnow": {"search": target_roles[0] if target_roles else None},
        "remoteok": {"tag": profile.skills[0].lower() if profile.skills else None},
        "greenhouse": {},
    }
    for connector in (remotive, arbeitnow, remoteok, greenhouse):
        try:
            fetched = await connector.fetch_jobs(limit=50, target_roles=target_roles, **connector_inputs[connector.__name__.split(".")[-1]])
            jobs.extend(fetched)
        except Exception as exc:  # noqa: BLE001
            print(f"connector failed {connector.__name__}: {exc}")

    normalized = [normalize_job(job) for job in jobs]
    normalized, url_verification_statuses = await verify_jobs(
        normalized, cache_dir=cache_dir, timeout=timeout
    )
    unique = dedupe(normalized)
    marked = mark_freshness(unique, max_age_days=freshness_days)
    freshness_counts = Counter(job.freshness_status for job in marked)
    url_status_counts = Counter(url_verification_statuses)
    elapsed = time.monotonic() - started

    return {
        "query_meta": query_meta,
        "candidate_urls": candidate_urls,
        "unique_jobs": marked,
        "fetch_counts": fetch_counts,
        "classification_counts": classification_counts,
        "extraction_counts": extraction_counts,
        "skip_reason_counts": skip_reason_counts,
        "fetch_failures": fetch_failures,
        "url_status_counts": url_status_counts,
        "freshness_counts": freshness_counts,
        "search_calls": search_calls,
        "playwright_messages": playwright_messages,
        "elapsed": elapsed,
    }


async def extract_jobs_with_provider(html: str, url: str, provider, max_chars: int) -> list[Job]:
    from app.extraction.extractor import extract_jobs

    return await extract_jobs(html, url, provider, max_chars=max_chars)


async def main() -> None:
    args = parse_args()
    text = extract_text(Path(args.cv))
    provider = get_provider()
    raw_complete = provider.complete
    ai_calls = 0

    async def counted_complete(prompt: str, system: str | None = None) -> str:
        nonlocal ai_calls
        ai_calls += 1
        return await raw_complete(prompt, system)

    provider.complete = counted_complete

    profile = await extract_profile(text, provider)
    prefs = Preferences(
        work_modes=[WorkMode(m) for m in args.work_mode] if args.work_mode else [],
        employment_types=[EmploymentType(e) for e in args.employment_type] if args.employment_type else [],
        countries=args.country or ["WORLDWIDE"],
        seniority_override=args.seniority,
    )
    result = await run_pipeline(
        profile,
        prefs,
        provider,
        search_limit=args.search_limit,
        listing_limit=args.listing_limit,
        child_limit=args.child_limit,
        cache_dir="./.cache",
        timeout=30,
        exclude_terms=args.exclude,
        freshness_days=args.freshness_days,
        llm_max_chars=args.llm_max_chars,
        use_playwright=not args.no_playwright,
    )

    print("\n[fetch] urls:", ", ".join(f"{status}={count}" for status, count in sorted(result["fetch_counts"].items())))
    print("[fetch] failures:", result["fetch_failures"])
    print(
        f"[fetch] candidate_urls={len(result['candidate_urls'])} "
        f"pages_fetched={sum(result['fetch_counts'].values())}"
    )
    print("[classification]", dict(result["classification_counts"]))
    print("[extraction]", dict(result["extraction_counts"]))
    print("[skipped_single_pages]", dict(result["skip_reason_counts"]))
    print("[url_verification]", result["url_status_counts"])
    print("[freshness]", result["freshness_counts"])
    print(
        f"[jobs] extracted={sum(result['extraction_counts'].values())} "
        f"after_dedupe={len(result['unique_jobs'])}"
    )
    print("[jobs] connectors:", Counter(job.source for job in result["unique_jobs"]))
    print("[queries]")
    for query in result["query_meta"]:
        print(f"  - {query.kind}: {query.text}")
    if result["playwright_messages"]:
        print("[playwright] ", ", ".join(sorted(set(result["playwright_messages"]))))
    print(f"[calls] search_calls={result['search_calls']} ai_calls={ai_calls} elapsed={result['elapsed']:.1f}s")

    show = result["unique_jobs"] if args.all else result["unique_jobs"][:10]
    for job in show:
        print(
            f"{job.title} | {job.company} | {job.source} | {job.url} | "
            f"posted={_display(job.posted_date)} | {_display(job.work_mode)} | "
            f"{_display(job.employment_type)} | location={_display(job.location)} | "
            f"country={_display(job.country)} | remote_elig={_display(job.remote_eligibility)} | "
            f"seniority={_display(job.seniority)} | freshness={_display(job.freshness_status)} | "
            f"verified={_display(job.url_verification_status)}"
        )
    if not args.all:
        print(f"\nTotal: {len(result['unique_jobs'])} (showing top {len(show)})")
    else:
        print(f"\nTotal: {len(result['unique_jobs'])}")


if __name__ == "__main__":
    asyncio.run(main())
