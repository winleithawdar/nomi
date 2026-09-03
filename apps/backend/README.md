# Backend

This folder contains the Python backend for Nomi.

## Structure

```text
apps/backend/
├── src/               # Backend application code
└── tests/             # Backend test suite
```

The backend includes the personal baseline layer (Winnie), P1/P2 detection, and the P4
verification + escalation + caregiver alert engine.

For the live proof of concept, use the Telegram provider. The WhatsApp provider
is kept as a compatible adapter, but requires Meta-specific setup and is not the
recommended local or presentation path.

## Run API

```bash
pip install -e .
DATABASE_URL=sqlite:///./nomi_demo.db NOMI_DATA_MODE=demo NOMI_MESSAGING_PROVIDER=mock \
  uvicorn nomi_backend.api:app --reload
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./nomi_verification.db` | SQLAlchemy connection for verification/alert persistence. Use a dedicated local `.db` file for demo runs. |
| `NOMI_DATA_MODE` | `demo` | Use deterministic `demo` data or PostgreSQL `database` reads |
| `NOMI_CORS_ORIGINS` | Local frontend URLs | Comma-separated allowed frontend origins |
| `NOMI_MESSAGING_PROVIDER` | `mock` | `mock`, `telegram` (live demo), or `whatsapp` |
| `TELEGRAM_BOT_TOKEN` | empty | BotFather token; required when provider is `telegram` |
| `TELEGRAM_WEBHOOK_SECRET` | empty | `X-Telegram-Bot-Api-Secret-Token` / `setWebhook` `secret_token` |
| `NOMI_DEMO_SENIOR_CHAT_ID` | empty | Seed `senior-1` Telegram chat id (alias of `NOMI_DEMO_SENIOR_WA_ID`) |
| `NOMI_DEMO_CAREGIVER_CHAT_ID` | empty | Seed caregiver contact for `senior-1` |

For Supabase, set `DATABASE_URL` to the PostgreSQL connection string and apply migrations
from `infra/supabase/migrations/`.

## Verification API (P3 / P5)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/verifications` | Start senior-first verification from a detection payload |
| `POST` | `/api/v1/verifications/{id}/response` | Record senior response (`reassuring` or `help_needed`) |
| `POST` | `/api/v1/verifications/{id}/no-response` | Handle verification timeout (P3 scheduler) |
| `GET` | `/api/v1/verifications/{id}` | Fetch verification detail |
| `GET` | `/api/v1/seniors/{id}/verification-status` | Active verification for dashboard |
| `GET` | `/api/v1/seniors/{id}/verifications` | Verification history |
| `GET` | `/api/v1/seniors/{id}/alerts` | Caregiver alert history |
| `GET` | `/api/v1/seniors/{id}/detections/change` | Latest longitudinal change result |
| `PUT` | `/api/v1/seniors/{id}/contacts/{role}` | Register a senior or caregiver messaging contact |
| `POST` | `/api/v1/checkins` | Send and persist a check-in |
| `POST` | `/api/v1/checkins/{id}/missed` | Close a missed check-in and run detection |
| `GET` | `/api/v1/verifications/{id}/check-in-message` | P3: outbound senior check-in text |
| `GET` | `/api/v1/alerts` | P5: dashboard alert feed (optional filters) |
| `GET` | `/api/v1/alerts/{id}/caregiver-message` | P3: outbound caregiver alert text |
| `GET` | `/api/v1/alerts/{id}` | Alert detail |
| `POST` | `/api/v1/alerts/{id}/delivered` | P3: mark alert delivered |

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
