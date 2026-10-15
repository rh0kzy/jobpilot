#!/usr/bin/env python3
"""Developer command: run the full Phase 1 pipeline from a CV file."""

import argparse
import asyncio
from pathlib import Path

from app.core.models import Preferences, WorkMode, EmploymentType
from app.cv.parser import extract_text
from app.cv.profile_extractor import extract_profile
from app.discovery.fetcher import fetch
from app.discovery.query_generator import generate_queries
from app.discovery.search import get_search_provider
from app.extraction.extractor import extract_jobs
from app.filters.liveness import is_live
from app.normalize.normalizer import dedupe, normalize_job
from app.providers.factory import get_provider
from app.connectors import remotive, arbeitnow, remoteok, greenhouse


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--cv", required=True)
    p.add_argument("--work-mode", action="append", default=[])
    p.add_argument("--employment-type", action="append", default=[])
    p.add_argument("--country", action="append", default=[])
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    text = extract_text(Path(args.cv))
    provider = get_provider()
    profile = await extract_profile(text, provider)
    prefs = Preferences(
        work_modes=[WorkMode(m) for m in args.work_mode] if args.work_mode else [],
        employment_types=[EmploymentType(e) for e in args.employment_type] if args.employment_type else [],
        countries=args.country or ["WORLDWIDE"],
    )
    queries = generate_queries(profile, prefs)
    search = get_search_provider()
    urls: list[str] = []
    for q in queries:
        try:
            urls.extend(await search.search(q, limit=5))
        except Exception as exc:  # noqa: BLE001
            print(f"search failed: {exc}")

    jobs = []
    for u in dict.fromkeys(urls):
        html = await fetch(u)
        if not html:
            continue
        if not is_live(html):
            continue
        try:
            jobs.extend(await extract_jobs(html, u, provider))
        except Exception as exc:  # noqa: BLE001
            print(f"extract failed {u}: {exc}")

    for connector in (remotive, arbeitnow, remoteok, greenhouse):
        try:
            jobs.extend(await connector.fetch_jobs(limit=20))
        except Exception as exc:  # noqa: BLE001
            print(f"connector failed {connector.__name__}: {exc}")

    normalized = [normalize_job(j) for j in jobs]
    unique = dedupe(normalized)
    for job in unique:
        print(
            f"{job.title} | {job.company} | {job.source} | {job.url} | "
            f"posted={job.posted_date} | {job.work_mode} | {job.employment_type} | {job.country}"
        )
    print(f"\nTotal: {len(unique)}")


if __name__ == "__main__":
    asyncio.run(main())
