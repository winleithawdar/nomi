# P6 integration handoff

## Connected in this change

- The Next.js dashboard now calls FastAPI for senior summaries, senior detail, latest anomaly,
  verification state, and caregiver alerts.
- FastAPI exposes a health endpoint, configurable CORS, anomaly and longitudinal-change
  endpoints, SQLite demo persistence, and optional PostgreSQL-backed baseline reads.
- The deterministic demo uses the real anomaly detector, starts senior-first verification,
  records no response, creates an alert, and displays it on the dashboard.
- The Supabase integration migration makes `senior_id` consistently text across workstreams,
  creates profile/consent relationships, and inserts idempotent demo data.
- The P3 check-in store now persists contacts, open/closed check-ins, webhook events, and
  derived interactions in PostgreSQL. New interactions automatically run detection and begin
  verification; verification replies can resolve or deliver a caregiver alert.

## API contract used by P5

| Method | Path | Frontend use |
|---|---|---|
| `GET` | `/health` | Deployment health check |
| `GET` | `/api/v1/seniors` | Dashboard and senior list |
| `GET` | `/api/v1/seniors/{id}` | Baseline detail and charts |
| `GET` | `/api/v1/seniors/{id}/detections/anomaly` | Latest sudden change |
| `GET` | `/api/v1/seniors/{id}/detections/change` | Latest sustained change |
| `GET` | `/api/v1/seniors/{id}/verification-status` | Active check-in/latest alert |
| `GET` | `/api/v1/alerts` | Dashboard caregiver alert feed |

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `NOMI_API_BASE_URL` | Frontend server | FastAPI base URL |
| `NOMI_CORS_ORIGINS` | Backend | Comma-separated allowed frontend origins |
| `NOMI_DATA_MODE` | Backend | `demo` or `database` |
| `DATABASE_URL` | Backend | SQLite or Supabase PostgreSQL URL |
| `NOMI_MESSAGING_PROVIDER` | Backend | `mock` or `whatsapp` |
| `WHATSAPP_*` | Backend | Meta Cloud API credentials and webhook verification |

## Decisions needed from teammates

1. **All backend owners:** confirm that text `senior_id` is the canonical contract. P1 originally
   created UUID columns, while P3/P4/P5 use text IDs. P6 currently resolves this in favour of
   text because it matches the active APIs.
2. **P3/P4 owners:** agree who runs the production timeout scheduler that calls
   `/verifications/{id}/no-response` and who sends/marks the caregiver alert as delivered.
3. **P5 owner:** confirm the current alert cards and detection/verification panels match the
   final presentation design. The data contract is live; styling can change independently.
4. **Project owner:** provide the final Supabase, backend HTTPS, frontend HTTPS, and Meta test
   phone details before deployment configuration can be completed.

## Known production blocker

The remaining operational item is scheduling timeout processing for seniors who never answer a
verification prompt. The `/verifications/{id}/no-response` path now delivers and records alerts,
but production still needs a cron/worker to call it after the configured timeout.

## Verification completed

- Persistent-store restart and duplicate-webhook tests added.
- Isolated database → signed webhook → detection → verification → delivered alert test added.
- `npm run build`: Next.js production build passed.
- Live-process smoke test: FastAPI health check, anomaly detection, unresolved verification,
  caregiver alert creation, and server-rendered dashboard alert all passed.
