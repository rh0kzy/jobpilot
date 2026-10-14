# Contributing to JobPilot

## Setup

- Backend: `cd apps/api && uv venv && uv pip install -e ".[dev]"`
- Frontend: `cd apps/web && pnpm install`
- Run backend: `uvicorn app.main:app --reload`
- Run frontend: `pnpm dev`

## Branch and PR rules

- Feature branches from `main`, one concern per PR.
- Run tests and linters before opening a PR.
- Follow the PR template.

## How to add a connector

See `docs/how-to-add-a-connector.md`.

## Code style

- Python: Ruff (lint + format).
- Frontend: ESLint + Prettier (shadcn/ui conventions).