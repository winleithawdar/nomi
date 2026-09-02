# P3 Implementation Notes

Finish-line notes for WhatsApp Cloud API integration and the check-in pipeline.
P3 owns transport, webhook handling, and check-in bookkeeping. P4 owns
verification timing and copy. P6 owns public HTTPS, Meta app wiring, and
persisting the SQL schema.

**Design:** [specs/2026-09-01-whatsapp-checkin-design.md](specs/2026-09-01-whatsapp-checkin-design.md)
**Meta setup:** [meta-cloud-api-setup.md](meta-cloud-api-setup.md)
**Plan:** [plans/2026-09-01-whatsapp-checkin-implementation-plan.md](plans/2026-09-01-whatsapp-checkin-implementation-plan.md)

## Files changed

- `apps/backend/src/nomi_backend/messaging/` — `settings.py`, `protocol.py`,
  `mock_provider.py`, `whatsapp_cloud.py`, `factory.py`, `__init__.py`
- `apps/backend/src/nomi_backend/checkins/` — `models.py`, `wellbeing.py`,
  `store.py`, `pipeline.py`, `__init__.py`
- `apps/backend/src/nomi_backend/api/app.py`
- `apps/backend/pyproject.toml` (`httpx`)
- `apps/backend/tests/test_messaging_settings.py`,
  `test_messaging_protocol.py`, `test_mock_provider.py`,
  `test_whatsapp_cloud.py`, `test_checkin_store.py`,
  `test_checkin_pipeline.py`, `test_whatsapp_webhook.py`,
  `test_checkin_api.py`, `test_p3_exports.py`
- `infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql`
- `.env.example`
- `docs/workstreams/P3/` — design spec, implementation plan, Meta setup, this
  notes file
- `docs/workstreams/README.md`

P3 did **not** change `baseline/calculator.py`, detection, `demo_repository`,
frontend, or `202608300001_baseline_layer.sql`.

## API routes added

- `GET /webhooks/whatsapp` — Meta hub challenge verification
- `POST /webhooks/whatsapp` — inbound Cloud API webhook (signature check +
  idempotent check-in close)
- `POST /api/v1/checkins` — on-demand outbound check-in

Existing `GET /api/v1/seniors*` routes are unchanged.

## Schema

New tables in `202609010001_whatsapp_checkin_pipeline.sql`:

- `senior_contacts`
- `nomi_checkins`
- `whatsapp_events`

`senior_id` is `text` in these tables. Runtime uses `InMemoryCheckInStore`.
The migration is for P6 to apply; P3 does not wire Supabase.

## Environment variables

From `.env.example`:

| Variable | Role |
| --- | --- |
| `NOMI_MESSAGING_PROVIDER` | `mock` (default) or `whatsapp` |
| `WHATSAPP_ACCESS_TOKEN` | Cloud API token (empty placeholder) |
| `WHATSAPP_PHONE_NUMBER_ID` | Sending phone number id |
| `WHATSAPP_VERIFY_TOKEN` | GET webhook hub.verify_token |
| `WHATSAPP_APP_SECRET` | POST `X-Hub-Signature-256` check |
| `WHATSAPP_GRAPH_API_VERSION` | Graph version (`v21.0` default) |
| `NOMI_CHECKIN_BODY` | Optional default outbound check-in body |

## Assumptions

- In-memory store at runtime until P6 wires Supabase.
- Demo GET endpoints still use `DemoBaselineRepository`.
- `text` vs uuid `senior_id` mismatch is deferred to P6.
- No message bodies are stored (wellbeing is parsed in memory, then text is
  dropped).
- Default provider is mock.
- Official Cloud API only; no unofficial WhatsApp clients.

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
