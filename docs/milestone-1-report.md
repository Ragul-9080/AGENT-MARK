# Milestone 1 report (Phase 1)

Date: 2026-10-19. Scope: Milestone 0 (foundation) and Milestone 1 (auth, contacts, consent,
campaigns, events, jobs). Milestone 2 has not started.

## Milestone 0 - done

| Requirement | Status | Evidence |
| --- | --- | --- |
| Monorepo with API, dashboard, shared types, docs, examples | Done | `apps/api`, `apps/web`, `packages/shared-types`, `docs/`, `examples/` |
| Docker Compose brings up the whole stack | Built, not executed here | `docker-compose.yml` (postgres, redis, migrate, api, worker, beat, voice, web); `docker compose config -q` passes in CI |
| CI runs lint, types, migrations, tests, web build, compose validation, secret check | Done | `.github/workflows/ci.yml` |
| Configuration via environment, template complete, no secrets committed | Done | `.env.example` covers every `Settings` field; CI job rejects committed `.env` |
| Health checks | Done | `GET /health`, `GET /health/ready`; voice stub on `:8001/health`; compose healthchecks |

## Milestone 1 - done

Acceptance was: a user signs in, imports 100 contacts, sees them, and isolation tests pass.

| Acceptance step | Status | Evidence |
| --- | --- | --- |
| Sign in / create a workspace | Done | Register + login through the dashboard BFF returns httpOnly cookies; `auth/me` works |
| Import 100 contacts | Done | CSV dry run then commit created 100 contacts; a second import created 0 and flagged 100 duplicates |
| See them | Done | `GET /contacts` returned 100; the `/contacts` page rendered them; search found a single match |
| Isolation tests pass | Done | `apps/api/tests/test_contacts.py` and friends cover cross-workspace reads; the e2e smoke test repeats it through the dashboard |

### Automated verification run in this milestone

| Check | Command | Result |
| --- | --- | --- |
| Lint | `ruff check .` (apps/api) | clean |
| Format | `ruff format --check .` | clean |
| Types | `mypy app` | clean |
| Tests | `pytest` | 69 passed, 94.5% coverage (gate 80%) |
| Migrations | `alembic upgrade head`, `alembic check` | at head, no pending operations |
| Web lint | `npm run lint` | clean |
| Web types | `npm run typecheck` | clean |
| Web build | `npm run build` | 16 routes, all dynamic, builds clean |
| End to end | `python scripts/smoke_test.py` | passed against the production standalone build |

`scripts/smoke_test.py` drives the running stack through the dashboard's own proxy: register,
`auth/me`, dry-run and commit import of 100 contacts, duplicate re-import, listing and search,
consent grant, eligibility check, suppression override, campaign create, add 30 recipients,
duplicate recipients rejected, start/pause/resume/stop, illegal transition returns 409,
dashboard summary, all ten dashboard pages rendering with the expected content, bad-login 401,
missing record 404, anonymous proxy call 401, and a second workspace seeing none of the first
workspace's data.

## What is built

- **Auth and tenancy**: workspaces, users, roles (`owner`/`admin`/`member`), Argon2id hashes,
  HS256 access (15 min) + refresh (7 day) tokens, auth-route rate limiting, workspace-scoped
  dependencies on every route.
- **Contacts**: CRUD, search by name/phone/email, filters (tag, language, source), pagination,
  E.164 phone normalisation, tag normalisation, workspace-unique phone and email.
- **CSV import**: dry-run preview with per-row status and errors, duplicate detection in-file
  and against the database, custom columns stored as custom fields, 5 MB / 5,000 row guards.
- **Consent and suppression**: per-channel consent with proof and timestamp, suppression list
  (`dnd`, `unsubscribe`, `bounce`, `complaint`, `manual`), and one eligibility gate
  (`check_channel_allowed`) that every send path must use.
- **Campaigns**: draft -> scheduled -> running -> paused -> completed state machine with an
  explicit `failed` state, recipient management with duplicate skipping, scheduler promotion of
  due campaigns, and delete restricted to non-running campaigns.
- **Events**: append-only cross-module timeline (`system`, `voice`, `email`, `seo`) written by a
  single service and surfaced on contacts, campaigns and the dashboard.
- **Jobs**: database-backed progress and terminal states including `dead_letter`, Celery app
  with `default`, `voice`, `seo`, `email` queues, and a `system.ping` job to verify the pipeline.
- **Webhooks**: workspace-scoped receiver that stores raw provider callbacks before any parsing.
- **Dashboard**: sign in/up, overview with stats and activity, contacts (list, filters, import,
  detail with consent controls and eligibility), campaigns (list, create, detail, controls,
  recipient picker), settings (workspace profile, calling window, members, suppression list),
  and clearly-labelled Voice / Website & SEO / Email scope pages.
