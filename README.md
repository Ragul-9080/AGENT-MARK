# Agentic Marketing Platform - Phase 1

One shared backend and dashboard for three AI marketing agents:

- **Voice agent** - outbound and inbound calls, transcripts, outcomes (Milestone 4).
- **Website & SEO agent** - Playwright crawl, rule checks, AI strategy (Milestone 3).
- **Email marketing agent** - templates, AI drafts, sends, tracking (Milestone 2).

Phase 1 status: **Milestones 0 and 1 complete, Milestone 2 email backend complete**
(console provider by default; SES behind the same adapter).

## What works today

- Email/password auth with workspaces, roles, JWT access + refresh tokens, argon2 hashing,
  auth-route rate limiting.
- Shared contact list: CRUD, search/filter/tags, E.164 normalisation, duplicate detection,
  CSV import with a dry-run error preview.
- Consent and suppression records, plus a per-contact eligibility check that every send path
  will use.
- Campaign create/schedule/start/pause/resume/stop state machine, campaign recipients.
- Append-only event timeline written by the common backend.
- Email agent backend: consent/suppression-gated sends, console + SES adapters, message
  history and provider webhooks (`EMAIL_PROVIDER=console` logs without storing PII).
- Dashboard summary, paginated lists, consistent errors, request IDs.
- Celery job infrastructure with retries, progress in the database, and a dead-letter state.
- Next.js dashboard: sign in/up, home, contacts (import + detail + consents), campaigns,
  settings, and clearly-marked placeholders for the three agent screens.

Milestone status and evidence: `docs/milestone-1-report.md`.

## Quick start with Docker

```bash
cp .env.example .env          # fill in JWT_SECRET at minimum
docker compose up --build
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health and `/health/ready`
- Voice server (stub until Milestone 4): http://localhost:8001/health

Register a workspace, then import `examples/contacts.csv` from the Contacts screen.

## Local development without Docker (free, no external services)

Prerequisites: Python 3.12+, Node 22+, PostgreSQL 16+. Redis is **not** required:
`REDIS_URL=` falls back to in-process rate limiting, and `CELERY_TASK_ALWAYS_EAGER=true`
runs queued jobs inline. Email uses the `console` provider, so nothing is sent and no
provider account is needed.

### One command

```powershell
npm run dev:local
```

This loads `.env`, checks PostgreSQL, runs `alembic upgrade head`, starts the API on
port **8010** and the dashboard on port **3000**, then opens `/login`.

- Dashboard: http://localhost:3000
- API docs: http://127.0.0.1:8010/docs
- Register first: http://localhost:3000/register

Port 8010 is used because port 8000 may already belong to another project. Change
`API_INTERNAL_URL` in `.env` (and every use of it) if you prefer another port.

### Manual start

```powershell
# 1. Environment (once)
Copy-Item .env.example .env
#    Edit .env: set DATABASE_URL to your local PostgreSQL and a JWT_SECRET.

# 2. API
cd apps\api
..\..\.venv\Scripts\alembic.exe upgrade head
..\..\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8010

# 3. Dashboard (new terminal)
#    apps\web\.env.local must contain: API_INTERNAL_URL=http://127.0.0.1:8010
npm run dev
```

Next.js only reads environment files inside `apps/web`; the root `.env` is for the API.
Keep `API_INTERNAL_URL` in both places and use `http://localhost:3000` in the browser.

## Tests and quality gates

```bash
cd apps/api
pytest --cov=app --cov-report=term-missing
ruff check .
ruff format --check .
mypy app
```
```bash
npm run lint
npm run typecheck
npm run build
```

The API test suite expects `DATABASE_URL` to point at a disposable PostgreSQL database.
Each run clears the schema and applies the Alembic migrations.

### End-to-end smoke test

With the API and dashboard running, the smoke test drives the whole flow through the dashboard
proxy the way a browser does: sign up, import 100 contacts, consent, suppression, campaign
lifecycle, page rendering, error handling and workspace isolation.

```bash
.venv\Scripts\python scripts\smoke_test.py --web http://localhost:3000 --api http://localhost:8000
```

It never calls a paid provider: no call is placed and no email is sent.

## Repository layout

```
apps/api/          FastAPI backend, SQLAlchemy models, Celery workers, Alembic
apps/voice/        WebSocket voice server (health-check stub in Phase 1 M0)
apps/web/          Next.js dashboard with a server-side API proxy
packages/shared-types/  TypeScript API types used by the dashboard
docs/              architecture, runbook, compliance
examples/          sample CSV for import
```

## Key documents

- `docs/architecture.md` - components, data model, provider research, decisions.
- `docs/runbook.md` - operation, provider checks, failure handling.
- `docs/compliance.md` - consent, suppression, calling-hours and recording controls.

## Phase 1 boundaries

Not built: paid ads, social posting, SMS/WhatsApp, automatic site changes, billing, mobile
apps. The SEO agent is read-only. The email and voice provider adapters are introduced in
their own milestones.
