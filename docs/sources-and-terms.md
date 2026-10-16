# Sources and terms

## Compliance rules (all sources)
- Respect robots.txt and per-domain rate limits.
- Blocklist is enforced: LinkedIn, Indeed, Glassdoor are never scraped.
- Keep source attribution and original links.
- Never scrape login-required pages; never auto-apply.
- Read each platform's official documentation and terms before using an endpoint.

## Sources
- Remotive: attribution and link back required, low fetch frequency (~4/day), do not repost to third-party boards.
- Arbeitnow and other open feeds: use lightly, link back.
- Remote OK: public API, link back, respect rate limits.
- Jobicy: public API, link back, respect rate limits.
- Greenhouse, Lever, Ashby public boards and posting endpoints: public endpoints, respect crawl delay. ATS-specific postings are fetched from their documented public posting endpoints when available, otherwise fall back to page extraction.
- Web search: respect robots.txt and per-domain rate limits; results cached 24 hours; capped per run (default 10 queries).

## Not scraped
- LinkedIn, Indeed, Glassdoor.

## Listing expansion
- Only on allowed sites. Depth 1, configurable cap per page (default 15).
- Sites whose robots.txt/terms disallow listing scraping are skipped and recorded here.
