# Nomi

Nomi is a caregiver support tool that helps families notice meaningful changes
in an older adult's routine without treating every delayed reply as an
emergency. It learns a personal baseline from recent check-ins, checks with the
senior first when something changes, and only then gives the caregiver a clear,
actionable alert.

## The Problem

Caregivers often have limited visibility into a loved one's day-to-day
wellbeing. A missed or late reply can be concerning, but population-wide rules
are noisy: one person's unusual delay may be another person's normal routine.
Nomi is designed to reduce that uncertainty while preserving the senior's
agency.

## Proposed Solution

Nomi combines a FastAPI backend, a mobile-first Next.js caregiver dashboard,
and a messaging proof of concept:

- **Personal baselines:** calculates each senior's typical response time,
  interaction frequency, missed-check-in rate, and optional wellbeing pattern.
- **Explainable change detection:** identifies isolated anomalies and sustained
  changes from that senior's own recent pattern.
- **Senior-first verification:** sends a check-in before escalating, so an
  ordinary explanation does not immediately become a caregiver alert.
- **Clear caregiver experience:** presents live check-ins, plain-language
  assessments, alerts, and visual trends in a phone-first dashboard.
- **Telegram proof of concept:** supports a live Telegram Bot API round trip
  for demonstrations, while the mock provider makes local development work
  without external credentials. The existing WhatsApp adapter is retained for
  future deployment.

What makes Nomi distinct is the sequence: **personal normal -> verified
change -> helpful next step**. It is not a generic chatbot or a one-size-fits-
all alert threshold.

### Why Telegram For The Demo

The messaging abstraction supports both Telegram and WhatsApp. For this proof
of concept, Telegram is the live transport because it provides a fast,
reliable bot-and-webhook setup for demonstrating the complete round trip within
the project timeline. WhatsApp Cloud API remains a supported adapter, but its
Meta app, business, phone-number, and webhook setup adds approval and
configuration overhead that is not necessary to validate Nomi's core workflow.

## Architecture

```text
Senior reply / scheduled check-in
            |
            v
FastAPI: baseline + detection + verification + persistence
            |
            +--> Telegram or mock messaging provider
            |
            v
Next.js caregiver dashboard
```

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer and npm
- Optional for live messaging: a Telegram bot token and a public HTTPS tunnel
  such as ngrok

## Run Locally

The default local path uses deterministic demo data, SQLite, and mock
messaging. It does not require Supabase, Telegram, or WhatsApp credentials.

1. Clone the repository and open it:

```bash
git clone <repository-url>
cd nomi
```

2. Start the backend in one terminal:

```bash
cd apps/backend
python -m venv ../../.venv-backend
source ../../.venv-backend/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
DATABASE_URL=sqlite:///./nomi_demo.db NOMI_DATA_MODE=demo NOMI_MESSAGING_PROVIDER=mock \
  uvicorn nomi_backend.api:app --reload --port 8000
```

Confirm that the API is available:

```bash
curl http://127.0.0.1:8000/health
```

3. Start the frontend in a second terminal:

```bash
cd apps/frontend
npm ci
NOMI_API_BASE_URL=http://127.0.0.1:8000 NEXT_PUBLIC_NOMI_API_BASE_URL=http://127.0.0.1:8000 \
  npm run dev
```

4. Open [http://localhost:3000/dashboard](http://localhost:3000/dashboard).
   The dashboard is designed primarily for a phone-width caregiver view.

`apps/backend/nomi_demo.db` is local state. Delete it when you want to reset
the demo data.

## Telegram Proof Of Concept

For a live messaging demo, create a bot with
[@BotFather](https://t.me/BotFather), then copy `.env.example` to `.env` and
set the following values:

```env
NOMI_MESSAGING_PROVIDER=telegram
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_WEBHOOK_SECRET=<a secret you choose>
NOMI_DEMO_SENIOR_CHAT_ID=<senior chat id>
NOMI_DEMO_CAREGIVER_CHAT_ID=<caregiver chat id>
```

Run the API, expose `http://127.0.0.1:8000` through an HTTPS tunnel, then
register `<public-url>/webhooks/telegram` as the Telegram webhook. The full
step-by-step guide, including webhook registration and chat-id lookup, is in
[the Telegram demo guide](docs/workstreams/P3/telegram-demo-setup.md).

Never commit a populated `.env` file or bot token.

## Configuration

| Variable | Local default | Purpose |
| --- | --- | --- |
| `NOMI_DATA_MODE` | `demo` | Uses deterministic demo data; set to `database` to read the shared database schema. |
| `DATABASE_URL` | SQLite file | Database for verification, alerts, and persistent check-ins. |
| `NOMI_MESSAGING_PROVIDER` | `mock` | `mock`, `telegram`, or `whatsapp`. |
| `NOMI_API_BASE_URL` | `http://127.0.0.1:8000` | Server-side URL used by the Next.js app. |
| `NEXT_PUBLIC_NOMI_API_BASE_URL` | `http://127.0.0.1:8000` | Browser-visible API URL used by live check-in updates. |

For PostgreSQL/Supabase setup, see [database setup](docs/database-setup.md).

## Verify The Project

Backend tests:

```bash
cd apps/backend
python -m unittest discover -s tests -p "test_*.py"
```

Frontend production build:

```bash
cd apps/frontend
npm run build
```

## Repository Layout

```text
apps/backend/     FastAPI API, detection, verification, messaging, persistence
apps/frontend/    Next.js caregiver dashboard
docs/             architecture, setup, and workstream documentation
infra/supabase/   PostgreSQL migrations
```
