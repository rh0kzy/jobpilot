# JobPilot — Project Setup Instructions for the AI Agent

> **Working name:** JobPilot (replace everywhere if the name changes)
> **Goal of this file:** Make the AI agent install the stack, create the GitHub repository (via the GitHub MCP), and organize the whole project structure **before any application code is written**.

---

## 0. Rules for the agent (read first)

1. **Do NOT write application logic.** Only scaffolding: folders, config files, package manifests, placeholder README files, Docker setup, CI, and GitHub repo setup.
2. Work **step by step**, in the order of this file. After each major section, print a short status report.
3. If something is ambiguous or a tool is missing, **stop and ask** instead of guessing.
4. Never commit secrets. Only `.env.example` is committed.
5. Use the **GitHub MCP** for everything on GitHub (repo creation, labels, issues, project board). Do not ask the user to do it manually unless the MCP lacks the capability.
6. When finished, **stop**. Do not start Phase 1 coding. Report the final structure and wait for the user.
7. If the user has a session-logging workflow configured for their projects (for example an Obsidian project hub plus per-session notes recording the agent tool and model used), follow it for this session.

---

## 1. Project overview (for context)

JobPilot is an **open source, self-hosted** tool:

1. The user clones the repo and adds **their own AI API key** in a `.env` file.
2. The user uploads a **CV** (PDF/DOCX) and chooses preferences:
   - **Work mode:** remote / hybrid / on-site
   - **Employment type:** full-time / part-time / contract / internship
   - **Country:** one, several, or worldwide
3. The AI reads the CV, **searches the web and job sources**, fetches job pages, and ranks them.
4. Results are shown in **three tiers**:
   - All best jobs
   - Top matches
   - Strong fit (90%+ fit score — a *fit score*, not a hiring probability)
5. Each result card shows: **job title, company name, source website, posted date (if known), match score, and an Apply button** that opens the original job page in a new tab.

**Privacy principle:** CV is processed locally; no CV storage by default (in-memory for MVP).

---

## 2. Decisions already made

| Decision | Value |
|---|---|
| Name | JobPilot (placeholder) |
| License | MIT |
| Repo layout | Single monorepo |
| Build order | Backend pipeline first, UI second |
| Storage (MVP) | In-memory + local cache file |
| Storage (v1.1) | SQLite (saved profile, seen jobs, "new since last visit") |
| AI layer | Provider-agnostic (Mistral, Gemini, Groq, OpenAI, Ollama) |
| Job discovery | Hybrid: web search + page fetching as the main engine, plus fast sources (Remotive, Arbeitnow, Remote OK, Greenhouse/Lever/Ashby boards) |
| Auto-apply | **Out of scope** (human stays in the loop via the Apply button) |

---

## 3. Stack to install

### 3.1 Prerequisites (verify, install if missing)

- Git
- Docker and Docker Compose
- Node.js (current LTS) and a package manager (pnpm preferred, npm acceptable)
- Python 3.11 or newer
- A Python environment tool (uv preferred, venv acceptable)

Verify each with its version command and report the versions found.

### 3.2 Frontend — `apps/web`

- Next.js (App Router) with TypeScript
- Tailwind CSS
- shadcn/ui
- Lucide icons
- ESLint and Prettier

### 3.3 Backend — `apps/api`

- Python with **FastAPI** and Uvicorn
- Pydantic (data models and settings)
- python-multipart (file upload)
- httpx (async HTTP client)
- pytest and pytest-asyncio (tests)
- Ruff (lint and format)

### 3.4 CV parsing

- PyMuPDF (PDF text extraction)
- pdfplumber (fallback for tables and layout)
- python-docx (DOCX)
- Optional OCR fallback for scanned PDFs: pytesseract (document as optional, do not require)

### 3.5 Web discovery and page fetching

- trafilatura (clean main-text extraction)
- extruct (extract schema.org **JobPosting** JSON-LD structured data — try this **before** using the LLM)
- selectolax or BeautifulSoup (HTML parsing)
- Playwright (only for JavaScript-heavy pages; make it an optional extra, not required for basic run)
- A search provider integration, configurable through `.env`:
  - Default: one search API with a free tier (Tavily or Brave Search)
  - Advanced option: self-hosted SearXNG
