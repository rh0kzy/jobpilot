"""Greenhouse public boards connector (board tokens from a curated file)."""

from datetime import datetime
from pathlib import Path

import httpx

from app.core.models import Job


def _load_board_tokens() -> list[str]:
    path = Path(__file__).with_name("greenhouse_boards.txt")
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def fetch_jobs(limit: int = 50) -> list[Job]:
    jobs: list[Job] = []
    tokens = _load_board_tokens()
    for token in tokens:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
            resp.raise_for_status()
        except Exception:  # noqa: BLE001, S112
            continue
        data = resp.json()
        # company name via board endpoint (best effort)
        company = token
        for item in data.get("jobs", []):
            if len(jobs) >= limit:
                break
            updated = item.get("updated_at")
            try:
                posted = datetime.fromisoformat(updated).date() if updated else None
            except Exception:  # noqa: BLE001
                posted = None
            jobs.append(
                Job(
                    title=item.get("title", ""),
                    company=company,
                    url=item.get("absolute_url", ""),
                    source=f"greenhouse.io/{token}",
                    posted_date=posted,
                    page_text=item.get("content", ""),
                )
            )
    return jobs
