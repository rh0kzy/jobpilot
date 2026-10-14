# Architecture

Pipeline:

CV file -> PDF/DOCX parser -> structured profile -> query generation (profile + preferences) -> discovery (web search + fast connectors) -> page fetch (robots.txt + rate limit) -> extraction (JSON-LD first, LLM fallback) -> normalizer (work mode, employment type, country, eligibility) -> filters (hard filters, remote eligibility) -> matching (embeddings + score breakdown) -> tier assignment (all best, top matches, strong fit 90%+) -> result cards (title, company, source, posted date, score, Apply button).