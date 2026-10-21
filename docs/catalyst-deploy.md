# Deploying to Zoho Catalyst

This guide walks through deploying the Agentic Marketing Platform on Zoho
Catalyst (serverless functions + static client hosting).

## Project structure for Catalyst

```
AMA/
├── catalyst.json              # Root project config (functions + client targets)
├── functions/                 # Catalyst Python serverless functions
│   ├── shared/                # Shared library (config, models, services, schemas)
│   ├── auth/                  # Auth function (register, login, me)
│   ├── contacts/              # Contacts function (CRUD, import, consent)
│   ├── campaigns/             # Campaigns function (state machine, recipients)
│   ├── email/                 # Email function (send, webhooks)
│   ├── voice/                 # Voice function (stub, Phase 1)
│   ├── webhooks/              # Webhooks function (provider callbacks)
│   └── jobs/                  # Jobs function (progress, system.ping)
│       ├── main.py            # Catalyst handler entry point
│       ├── catalyst-config.json  # Per-function config (stack, env vars)
│       └── requirements.txt   # Python dependencies
├── client/                    # Catalyst client (Next.js static export)
│   ├── client-package.json    # Client config (name, version, homepage, 404)
│   ├── index.html             # SPA entry point
│   └── 404.html               # Custom 404 page
├── scripts/
│   └── deploy-catalyst.sh     # One-command deployment script
└── docs/
    └── catalyst-deploy.md     # This file
```

## Prerequisites

1. **Catalyst CLI** installed:
   https://docs.catalyst.zoho.com/en/cli/v1/

2. **Logged in**:
   ```bash
   catalyst login
   ```

3. **Environment variables** set in your shell or `.env` (never commit secrets):
   See `.env.example` for the complete list. Key variables:
   - `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`
   - `EMAIL_PROVIDER`, `EMAIL_FROM_ADDRESS`, `AWS_REGION`
   - `VOBIZ_AUTH_ID`, `VOBIZ_AUTH_TOKEN`, `SARVAM_API_KEY`

## Deployment

### One command

```bash
./scripts/deploy-catalyst.sh production
```

The script:
1. Builds the Next.js frontend as a static export (`apps/web/out/`)
2. Copies static assets to `client/` for Catalyst client hosting
3. Deploys each Python function under `functions/`
4. Deploys the client

### Per-function deployment

Deploy a single function:

```bash
catalyst deploy function email
```

Deploy the client:

```bash
catalyst deploy client
```

## Environment variables in Catalyst

Each function's `catalyst-config.json` declares its `env_variables`. Set the actual
values in the Catalyst console (Functions -> your function -> Environment Variables)
or via the CLI:

```bash
# Example: set JWT_SECRET for the auth function
catalyst function update auth --env-variables JWT_SECRET=<your-secret>
```

Never hardcode secrets in `catalyst-config.json` — use `${VAR_NAME}` placeholders.

## Database

Catalyst functions connect to an external PostgreSQL (or Catalyst Data Store).
Set `DATABASE_URL` in each function's environment variables. The initial schema
(Alembic migration `d1a44dda1860`) must be applied to the target database before
first deployment:

```bash
# Run locally against the target DB
alembic upgrade head
```

## Email sending (Milestone 2)

The email function defaults to `EMAIL_PROVIDER=console` (logs only, no real
email sent). To send real email via Amazon SES:

1. Set `EMAIL_PROVIDER=ses` in the email function's env vars.
2. Set `EMAIL_FROM_ADDRESS`, `AWS_REGION`, and AWS credentials.
3. Verify your SES domain/identity (see open question 9 in `docs/architecture.md`).

## Voice (Phase 1 stub)

The voice function is a stub — it answers health checks and refuses outbound
calls with HTTP 501. Real Vobiz + Sarvam integration lands in Phase 2.

## Local development

For local development (not Catalyst), use the existing Docker Compose stack:

```bash
docker compose up
```

Or run the API and dashboard directly from `apps/api` and `apps/web`.

## Catalyst CLI reference

| Command | Purpose |
|---------|---------|
| `catalyst login` | Authenticate with Catalyst |
| `catalyst whoami` | Check login status |
| `catalyst deploy function <name>` | Deploy one function |
| `catalyst deploy client` | Deploy the frontend client |
| `catalyst deploy` | Deploy all resources |
