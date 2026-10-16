# JobPilot

**Open source, self-hosted AI job finder.** Upload your CV, choose your preferences, get the best-matching jobs from around the world. Free, private — bring your own AI key.

Backend requires **Python 3.13.x**.

## How it works (7-step pipeline)

1. Upload your CV (PDF/DOCX) and set preferences (work mode, employment type, country or worldwide).
2. The AI reads your CV and builds a structured profile.
3. It generates search queries from your profile + preferences.
4. It discovers jobs via web search and fast job sources.
5. It fetches each job page and extracts structured data (JSON-LD first, LLM fallback).
6. It normalizes, filters, and matches jobs to your profile via embeddings + an LLM pass.
7. Results are shown in three tiers — all best jobs, top matches, strong fit (90%+).

## Quick start

```bash
git clone https://github.com/rh0kzy/jobpilot.git
cd jobpilot
cp .env.example .env
# add your AI provider key to .env
docker compose up --build
```

Then open http://localhost:3000.

## Privacy

Your CV is processed locally and not stored by default (in-memory for MVP). It is only sent to the AI provider you choose. Use Ollama for a fully local mode.

## Supported sources

Planned sources include Remotive, Arbeitnow, Remote OK, and public Greenhouse/Lever/Ashby boards, plus web search. LinkedIn, Indeed and Glassdoor are **not** scraped. See `docs/sources-and-terms.md`.

## Roadmap

See `ROADMAP.md`. Auto-apply is intentionally out of scope; a human stays in the loop via the Apply button.

## Contributing

See `CONTRIBUTING.md`.

## License

MIT — see `LICENSE`.