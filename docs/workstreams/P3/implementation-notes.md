# P3 Implementation Notes

Finish-line notes for WhatsApp Cloud API integration and the check-in pipeline.
P3 owns transport, webhook handling, and check-in bookkeeping. P4 owns
verification timing and copy. P6 owns public HTTPS, Meta app wiring, and
persisting the SQL schema.

**Design:** [specs/2026-09-01-whatsapp-checkin-design.md](specs/2026-09-01-whatsapp-checkin-design.md)
**Telegram demo:** [telegram-demo-setup.md](telegram-demo-setup.md)
**Presentation:** [presentation-demo.md](presentation-demo.md)
**Session scoring:** [session-scoring.md](session-scoring.md)
**Meta setup:** [meta-cloud-api-setup.md](meta-cloud-api-setup.md)
**Plan:** [plans/2026-09-01-whatsapp-checkin-implementation-plan.md](plans/2026-09-01-whatsapp-checkin-implementation-plan.md)

## Files changed

- `apps/backend/src/nomi_backend/messaging/` — `settings.py`, `protocol.py`,
  `mock_provider.py`, `whatsapp_cloud.py`, `factory.py`, `__init__.py`
- `apps/backend/src/nomi_backend/checkins/` — `models.py`, `wellbeing.py`,
  `store.py`, `pipeline.py`, `scheduler.py`, `sessions.py`, `semantics.py`,
  `__init__.py`
- `apps/backend/src/nomi_backend/api/app.py`
- `apps/backend/pyproject.toml` (`httpx`, `python-dotenv`, `scikit-learn`)
- `apps/backend/tests/test_messaging_settings.py`,
  `test_messaging_protocol.py`, `test_mock_provider.py`,
  `test_whatsapp_cloud.py`, `test_checkin_store.py`,
  `test_checkin_pipeline.py`, `test_whatsapp_webhook.py`,
  `test_telegram_webhook.py`, `test_checkin_api.py`, `test_p3_exports.py`,
  `test_semantics.py`, `test_scheduler.py`, `test_sessions.py`
- `infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql`
- `.env.example`
- `docs/workstreams/P3/` — design spec, implementation plan, Meta setup, this
  notes file
- `docs/workstreams/README.md`

P3 did **not** change `baseline/calculator.py`, detection, `demo_repository`,
or `202608300001_baseline_layer.sql`. The caregiver senior page has a meal
session card; dashboard charts stay on demo history.

## API routes added

- `GET /webhooks/whatsapp` — Meta hub challenge verification
- `POST /webhooks/whatsapp` — inbound Cloud API webhook (signature check +
  idempotent check-in close)
- `POST /webhooks/telegram` — Telegram Bot API webhook (secret token + text updates)
- `POST /api/v1/contacts` — demo upsert of `wa_id` → senior (role `senior` or
  `caregiver`)
- `POST /api/v1/checkins` — on-demand outbound check-in (extra ping; meal=`extra`)
- `POST /api/v1/checkins/run-due` — send the current SGT meal if not already sent
- `GET /api/v1/seniors/{id}/schedule` — next meal clock in Asia/Singapore
- `GET /api/v1/seniors/{id}/sessions/latest` — latest scored meal label + tracks

Existing `GET /api/v1/seniors*` demo-baseline routes are unchanged.

## Schema

New tables in `202609010001_whatsapp_checkin_pipeline.sql`:

- `senior_contacts`
- `nomi_checkins`
- `whatsapp_events`

`senior_id` is `text` in these tables. Runtime uses `InMemoryCheckInStore`.
The migration is for P6 to apply; P3 does not wire Supabase.

Meal session scoring also `create_all`s `checkin_sessions` and
`checkin_messages` on the SQLAlchemy engine (default SQLite
`nomi_verification.db`) so follow-up text can be stored locally.

## Environment variables

From `.env.example`:

| Variable | Role |
| --- | --- |
| `NOMI_MESSAGING_PROVIDER` | `mock` (default), `telegram` (live demo), or `whatsapp` |
| `TELEGRAM_BOT_TOKEN` | BotFather token (empty placeholder) |
| `TELEGRAM_WEBHOOK_SECRET` | POST `X-Telegram-Bot-Api-Secret-Token` check |
| `NOMI_DEMO_SENIOR_CHAT_ID` | Optional boot seed: maps this chat id to `senior-1` |
| `NOMI_DEMO_CAREGIVER_CHAT_ID` | Optional boot seed: caregiver contact for `senior-1` |
| `WHATSAPP_ACCESS_TOKEN` | Cloud API token (empty placeholder) |
| `WHATSAPP_PHONE_NUMBER_ID` | Sending phone number id |
| `WHATSAPP_VERIFY_TOKEN` | GET webhook hub.verify_token |
| `WHATSAPP_APP_SECRET` | POST `X-Hub-Signature-256` check |
| `WHATSAPP_GRAPH_API_VERSION` | Graph version (`v21.0` default) |
| `NOMI_CHECKIN_BODY` | Optional default outbound check-in body |
| `NOMI_DEMO_SENIOR_WA_ID` | Optional leftover alias for `NOMI_DEMO_SENIOR_CHAT_ID` |
| `NOMI_SCHEDULER_ENABLED` | `1` (default) runs the 60s meal loop; `0` disables it |

## Assumptions

- In-memory store at runtime until P6 wires Supabase.
- Demo GET endpoints still use `DemoBaselineRepository` (charts are canned).
- `text` vs uuid `senior_id` mismatch is deferred to P6.
- Meal follow-up bodies are stored in `checkin_messages` for session scoring.
  Live-checkin still returns only wellbeing 1–5.
- Default provider is mock.
- Official Cloud API only; no unofficial WhatsApp clients.
- Live demo uses Telegram. Meals are 08:00 / 12:30 / 18:30 Asia/Singapore.

## Tests

Unittest files listed under Files changed. From `apps/backend/`:

```
python -m unittest discover -s tests -p "test_*.py" -v
```

`test_p3_exports.py` asserts the public package imports P4 and P6 need.

## P4 integration

```python
from nomi_backend.checkins import (
    CheckInService,
    send_verification_prompt,
    send_caregiver_alert,
)
# mark_missed is CheckInService.mark_missed
```

P4 owns timeouts and copy. `send_verification_prompt` and
`send_caregiver_alert` send outbound text only; they do not create check-in
observations.

Also exported for P4: `ContactNotFound`, `InMemoryCheckInStore`,
`MessagingProvider`, `build_messaging_provider`, `MessagingSettings`.

## P6 integration

- Expose public HTTPS for `GET`/`POST /webhooks/whatsapp`.
- Apply `infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql`.
- Follow [meta-cloud-api-setup.md](meta-cloud-api-setup.md) for the Meta app,
  verify token, and Cloud API credentials.
- Keep `NOMI_MESSAGING_PROVIDER=mock` as the demo fallback when Cloud API
  credentials are not configured.
