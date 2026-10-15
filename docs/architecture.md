# Architecture

Pipeline:

CV file -> PDF/DOCX parser -> structured profile -> query generation (profile + preferences) -> discovery (web search + fast connectors) -> page fetch (robots.txt + rate limit) -> page classification (`single_job`, `listing`, `other`) -> extraction (JobPosting JSON-LD first, LLM fallback) -> normalizer (work mode, employment type, country) -> filters (hard filters, remote eligibility) -> matching (embeddings + score breakdown) -> tier assignment (all best, top matches, strong fit 90%+) -> result cards (title, company, source, posted date, score, Apply button).

Listing pages are never emitted as job records. On listing pages, the pipeline extracts depth-1 job links, then fetches and extracts only those individual postings.
