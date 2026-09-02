# P3 — Meta WhatsApp Cloud API Setup

Team checklist for the **official** WhatsApp Business Platform / Cloud API.
P3 code talks to Graph API only. Do not use WhatsApp Web scraping, Selenium,
or unofficial personal-account libraries.

Companion docs:

- Brief: [p3-whatsapp-integration.md](../p3-whatsapp-integration.md)
- Design: [specs/2026-09-01-whatsapp-checkin-design.md](specs/2026-09-01-whatsapp-checkin-design.md)
- Implementation plan: [plans/2026-09-01-whatsapp-checkin-implementation-plan.md](plans/2026-09-01-whatsapp-checkin-implementation-plan.md)

P6 owns the public HTTPS URL and production secret injection. P3 owns the
callback path (`/webhooks/whatsapp`) and the env var names.

## 1. What you need from Meta

| Item | Env var | Where it appears in Meta |
|---|---|---|
| Permanent or temporary access token | `WHATSAPP_ACCESS_TOKEN` | WhatsApp → API Setup / System User token |
| Phone number ID | `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp → API Setup (not the display number) |
| App secret | `WHATSAPP_APP_SECRET` | App settings → Basic |
| Webhook verify token | `WHATSAPP_VERIFY_TOKEN` | You invent this string; paste the same value into Meta and `.env` |
| Graph API version | `WHATSAPP_GRAPH_API_VERSION` | Default `v21.0` |
| Provider switch | `NOMI_MESSAGING_PROVIDER` | `whatsapp` or `mock` |

Copy placeholders from the repo-root `.env.example`. Never commit a filled
`.env`.

## 2. Create the Cloud API app

1. In [Meta for Developers](https://developers.facebook.com/), create an app
   (type **Business**) and add the **WhatsApp** product.
2. Attach a Meta Business portfolio if prompted.
3. Under WhatsApp → **API Setup**, note:
   - Phone number ID
   - WhatsApp Business Account ID (not required by P3 code; useful for Meta UI)
   - Temporary access token (good for local proof; expires)
4. For anything longer than a demo spike, create a **system user** in
   Business Settings, grant WhatsApp permissions, generate a token, and use
   that as `WHATSAPP_ACCESS_TOKEN`.
5. Add a test recipient number in the API Setup allow-list while the app is
   in development mode. Production sending to arbitrary numbers requires
   Meta business verification and a production phone number — P6 tracks that
   gate.

Official send endpoint P3 uses:

```
POST https://graph.facebook.com/{version}/{phone-number-id}/messages
Authorization: Bearer {access-token}
```

Body shape (text only for MVP):

```json
{
  "messaging_product": "whatsapp",
  "to": "<wa_id or E.164 digits>",
  "type": "text",
  "text": { "body": "..." }
}
```

## 3. Configure the webhook (needs P6 HTTPS)

Meta will only subscribe a callback that is **public HTTPS**. Localhost
does not work unless you tunnel (ngrok or similar) for development.

1. Deploy or tunnel FastAPI so this URL is reachable:
   `https://<host>/webhooks/whatsapp`
2. In Meta → WhatsApp → **Configuration** → Webhook:
   - Callback URL: that HTTPS URL
   - Verify token: the same string as `WHATSAPP_VERIFY_TOKEN`
3. Meta sends `GET` with `hub.mode=subscribe`, `hub.verify_token`,
   `hub.challenge`. Nomi returns the challenge as plain text when the token
   matches.
4. Subscribe the **messages** field on the WhatsApp Business Account.
5. After subscribe, Meta `POST`s JSON to the same path. Nomi checks
   `X-Hub-Signature-256` using `WHATSAPP_APP_SECRET`.

If verification fails: confirm the process serving `/webhooks/whatsapp` is
the Nomi backend (not the Next.js app), TLS is valid, and
`WHATSAPP_VERIFY_TOKEN` matches Meta exactly (no trailing newline).

## 4. Map a test senior

P3 will not auto-create seniors from inbound chat. Seed a contact (in-memory
for local mock/demo; SQL `senior_contacts` after P6 applies the migration):

| senior_id | wa_id | role |
|---|---|---|
| `senior-1` | the test handset's WhatsApp id (usually digits, no `+`) | `senior` |
| `senior-1` | caregiver handset wa_id | `caregiver` |

`wa_id` in webhooks is typically the digits Meta sends in `messages[].from`.
Use that exact value in the contact row.

## 5. Prove the round trip

1. Set `NOMI_MESSAGING_PROVIDER=whatsapp` and the four WhatsApp env vars.
2. `POST /api/v1/checkins` with `{"senior_id": "senior-1"}`.
3. Confirm the test handset receives the check-in text.
4. Reply `4` (or any short text).
5. Confirm the webhook logs a 200 and the store now has a
   `checkin_response` `SeniorInteraction` with `checkin_sent_at` /
   `response_received_at` set.

## 6. When Meta blocks live sending

Development-mode apps, expired tokens, unverified businesses, and template
restrictions outside the 24-hour customer-care window are the usual blocks.

Flip the backend:

```
NOMI_MESSAGING_PROVIDER=mock
```

`MockMessagingProvider` records outbound sends in memory and returns fake
`mock-wamid-*` ids. Tests inject inbound messages through
`CheckInService.handle_inbound_message` without Graph. P6 can keep this
fallback for the live presentation if WhatsApp is unavailable.

Do **not** work around a Meta block with unofficial clients.

## 7. Operational notes

- **24-hour window:** after a user messages the business, session messages
  are allowed for 24 hours. Outbound check-ins to a user who has never
  messaged the business number may require an approved template. MVP demo
  should have the test user message Nomi once first, or use a template P6
  registers. P3's provider sends `type=text` only; template sends are a
  follow-up if the demo cannot stay inside the session window.
- **Retries:** Meta retries webhooks on non-2xx. Nomi returns 200 after a
  valid signature even when the sender is unknown, so duplicates must be
  idempotent on `wamid`.
- **Privacy:** do not log access tokens, app secrets, or full inbound
  message bodies. Wellbeing parse uses the body in memory and discards it.
- **Scopes:** the token must be able to send WhatsApp messages for the
  phone-number id. If Graph returns 401/403, rotate the token and confirm
  the phone-number id belongs to the same WABA.

## 8. Local development without Meta

```
NOMI_MESSAGING_PROVIDER=mock
WHATSAPP_VERIFY_TOKEN=dev-verify
WHATSAPP_APP_SECRET=dev-secret
```

Webhook GET/POST signature tests use these fake values. Outbound
`POST /api/v1/checkins` succeeds without network. This is the default so
`unittest` does not need credentials.