- robots.txt checking and per-domain rate limiting must be planned for (create placeholder module and docs only)

### 3.6 Matching

- sentence-transformers with a **multilingual** model (Arabic, French, English support)
- ChromaDB (embedded) for the vector store
- NumPy

### 3.7 AI provider layer

Create a placeholder abstraction (docs and empty module only) designed so that **one interface** supports:

- Mistral
- Google Gemini
- Groq
- OpenAI
- Ollama (local)

Add the official SDKs (or use httpx) as **optional dependency groups**, so users install only what they use.

### 3.8 Packaging and DevOps

- Docker Compose (services: `web`, `api`)
- Dockerfiles for `web` and `api`
- GitHub Actions: lint, test, build
- Pre-commit hooks (Ruff, Prettier, basic file checks)

---

## 4. Target directory structure

Create exactly this structure. Put a short `README.md` (one or two lines describing the folder's purpose) in each folder, or a `.gitkeep` where a README is not useful.

```
jobpilot/
├── apps/
│   ├── web/                      # Next.js frontend
│   └── api/                      # FastAPI backend
│       ├── app/
│       │   ├── main.py           # entry point (minimal health check only)
│       │   ├── core/             # settings, logging, errors
│       │   ├── cv/               # CV parsing module
│       │   ├── discovery/        # query generation, web search, page fetching
│       │   ├── extraction/       # JSON-LD first, LLM fallback
│       │   ├── connectors/       # fast sources, one folder/file per source
│       │   │   └── base.py       # shared connector interface (placeholder)
│       │   ├── normalize/        # job normalizer: mode, type, country, eligibility
│       │   ├── filters/          # hard filters and remote eligibility logic
│       │   ├── matching/         # embeddings, scoring, tiers
│       │   ├── providers/        # AI provider abstraction + implementations
│       │   ├── cache/            # local cache handling
│       │   └── api/              # routes (upload, search, results)
│       ├── tests/
│       │   └── fixtures/         # sample CVs and sample job pages (anonymized)
│       └── pyproject.toml
├── docs/
│   ├── architecture.md
│   ├── how-to-add-a-connector.md
│   ├── provider-setup.md         # free options: Gemini, Groq, Ollama
│   ├── scoring-model.md
│   ├── sources-and-terms.md      # allowed sources, attribution, rate limits
│   └── privacy.md
├── scripts/                      # dev helper scripts
├── .github/
│   ├── workflows/
│   │   ├── ci.yml
│   │   └── docker-build.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── new_connector.md
│   └── PULL_REQUEST_TEMPLATE.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .editorconfig
├── .pre-commit-config.yaml
├── LICENSE                       # MIT
├── README.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── ROADMAP.md
```

---

## 5. Environment variables

Create `.env.example` with **placeholders only**, grouped and commented:

- **AI provider:** selected provider name, model name, API key variable per provider, Ollama base URL
- **Search provider:** selected provider, API key
- **Optional source keys:** Adzuna app id and key, Jooble key (clearly marked optional)
- **App settings:** cache folder path, cache refresh interval, default country list, request timeout, per-domain rate limit
- **Frontend:** API base URL

Include a **first-run check** requirement in the docs: the app must tell the user clearly when the AI key is missing or invalid (document this requirement only, do not implement).

---

## 6. GitHub setup (use the GitHub MCP)

1. **Create the repository** `jobpilot` (public) under the user's account.
   - Description: "Open source, self-hosted AI job finder: upload your CV, get the best-matching jobs from around the world. Free, private, bring your own AI key."
   - Initialize with the MIT license.
   - Topics: `ai`, `job-search`, `cv`, `resume`, `open-source`, `fastapi`, `nextjs`, `llm`, `rag`, `self-hosted`
2. **Default branch:** `main`.
3. **Branch strategy:** feature branches, pull requests into `main`. Enable branch protection on `main` if the MCP permits (require CI to pass).
4. **Labels:** create at least:
   - `good first issue`, `help wanted`, `bug`, `enhancement`
   - `connector`, `ai-provider`, `matching`, `frontend`, `backend`, `docs`
   - `phase-0`, `phase-1`, `phase-2`, `phase-3`, `phase-4`
5. **Project board:** columns Backlog, Ready, In progress, Review, Done.
6. **Initial issues** (create them, label them, and add to the board):

   **Phase 0 — Setup**
   - Repo scaffolding and CI
   - Docker Compose for web and api
   - `.env` handling and first-run key check

   **Phase 1 — Core pipeline (backend)**
   - CV parser: file in, structured profile out
   - AI provider layer with two providers working
   - Query generation from profile and preferences
   - Web search integration
   - Page fetching with robots.txt respect and rate limiting
   - JSON-LD extraction with LLM fallback
   - Connector interface plus first connectors (Remotive, Arbeitnow, Remote OK, Greenhouse boards)
   - Job normalizer (work mode, employment type, country, allowed countries)
   - Liveness check and deduplication

   **Phase 2 — Matching**
   - Embeddings and similarity search
   - Hard filters including remote eligibility
   - Score breakdown and tier assignment (all, top matches, strong fit 90%+)
   - Evaluation set of anonymized CVs and real jobs

   **Phase 3 — Interface**
   - Upload page with preferences form (work mode, employment type, country or worldwide)
   - Result cards: title, company, source site, posted date, score, Apply button
   - Loading progress, error and empty states
   - Editable filters on the results page

   **Phase 4 — Launch**
   - README with demo GIF and four-command quick start
   - Additional connectors
   - Good-first-issue set for contributors

   **Backlog (post-MVP, do not start)**
   - Saved profile and "new since last visit" (SQLite)
   - Application tracker
   - Tailored CV and cover letter
   - Skill gap view
   - Scam and fake-job warning
   - Daily digest by email or Telegram
   - Browser extension
   - Community-maintained company career page list and country packs

---

## 7. Documentation files to draft (short, real content)

Write concise but real first versions of:

- **README.md:** name, tagline, what it does, how it works (the 7-step pipeline), planned quick start (clone, copy `.env.example`, add key, run Docker Compose), supported sources and honest coverage note, privacy section, roadmap link, contributing link, license
- **CONTRIBUTING.md:** how to set up, branch and PR rules, how to add a connector, code style
- **docs/architecture.md:** pipeline diagram description (CV → profile → queries → discovery → fetch → extract → normalize → filter → match → tiers → cards)
- **docs/sources-and-terms.md:** list of planned sources and their rules:
  - Remotive: attribution and link back required, low fetch frequency (about four per day), do not repost to third-party boards
  - Arbeitnow and other open feeds: use lightly, link back
  - Greenhouse, Lever, Ashby public boards: public endpoints, respect crawl delay
  - LinkedIn, Indeed, Glassdoor: **not scraped**
  - Add a note: read each source's current terms before building its connector
- **docs/privacy.md:** CV handled locally, not stored by default, only sent to the AI provider the user chose, optional local mode with Ollama
- **docs/scoring-model.md:** components of the fit score (required skills, nice-to-have skills, experience, seniority, languages, eligibility, LLM judgment pass) and the note that the score is **not** a hiring probability

---

## 8. Quality gates before reporting done

The agent must verify and report:

- [ ] Repository exists on GitHub with the MIT license and correct topics
- [ ] All directories from section 4 exist and are committed to `main`
- [ ] `docker compose config` validates
- [ ] Frontend dependencies install without errors; the dev server starts to the default page
- [ ] Backend dependencies install without errors; the health check endpoint responds
- [ ] CI workflow file is valid and runs lint and test steps (even if tests are empty)
- [ ] `.env.example` exists and `.env` is git-ignored
- [ ] Labels, board, and initial issues created
- [ ] Docs files exist with real first-version content

---

## 9. Final report format

When done, print:

1. The final directory tree
2. The installed versions of each tool
3. The repository URL
4. A table of created labels and issues (title, label, phase)
5. Anything skipped or needing user action, with the reason
6. A clear statement: **"Setup complete. Waiting for instructions to start Phase 1."**

Then **stop**.
