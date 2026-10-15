#!/usr/bin/env python3
"""Developer command: run the full Phase 1 pipeline from a CV file."""

import argparse
import asyncio
import time
from collections import Counter
from pathlib import Path

from app.connectors import arbeitnow, greenhouse, remoteok, remotive
from app.core.models import EmploymentType, Preferences, Profile, WorkMode
from app.cv.parser import extract_text
from app.cv.profile_extractor import extract_profile
from app.discovery.fetcher import fetch_detailed
from app.discovery.query_generator import generate_queries, target_terms
from app.discovery.search import get_search_provider
from app.extraction.classification import classify_page, extract_job_links
from app.extraction.extractor import _from_jsonld, extract_jobs
from app.filters.liveness import is_live
from app.normalize.normalizer import dedupe, normalize_job
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
    p.add_argument("--all", action="store_true", help="print all final jobs, not top 10")
    return p.parse_args()


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
    exclude_terms: list[str] | None = None,
):
    started = time.monotonic()
    search = get_search_provider()
    queries = generate_queries(
        profile, prefs, seniority_override=None, exclude_terms=exclude_terms
    )
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
    fetch_failures: list[tuple[str, str]] = []
    closed_failures: list[str] = []
    jobs: list = []
    jsonld_calls = 0

    async def process_single_page(url: str, html: str, count_classification: bool) -> None:
        nonlocal jsonld_calls
        if url in visited or not html or not is_live(html):
            if url not in closed_failures and not is_live(html):
                closed_failures.append(url)
            return
        visited.add(url)
        if count_classification:
            classification_counts["single_job"] += 1
        try:
            jsonld_jobs = _from_jsonld(html, url)
            if jsonld_jobs:
                jsonld_calls += 1
                extraction_counts["jsonld"] += len(jsonld_jobs)
                jobs.extend(jsonld_jobs)
                return
            extracted = await extract_jobs(html, url, provider)
            if extracted:
                extraction_counts["llm_fallback"] += len(extracted)
                jobs.extend(extracted)
        except Exception as exc:  # noqa: BLE001
            print(f"extract failed {url}: {exc}")

    async def visit(url: str, depth: int, *, count_page: bool) -> None:
        if url in visited:
            return
        result = await fetch_detailed(url, cache_dir=cache_dir, timeout=timeout)
        fetch_counts[result.status] += 1
        if result.html is None:
            fetch_failures.append((url, result.status))
            return
        page_type = await classify_page(result.html, url, provider)
        if count_page:
            classification_counts[page_type] += 1
        if page_type == "single_job":
            await process_single_page(url, result.html, count_classification=False)
        elif page_type == "listing" and depth < 1:
            links = extract_job_links(result.html, url, limit=listing_limit)
            for child in links[:child_limit]:
                await visit(child, depth + 1, count_page=True)

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
    unique = dedupe(normalized)
    elapsed = time.monotonic() - started
    return {
        "queries": queries,
        "candidate_urls": candidate_urls,
        "unique_jobs": unique,
        "fetch_counts": fetch_counts,
        "classification_counts": classification_counts,
        "extraction_counts": extraction_counts,
        "fetch_failures": fetch_failures,
        "closed_removed": closed_failures,
        "search_calls": search_calls,
        "elapsed": elapsed,
        "jsonld_calls": jsonld_calls,
    }


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
    )
    ai_calls_final = ai_calls

    print("\n[fetch] urls:", ", ".join(f"{status}={count}" for status, count in sorted(result["fetch_counts"].items())))
    print("[fetch] failures:", result["fetch_failures"])
    print(
        f"[fetch] candidate_urls={len(result['candidate_urls'])} "
        f"pages_fetched={sum(result['fetch_counts'].values())}"
    )
    print("[classification]", dict(result["classification_counts"]))
    print("[extraction]", dict(result["extraction_counts"]))
    print("[queries]")
    for query in result["queries"]:
        print(f"  - {query}")
    print("[jobs] extracted:", sum(result["extraction_counts"].values()))
    print("[jobs] connectors:", Counter(job.source for job in result["unique_jobs"]))
    print("[jobs] after dedupe:", len(result["unique_jobs"]))
    print(f"[calls] search_calls={result['search_calls']} ai_calls={ai_calls_final} elapsed={result['elapsed']:.1f}s")

    show = result["unique_jobs"] if args.all else result["unique_jobs"][:10]
    for job in show:
        print(
            f"{job.title} | {job.company} | {job.source} | {job.url} | "
            f"posted={job.posted_date} | {job.employment_type} | {job.work_mode} | {job.country}"
        )
    if not args.all:
        print(f"\nTotal: {len(result['unique_jobs'])} (showing top {len(show)})")
    else:
        print(f"\nTotal: {len(result['unique_jobs'])}")

if __name__ == "__main__":
    asyncio.run(main())