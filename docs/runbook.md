# Runbook

## Services

| Service | Local URL | Health |
| --- | --- | --- |
| Dashboard | http://localhost:3000 | `/login` |
| API | http://localhost:8000 | `/health`, `/health/ready` |
| API docs | http://localhost:8000/docs | - |
| Voice server | http://localhost:8001 | `/health` (stub until M4) |
| PostgreSQL | localhost:5432 | `pg_isready` |
| Redis | localhost:6379 | `redis-cli ping` |

## Start and stop

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f api worker
docker compose down          # keep data
docker compose down -v       # delete local data
```

Migrations run automatically in the one-shot `migrate` service. To run them manually:

```bash
docker compose run --rm migrate alembic upgrade head
```

## Local test database

The test suite applies migrations to the database in `DATABASE_URL` and clears the schema.
Never point it at shared or production data.

```bash
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ama_test
cd apps/api
alembic upgrade head
pytest --cov=app --cov-report=term-missing
```

## Health and readiness

- `GET /health` is process liveness only.
- `GET /health/ready` checks PostgreSQL. If `REDIS_URL` is set, Redis is checked too and a
  failure returns `503` with `redis: "down"`.
- Request IDs are returned in `X-Request-ID` and included in every API log line.

## Background jobs

- Queues: `default`, `voice`, `seo`, `email`.
- Workers: `celery -A app.workers.celery_app.celery_app worker -Q default,voice,seo,email`.
- Scheduler: `celery -A app.workers.celery_app.celery_app beat`.
- A job row is created before enqueueing, updated to `running` with progress, then
  `succeeded` / `failed` / `dead_letter`.
- `dead_letter` means retries are exhausted. Inspect `jobs.error`, fix the cause, then
  re-enqueue deliberately; there is no automatic replay.
- `GET /jobs?status=dead_letter` lists them for owners/admins.

## Provider checks (before Milestone 2 and 4)

### Amazon SES

1. Verify the sending domain (or address) in the SES console for the chosen region.
2. Publish DKIM CNAME records; add SPF and a DMARC record.
3. Request production access if the account is still in the sandbox.
4. Put `EMAIL_PROVIDER=ses`, `AWS_*`, and the From identity in `.env`.
5. Send one test message through the API test-send route (Milestone 2).

### Vobiz

1. Create the account, complete KYC, and buy the correct India number series.
2. Copy `X-Auth-ID` and `X-Auth-Token` from Settings -> API.
3. Point the application/call `answer_url` (or stream) at the public HTTPS voice server.
4. Confirm callback signatures are enabled and store `VOBIZ_WEBHOOK_SECRET`.
5. Place one manual call to the developer's phone (Milestone 4a).

### Sarvam

1. Create an API key and set `SARVAM_API_KEY`.
2. Confirm the STT/TTS model versions in `docs/architecture.md` before implementation.
3. Run a short Hindi and English TTS/STT smoke test (Milestone 4a).

## Latency logging (Milestone 4)

Planned measurement: timestamp at end of contact speech (STT VAD `speech_end`) and timestamp
at first outbound audio frame for the reply. Store per turn and report the median and p95 in
this runbook. **Not measured yet** - do not claim a latency figure until a real call is run.

## Incident basics

1. Check `/health/ready` and `docker compose ps`.
2. Check API logs by request ID; check worker logs for the campaign ID.
3. If the database is down, the API returns 503 and workers retry with backoff.
4. If Redis is down, API reads/writes still work but rate limiting falls back to per-process
   memory (not shared across replicas) and Celery cannot enqueue.
5. For a bad campaign, `stop` it; for a bad contact, delete it or add a suppression.
6. Rotate any leaked secret, then restart API and workers.

## Backup and retention

- PostgreSQL: daily logical dumps (`pg_dump -Fc`) retained per the customer agreement;
  restore into a scratch database before relying on a backup.
- Redis: queues are transient; do not treat Redis as a system of record.
- Recordings/transcripts: retention policy is an open legal question; until confirmed,
  store only what the voice milestone requires and support deletion by contact.

## Known limitations (end of Milestone 1)

- Docker Compose was not executed on the development machine (Docker not installed); it is
  validated by CI. The API ran under uvicorn and the dashboard ran from the production
  standalone bundle that `apps/web/Dockerfile` ships.
- Redis is not installed locally; API tests exercise the in-memory rate limiter and Celery
  eager mode. Queue, `beat` and worker paths need a real broker.
- Voice, SEO and email module screens are placeholders.
- No real provider credentials are configured, so no paid API has been called.
- There is no `app/(dashboard)/loading.tsx`. A route-level loading boundary commits HTTP 200
  before `notFound()` runs, which made a missing or cross-workspace record render a 404 page
  with a 200 status. Correct status codes were chosen over the skeleton; re-adding the file
  restores the skeleton and the 200 status.
- Client-side interactions are not covered by browser automation; `scripts/smoke_test.py`
  asserts rendered page content instead.
