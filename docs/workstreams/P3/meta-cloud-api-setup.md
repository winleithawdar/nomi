# P3 — Meta WhatsApp Cloud API Setup

> **Reference only:** the submitted live proof of concept uses Telegram because
> it is faster to configure and demonstrate end to end. Follow this guide only
> when configuring the retained WhatsApp provider after the demo.

From **no Meta developer account** to a local live round trip:

**Nomi/FastAPI → WhatsApp → senior reply → Meta webhook → FastAPI**

Official Cloud API only. Do not use WhatsApp Web scraping or unofficial
clients. You do **not** need a paid WhatsApp Business account for a
development-mode test. A personal Facebook login is enough.

Companion docs:

- Brief: [p3-whatsapp-integration.md](../p3-whatsapp-integration.md)
- Design: [specs/2026-09-01-whatsapp-checkin-design.md](specs/2026-09-01-whatsapp-checkin-design.md)
- Implementation notes: [implementation-notes.md](implementation-notes.md)

P6 owns production HTTPS. For this proof, ngrok (or similar) stands in.

## 0. What you will collect

| Item | Env var | Where it appears |
|---|---|---|
| Temporary or system-user token | `WHATSAPP_ACCESS_TOKEN` | WhatsApp → API Setup |
| Phone number ID | `WHATSAPP_PHONE_NUMBER_ID` | API Setup (not the display number) |
| App secret | `WHATSAPP_APP_SECRET` | App settings → Basic |
| Verify token (you invent this) | `WHATSAPP_VERIFY_TOKEN` | Same string in `.env` and Meta webhook form |
| Graph version | `WHATSAPP_GRAPH_API_VERSION` | Default `v21.0` |
| Provider | `NOMI_MESSAGING_PROVIDER` | `whatsapp` for live, `mock` otherwise |
| Your test phone digits | `NOMI_DEMO_SENIOR_WA_ID` | Country code + number, no `+` |

Never commit a filled `.env`. Copy placeholders from repo-root `.env.example`.

---

## 1. Register as a Meta developer (from a Facebook login)

1. Open [https://developers.facebook.com/](https://developers.facebook.com/).
2. Log in with your existing Facebook account.
3. Accept **Meta for Developers** terms (Get started / Register as a
   developer) if prompted.
4. Confirm phone or email if Meta asks. Use a number you control.

You now have a developer account. Next you create an **app**, not a
personal WhatsApp scrape.

## 2. Create a Business app and add WhatsApp

1. **Create app** → type **Business** → name it e.g. `Nomi P3`.
2. If Meta asks for a Business portfolio, create a free one (your name is
   fine for a student MVP).
3. Add the **WhatsApp** product (Set up / API Setup).
4. On **API Setup**, copy:
   - **Phone number ID** (the id string, not the human display number)
   - **Temporary access token** (expires; enough for this proof)
5. **App settings → Basic** → copy **App secret**.
6. Under API Setup, **To** → add **your personal WhatsApp number** to the
   allow-list. Meta sends a confirmation code in WhatsApp; enter it.

Until the app is live/verified, you can only message allow-listed numbers.
That is enough for P3.

## 3. Local `.env` (repo root)

```
NOMI_MESSAGING_PROVIDER=whatsapp
WHATSAPP_ACCESS_TOKEN=<temporary token>
WHATSAPP_PHONE_NUMBER_ID=<phone number id>
WHATSAPP_VERIFY_TOKEN=nomi-p3-verify
WHATSAPP_APP_SECRET=<app secret>
WHATSAPP_GRAPH_API_VERSION=v21.0
NOMI_DEMO_SENIOR_WA_ID=<your number digits, no plus, e.g. 6591234567>
```

`WHATSAPP_VERIFY_TOKEN` is invented by you. Paste the **same** string into
Meta’s webhook form.

`wa_id` is usually country code + number with no `+` or spaces. If a later
webhook `from` field differs, use that exact value.

The API loads this file at startup (`python-dotenv`). Restart uvicorn after
editing `.env`.

If `NOMI_DEMO_SENIOR_WA_ID` is set, Nomi upserts `senior-1` as a senior
contact on boot. You can also register a number at runtime:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/contacts \
  -H 'Content-Type: application/json' \
  -d '{"senior_id":"senior-1","wa_id":"6591234567","role":"senior"}'
```

## 4. Run the API and a public HTTPS tunnel

Meta will not call `localhost`.

From `apps/backend/` (with `src` on `PYTHONPATH`, e.g. `pip install -e .`
or `PYTHONPATH=src`):

```bash
uvicorn nomi_backend.api.app:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
ngrok http 8000
```

Copy the `https://<id>.ngrok-free.app` URL.

In Meta → WhatsApp → **Configuration** → Webhook:

- Callback URL: `https://<id>.ngrok-free.app/webhooks/whatsapp`
- Verify token: `nomi-p3-verify` (must match `.env`)

Subscribe the **messages** field.

If GET verification fails: port 8000 must be this FastAPI process (not
Next.js), the token must match exactly, and ngrok must still be running.

## 5. Open the 24-hour window, then prove the round trip

Cloud API `type=text` (what Nomi sends) only works after the test user has
messaged the business number, or you use an approved template.

1. From your phone, send any text to the Meta **test WhatsApp number** on
   API Setup.
2. Confirm the contact exists (`NOMI_DEMO_SENIOR_WA_ID` or the curl above).
3. Send a check-in:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/checkins \
  -H 'Content-Type: application/json' \
  -d '{"senior_id":"senior-1"}'
```

Expected: HTTP **201** with `"status":"sent"` and an `outbound_wamid`.

4. The phone should receive the Nomi check-in. Reply `4` (or any short text).
5. Success: Meta POSTs to `/webhooks/whatsapp` (200), and the in-memory
   store has a `checkin_response` with `checkin_sent_at` /
   `response_received_at` set.

Restarting uvicorn wipes the in-memory store (P6 will persist later).

## 6. When Meta blocks live sending

Development-mode apps, expired tokens, unverified businesses, and the
24-hour session window are the usual blocks.

```
NOMI_MESSAGING_PROVIDER=mock
```

Do **not** work around a Meta block with unofficial clients.

## 7. Operational notes

- **Retries:** Meta retries webhooks on non-2xx. Nomi returns 200 after a
  valid signature even when the sender is unknown.
- **Privacy:** do not log tokens, app secrets, or full inbound bodies.
- **401/403 from Graph:** rotate the token and confirm the phone-number id
  belongs to the same WhatsApp Business Account.
