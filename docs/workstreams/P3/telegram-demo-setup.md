# P3 — Telegram Bot API Demo Setup

Live demo transport for Nomi check-ins and verification prompts. WhatsApp
Cloud API code stays in the backend; this path is the one you run for a
student/demo round trip.

**Nomi/FastAPI → Telegram bot → senior reply → webhook → FastAPI**

Meal follow-up chat text is stored locally so session scoring can run
(see [session-scoring.md](session-scoring.md)). The live-checkin API still
returns only wellbeing 1–5, not the raw Telegram thread. Verification
outcomes are recorded with `response_text=None`.

Companion docs:

- Brief: [p3-whatsapp-integration.md](../p3-whatsapp-integration.md)
- Implementation notes: [implementation-notes.md](implementation-notes.md)
- WhatsApp leftover: [meta-cloud-api-setup.md](meta-cloud-api-setup.md)

P6 owns production HTTPS. For this proof, ngrok (or similar) stands in.

## 0. What you will collect

| Item | Env var | Where it appears |
|---|---|---|
| Bot token from BotFather | `TELEGRAM_BOT_TOKEN` | Bot API `sendMessage` path |
| Webhook secret you invent | `TELEGRAM_WEBHOOK_SECRET` | `X-Telegram-Bot-Api-Secret-Token` + `setWebhook` `secret_token` |
| Senior Telegram chat id | `NOMI_DEMO_SENIOR_CHAT_ID` | Seeded as `senior-1` (stored on `wa_id`) |
| Caregiver Telegram chat id | `NOMI_DEMO_CAREGIVER_CHAT_ID` | Seeded as caregiver for `senior-1` |
| Provider | `NOMI_MESSAGING_PROVIDER` | `telegram` for live, `mock` otherwise |

Never commit a filled `.env`. Copy placeholders from repo-root `.env.example`.

---

## 1. Create a bot with BotFather

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts (display name + username ending in `bot`).
3. Copy the HTTP API token. Put it in `.env` as `TELEGRAM_BOT_TOKEN`.
4. Optionally send `/setprivacy` and disable privacy if you need group text
   (the demo is a private chat with the bot).

## 2. Get a chat id

The Bot API chat id is a numeric id, not the @username.

1. Start a private chat with your bot and send `/start` (or any text).
2. Either paste the numeric chat id if you already know it, or call getUpdates
   while no webhook is set:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates"
```

Look at `result[].message.chat.id`. Put that value in
`NOMI_DEMO_SENIOR_CHAT_ID`. Repeat from a second Telegram account for
`NOMI_DEMO_CAREGIVER_CHAT_ID` if you want caregiver alerts delivered.

`POST /api/v1/contacts` also accepts `chat_id` as an alias for `wa_id`
(the stored contact id field is still `wa_id`).

## 3. Run the API and expose HTTPS

From `apps/backend`:

```bash
pip install -e .
uvicorn nomi_backend.api:app --reload
```

In another terminal, tunnel port 8000:

```bash
ngrok http 8000
```

The webhook URL is:

```text
https://<ngrok-host>/webhooks/telegram
```

Invent a random `TELEGRAM_WEBHOOK_SECRET` and put it in `.env`. Then attach
the webhook (replace the placeholders):

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://<ngrok-host>/webhooks/telegram" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

Telegram will send `X-Telegram-Bot-Api-Secret-Token` on each POST. A mismatch
returns 403. If the secret env var is empty, the check is skipped (local
dev only).

## 4. Environment

```bash
NOMI_MESSAGING_PROVIDER=telegram
TELEGRAM_BOT_TOKEN=<BotFather token>
TELEGRAM_WEBHOOK_SECRET=<same secret_token as setWebhook>
NOMI_DEMO_SENIOR_CHAT_ID=<numeric chat id>
NOMI_DEMO_CAREGIVER_CHAT_ID=<numeric chat id for caregiver alerts>
NOMI_SCHEDULER_ENABLED=1
```

Restart uvicorn after editing `.env`. On boot, Nomi seeds `senior-1` from
`NOMI_DEMO_SENIOR_CHAT_ID` (or leftover `NOMI_DEMO_SENIOR_WA_ID`) and a
caregiver contact from `NOMI_DEMO_CAREGIVER_CHAT_ID` when set.

## 5. Send a check-in

```bash
curl -X POST http://127.0.0.1:8000/api/v1/checkins \
  -H "Content-Type: application/json" \
  -d '{"senior_id":"senior-1"}'
```

Reply in Telegram with `1`–`5` to close the check-in (wellbeing is parsed).
Nomi then asks two follow-ups; after the third senior turn it scores the
session (As usual / Changed from usual / Needs you now). Scheduled meals
are 08:00 / 12:30 / 18:30 SGT; `POST /api/v1/checkins/run-due` fires the
current meal. Dashboard **Send Nomi check-in** is an extra ping.

Starting a verification via `POST /api/v1/verifications` also sends the
senior prompt over Telegram when a senior contact exists. Replies `1`,
`2`, or text containing `help` / `not ok` / `not okay` map to
`help_needed`; anything else is `reassuring`. Those outcomes are recorded
with `response_text=None`.

## 6. Confirm the webhook

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
```

`url` should match your ngrok host. ngrok URLs change on restart — run
`setWebhook` again after a new tunnel.
