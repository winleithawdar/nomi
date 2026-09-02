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
2. **P3 owner:** choose whether `InMemoryCheckInStore` will remain demo-only or be replaced by a
   PostgreSQL `CheckInStore`. The current WhatsApp webhook is correct and duplicate-safe, but a
   backend restart loses open check-ins and inbound events.
3. **P3/P4 owners:** agree who runs the production timeout scheduler that calls
   `/verifications/{id}/no-response` and who sends/marks the caregiver alert as delivered.
4. **P5 owner:** confirm the current alert cards and detection/verification panels match the
   final presentation design. The data contract is live; styling can change independently.
5. **Project owner:** provide the final Supabase, backend HTTPS, frontend HTTPS, and Meta test
   phone details before deployment configuration can be completed.

## Known production blocker

The real WhatsApp path and the dashboard are individually connected to backend services, but
the P3 check-in store is still in memory. Do not claim restart-safe production persistence until
the P3 owner or P6 implements the PostgreSQL store. The deterministic seeded demo and mock
messaging path are ready as the presentation fallback.

## Verification completed

- `python -m unittest discover -s tests -p "test_*.py"`: 149 tests passed.
- `npm run build`: Next.js production build passed.
- Live-process smoke test: FastAPI health check, anomaly detection, unresolved verification,
  caregiver alert creation, and server-rendered dashboard alert all passed.
