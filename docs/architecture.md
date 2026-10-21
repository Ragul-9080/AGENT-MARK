# Architecture

Status: Milestones 0 and 1 implemented. Voice, SEO and email modules are designed but not
built. This document is the source of truth for structure and provider facts; update it at
the end of every milestone.

## System diagram

```
Dashboard (Next.js) --server-side proxy--> Common API (FastAPI)
                                              |        |
                                     PostgreSQL 16    Redis/Celery
                                              |
                       +----------------------+----------------------+
                       |                      |                      |
                   Voice worker           SEO worker            Email worker
                       |                      |                      |
                Vobiz + Sarvam         Playwright + LLM           SES + LLM
```

The voice server is a separate FastAPI WebSocket service. It talks to the common API for
session context and writes results back through internal service calls (Milestone 4).

## Runtime decisions

| Area | Decision | Reason |
| --- | --- | --- |
| Python | 3.12 in containers and CI | Matches the brief. Local development here used 3.15 because it was installed; the code avoids 3.13+ syntax. |
| ORM | SQLAlchemy 2.0 typed models, synchronous sessions | FastAPI runs sync endpoints in its threadpool. Celery is synchronous. One database access style everywhere. |
| IDs | UUIDv4, generated in Python | Safe to create before flush; no database-specific sequence assumptions. |
| Enums | Python `str` enums stored as VARCHAR + CHECK (`native_enum=False`) | Simpler migrations and safer enum evolution. |
| Timestamps | `TIMESTAMPTZ`, UTC | Workspace timezone is applied only for display and calling windows. |
| Auth | Argon2id password hashes, HS256 JWT access (15 min) + refresh (7 days) | No session table needed. Refresh tokens are typed and workspace-bound. |
| Tenancy | Every table has `workspace_id`; every query filters on it | Enforced in services and covered by isolation tests. |
| Roles | `owner`, `admin`, `member`, one role per user | A user belongs to one workspace in Phase 1; team members share that workspace. Multi-workspace switching is not in scope. |
| Jobs | `jobs` table stores progress and terminal state; `dead_letter` status is the DLQ | Satisfies progress + dead-letter requirements without another broker feature. |
| Webhooks | Raw payload stored in `webhook_deliveries` before any processing | Fast acknowledgement, replay/debug support, audit trail. |
| Local provider defaults | `EMAIL_PROVIDER=console`, no LLM calls | Milestones 0-1 must run without paid credentials. |

## Data model

All tables use UUID `id`, `workspace_id`, `created_at`, `updated_at` except `workspaces`
(which is itself the tenant boundary). Module tables are created in the initial migration so
later milestones add behaviour, not schema churn.

| Table | Notes |
| --- | --- |
| `workspaces` | Name, IANA timezone, default language, JSON settings (calling window, sender identity). |
| `users` | Globally unique lowercased email, Argon2 hash, role, active flag. |
| `contacts` | Phone (E.164), email, language, tags JSON, source, custom fields JSON. Unique phone and email per workspace. |
| `consents` | One row per contact + channel (`voice`, `email`) with `granted`/`revoked`, proof text and `recorded_at`. |
| `suppressions` | Permanent block by channel and normalized value; reasons `dnd`, `unsubscribe`, `bounce`, `complaint`, `manual`. |
| `campaigns` | Type (`voice`, `email`), status, `scheduled_at`, JSON settings. |
| `campaign_contacts` | Recipient state, attempts, last attempt time. Unique per campaign + contact. |
| `calls`, `call_turns` | Call metadata/outcome and transcript turns. |
| `email_messages`, `email_events` | Sent message state and engagement events. |
| `websites`, `seo_audits`, `seo_issues`, `seo_recommendations` | SEO module storage. |
| `events` | Cross-module timeline, written through one service. |
| `jobs` | Background job progress, retries and dead-letter state. |
| `webhook_deliveries` | Verified raw provider callbacks. |

## Common API conventions

- Base path: `/`; OpenAPI at `/docs` and `/openapi.json`.
- Errors: `{"error": {"code": "...", "message": "...", "request_id": "...", "details": [...]}}`.
- Every request returns `X-Request-ID`; the same ID appears in log lines.
- Lists: `limit` (default 50, max 200) and `offset`, response
  `{"items": [...], "total": n, "limit": n, "offset": n}`.
- Health: `GET /health` (liveness) and `GET /health/ready` (database; Redis reported as a
  dependency when configured).
- Auth: `Authorization: Bearer <access token>`.

## Campaign state machine

```
draft ──start──> scheduled ──(scheduler)──> running ──pause──> paused ──resume──> running
  │                  │                        │                   │
  └──────start──────>└────────stop───────────>└──────stop────────>└──stop──> completed
                                                                              failed (worker error)
```

`stop` moves a campaign to `completed` and records who stopped it in the event payload.
Illegal transitions return `409 conflict` with code `invalid_campaign_transition`.

## Consent and suppression enforcement

`check_channel_allowed()` in `app/services/consent.py` is the single gate used by every send
path:

1. Contact must be in the workspace.
2. Channel value must exist (phone for voice, email for email).
3. An active suppression on the normalized value blocks the send.
4. Consent must exist with `status=granted`.
5. The caller decides whether a missing consent can be replaced by a documented lawful basis
   (voice module); the default is block.

Voice additionally checks calling hours and the DND registry. DND is represented as a
suppression with reason `dnd`; the registry adapter is not implemented because no registry
provider/API has been selected (see open questions).

## Provider research (official documentation)

Read on 2026-10-19. Do not guess fields; these are the pages the implementation will follow.

### Vobiz (telephony)