- **Compliance in code paths**: consent before eligibility, suppression overrides consent,
  calling window validated and stored per workspace, no PII in logs, request IDs on responses
  and log lines, `Cache-Control: no-store` and hardening headers on API responses.

## What is deliberately not built

Paid ads, social posting, SMS/WhatsApp, automatic website changes, billing, mobile apps. The
SEO module is read-only by design. No real provider call is made anywhere in Milestones 0-1.

## What is not verified yet (be explicit with the client)

1. **`docker compose up` has never been executed.** Docker is not installed on this machine.
   The compose file is validated (`docker compose config -q`) in CI, and every image's runtime
   path was exercised locally: the API ran under uvicorn, and the dashboard ran from the
   production `output: standalone` bundle that `apps/web/Dockerfile` copies.
2. **Redis was never running.** Tests use the in-process rate-limiter fallback and Celery eager
   mode. Queue behaviour, `beat` scheduling and the `system.ping` job have not run against a
   real broker.
3. **No provider credentials exist**, so Vobiz, Sarvam and SES were never called. The webhook
   receiver was exercised with a locally generated token, not a real Vobiz signature.
4. **Token refresh in the proxy** (an expired access token triggering a refresh and a single
   retry) is implemented but was not observed end to end because access tokens live 15 minutes;
   the 401 path itself was verified.
5. **Recording and transcript tables are unused** until Milestone 4.
6. **UI is not covered by automated browser tests.** Rendering was verified by fetching pages
   and asserting on their content; client-side interactions (import panel, contact picker,
   forms) were code-reviewed and type-checked, not clicked by a browser automation tool.

## Decisions worth reviewing

| Decision | Why |
| --- | --- |
| `jobs` and `webhook_deliveries` tables added to the brief's list | Job progress/dead-letter and raw callback storage had nowhere else to live; both are workspace-scoped. |
| Webhook URL carries `workspace_id` + a workspace HMAC token | Provider callbacks have no user session. The payload-signature scheme is a placeholder until Vobiz's documented V2/V3 validation lands in Milestone 4. |
| Vobiz credentials are `VOBIZ_AUTH_ID` + `VOBIZ_AUTH_TOKEN` | The live API authenticates with `X-Auth-ID` / `X-Auth-Token`; the brief's single key does not exist. |
| Sarvam defaults to `saaras:v3` / `bulbul:v3`, overridable by env | Honours the brief while the v3 vs v4 question is open. |
| The global dashboard loading skeleton was removed | `loading.tsx` above a page commits an HTTP 200 before `notFound()` can run, so a missing or foreign record rendered a 404 page with a 200 status. Correct status codes were chosen over the skeleton; clients can re-add `app/(dashboard)/loading.tsx` if they prefer the skeleton. |
| Local API tests ran on PostgreSQL 18 (port 55432) | Docker is unavailable here. Compose and CI pin PostgreSQL 16, which is what the client will run. |
| Campaigns may only be deleted when not running or paused | Prevents deleting work that a worker is actively processing. |

## Open questions (answers needed before the related milestone)

The full list with reasoning lives in `docs/architecture.md` ("Open questions"), the provider
pages in the same file ("Provider research"). Summary:

1. Sarvam models: stay on `saaras:v3` + `bulbul:v3` as the brief pins, or move to Saaras v4 +
   Bulbul v4 Flash now that v3 is announced EOL on Voice Agents (2026-11-10)? (before M4)
2. Confirm the Vobiz credential rename to `VOBIZ_AUTH_ID` / `VOBIZ_AUTH_TOKEN`. (before M4)
3. Which DND registry/API should be used, and is a paid subscription expected? (before M4)
4. Which Vobiz number series (140 / 1600 / 92) and DLT registration does the first customer
   use? (before M4)
5. What consent proof formats are acceptable (IVR recording, web form timestamp + IP, signed
   upload)? (before M4; affects what we store)
6. Recording and transcript retention period, and the delete-on-request process? (before M4)
7. Confirm 09:00-21:00 local time as the default calling window. (before M4)
8. Raw STT/TTS pipeline as the brief specifies, or Sarvam Voice Agents? (before M4)
9. Which verified SES domain and region, and which From identity, for the first real send?
   (before M2 - this is the only question blocking the next milestone)
10. Is PostgreSQL 18 for local development and PostgreSQL 16 in containers acceptable, or
    should local development also be pinned to 16? (housekeeping)

## Recommended next step

Milestone 2 (email agent) can start as soon as question 9 is answered. Until an SES identity
and region are provided, the email module can be built and tested against
`EMAIL_PROVIDER=console`, which logs instead of sending, with real sending switched on the
moment credentials arrive.