- Introduction / quick start: https://www.vobiz.ai/docs/introduction,
  https://www.vobiz.ai/docs/quick-start
- Authentication (two headers `X-Auth-ID` and `X-Auth-Token`; base
  `https://api.vobiz.ai/api/v1`): https://www.vobiz.ai/docs/api-reference/authentication
- Make an outbound call (`POST /api/v1/Account/{auth_id}/Call/`; `from`, `to`,
  `answer_url` required): https://www.vobiz.ai/docs/call/make-call
- Call object / callbacks (`CallUUID`, `Event=StartApp` on answer, `Hangup` authoritative):
  https://www.vobiz.ai/docs/call/call-object, https://www.vobiz.ai/docs/concepts/callbacks
- Callback signature validation (`X-Vobiz-Signature-V2`/`V3`, HMAC-SHA256):
  https://www.vobiz.ai/docs/concepts/validating-callbacks
- Audio streams (fork audio to `wss://`; inbound L16 8/16 kHz or μ-law 8 kHz;
  bidirectional playback L16 8/16/24 kHz or μ-law 8 kHz; JSON frames with base64 audio):
  https://www.vobiz.ai/docs/audio-streams,
  https://www.vobiz.ai/docs/audio-streams/start-audio-stream
- Streaming concepts: https://www.vobiz.ai/docs/concepts/streaming-websockets
- XML `<Stream>` (start a stream from an answer URL):
  https://www.vobiz.ai/docs/xml/stream
- India compliance and DND/calling hours:
  https://www.vobiz.ai/docs/compliance/india/calling-regulations
- 140/160 series numbers: https://www.vobiz.ai/docs/best-practices/140-160-acquisition
- OpenAPI: https://www.vobiz.ai/openapi.json

Key corrections to the brief: Vobiz does **not** use a single `VOBIZ_API_KEY`; it requires
`X-Auth-ID` and `X-Auth-Token`. The environment template therefore exposes
`VOBIZ_AUTH_ID` and `VOBIZ_AUTH_TOKEN`. Callback signatures exist and will be verified in
Milestone 4 using the validation guide above, not a home-grown scheme.

### Sarvam (speech)

- Documentation index: https://docs.sarvam.ai/llms.txt
- Authentication (`api-subscription-key` header, base `https://api.sarvam.ai`):
  https://docs.sarvam.ai/api-reference/authentication
- Speech-to-text overview (models and limits):
  https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/overview
- STT REST (`POST /speech-to-text`, multipart, ≤30 s, 8/16 kHz telephony audio):
  https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/rest-api
- STT realtime streaming (`GET /speech-to-text-realtime/ws`; partial transcripts, VAD,
  barge-in signals, 8/16 kHz linear16/mulaw/alaw):
  https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming
- Text-to-speech overview: https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/overview
- TTS REST (`POST /text-to-speech`, base64 `audios`, formats include mulaw/linear16):
  https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/rest-api
- TTS streaming: https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/streaming-api
- Voices: https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/voices

Key findings that affect Milestone 4:

- Realtime streaming STT **is** available, so the brief's fallback (chunking utterances) is
  not required. The pipeline can use `saaras:v3-realtime` with server VAD and partial
  transcripts, which also gives barge-in signals.
- The docs now recommend **Saaras v4** and **Bulbul v4 Flash**; the brief pins
  `saaras:v3` / `bulbul:v3`. Both v3 and v4 are available. This is an open question below.
- Bulbul v3 reaches end of life on Sarvam Voice Agents on 2026-11-10 (the managed Voice
  Agents product, not necessarily the raw TTS API). Confirm before the voice milestone.
- Streaming STT accepts 8 kHz μ-law/linear16, matching Vobiz telephony output.

## Open questions (need answers before the related milestone)

1. **Sarvam model versions.** The brief pins Saaras v3 + Bulbul v3, but current docs
   recommend Saaras v4 + Bulbul v4 Flash and announce Bulbul v3 EOL on Voice Agents
   (2026-11-10). Should Phase 1 target v4 (one-line model change) or stay on v3?
2. **Vobiz credentials.** Confirm the env rename to `VOBIZ_AUTH_ID` / `VOBIZ_AUTH_TOKEN`.
   The brief's single `VOBIZ_API_KEY` does not match the live API.
3. **DND registry access.** Which provider or registry API will be used for TRAI DND
   checks? Until one is chosen, DND is a suppression reason with a manual/import path and
   the registry check is recorded as unavailable (never silently treated as "clean").
4. **Number series and DLT.** Which Vobiz number series (140 promotional, 1600
   transactional/service, 92 series) and DLT registration does the first customer use?
5. **Consent evidence.** What proof formats are acceptable (recorded IVR consent, web form
   timestamp + IP, signed form upload)? The current model stores free-text proof + time.
6. **Recording retention.** Confirm the retention period and the delete-on-request process
   for recordings/transcripts. No default is invented.
7. **Calling window.** Confirm 09:00-21:00 local time as the legal default; it is
   configurable per workspace.
8. **Sarvam Voice Agents vs raw pipeline.** The brief's architecture uses raw STT/TTS. A
   managed Voice Agents product now exists. Keep the raw pipeline for control and cost, or
   switch? Phase 1 assumes raw.
9. **Email sending identity.** Which verified SES domain/region and From address will be
   used for the first real send? Needed for Milestone 2 acceptance.
10. **Local tooling.** Docker and Redis are not installed on this machine, so
    `docker compose up` could not be executed here. Compose is validated by CI. Local API
    tests ran against PostgreSQL 18 on port 55432; containers pin PostgreSQL 16. Acceptable?
