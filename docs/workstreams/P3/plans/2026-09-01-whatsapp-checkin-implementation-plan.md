# P3 WhatsApp Check-In Implementation Plan

> **For agentic workers:** Implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking. Follow existing backend conventions. Do not
> skip tests.

**Goal:** Connect Nomi to the official WhatsApp Cloud API, own webhook
verification and inbound handling, send outbound text, map `wa_id` to seniors,
store check-ins with timestamps and Meta message IDs, and turn senior replies
into `SeniorInteraction` records the baseline layer already consumes.

**Architecture:** A `nomi_backend.messaging` package holds a Meta-free
`MessagingProvider` protocol, env-based settings, a mock provider, and a
Graph API provider. A `nomi_backend.checkins` package holds contacts,
check-in state, inbound idempotency, optional 1–5 wellbeing parsing, and a
`CheckInService` that orchestrates send → store → reply → `SeniorInteraction`.
FastAPI gains `GET/POST /webhooks/whatsapp` and `POST /api/v1/checkins`.
A SQL migration is committed for P6; runtime tests use an in-memory store.

**Tech Stack:** Python 3.11+, FastAPI, `httpx` (Graph API), stdlib
`hmac`/`hashlib`/`dataclasses`/`enum`/`unittest`/`unittest.mock`. Official
Cloud API only. No unofficial WhatsApp clients.

**Spec:** [docs/workstreams/P3/specs/2026-09-01-whatsapp-checkin-design.md](../specs/2026-09-01-whatsapp-checkin-design.md)

**Meta setup:** [docs/workstreams/P3/meta-cloud-api-setup.md](../meta-cloud-api-setup.md)

## Global Constraints

- **Python floor:** `>=3.11` (from `apps/backend/pyproject.toml`). No 3.12+-only
  syntax. `X | None` unions are fine.
- **Additive only.** Do **not** modify `baseline/calculator.py`,
  `baseline/models.py`, `detection/**`, `services/demo_repository.py`,
  `apps/frontend/**`, `infra/supabase/migrations/202608300001_baseline_layer.sql`,
  or root `README.md` except if a one-line status mention is requested later
  (not in this plan). `api/app.py` and `pyproject.toml` **are** modified.
- **Never `git commit`** (project rule). Every task's final step stages with
  `git add` and stops. The user commits.
- **Style match `nomi_backend/baseline/`:** `from __future__ import annotations`
  at top of every module; `@dataclass(frozen=True)` for value types; `str`-valued
  `Enum`s; module-level constants in `UPPER_SNAKE`.
- **No secrets in code or docs.** Placeholders only in `.env.example`.
- **No message bodies** on `SeniorInteraction` or check-in persistence. Parse
  wellbeing in memory, then drop the text.
- **No numeric risk/concern score.** P3 does not call detectors and does not
  invent scores.
- **Test runner (from `apps/backend/`):**
  - Single file: `python tests/test_whatsapp_cloud.py -v`
  - Full suite: `python -m unittest discover -s tests -p "test_*.py" -v`
- **Test file preamble** (every new test file starts with this, matching
  `tests/test_baseline.py`):
  ```python
  from __future__ import annotations

  import sys
  import unittest
  from pathlib import Path

  sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
  ```

---

## File Structure

| File | Responsibility |
|---|---|
| `apps/backend/src/nomi_backend/messaging/__init__.py` | Public messaging exports |
| `apps/backend/src/nomi_backend/messaging/protocol.py` | `Recipient`, `OutboundMessage`, `MessagingProvider`, `MessagingError`, `ContactRole` |
| `apps/backend/src/nomi_backend/messaging/settings.py` | `MessagingSettings.from_env()` |
| `apps/backend/src/nomi_backend/messaging/mock_provider.py` | In-memory `MockMessagingProvider` |
| `apps/backend/src/nomi_backend/messaging/whatsapp_cloud.py` | Graph API `WhatsAppCloudProvider` |
| `apps/backend/src/nomi_backend/messaging/factory.py` | `build_messaging_provider(settings)` |
| `apps/backend/src/nomi_backend/checkins/__init__.py` | Public check-in exports |
| `apps/backend/src/nomi_backend/checkins/models.py` | `CheckIn`, `CheckInStatus`, `SeniorContact`, `WhatsAppEvent` |
| `apps/backend/src/nomi_backend/checkins/wellbeing.py` | `parse_wellbeing_score(text) -> float \| None` |
| `apps/backend/src/nomi_backend/checkins/store.py` | `CheckInStore` protocol + `InMemoryCheckInStore` |
| `apps/backend/src/nomi_backend/checkins/pipeline.py` | `CheckInService` + P4 helpers |
| `apps/backend/src/nomi_backend/api/app.py` | **Modify:** webhook routes + `POST /api/v1/checkins` |
| `apps/backend/pyproject.toml` | **Modify:** add `httpx` |
| `infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql` | `senior_contacts`, `nomi_checkins`, `whatsapp_events` |
| `.env.example` | Placeholder env vars |
| `apps/backend/tests/test_messaging_settings.py` | Settings / env |
| `apps/backend/tests/test_messaging_protocol.py` | Protocol types |
| `apps/backend/tests/test_mock_provider.py` | Mock provider |
| `apps/backend/tests/test_whatsapp_cloud.py` | Graph client with httpx mocked |
| `apps/backend/tests/test_checkin_store.py` | Store + idempotency |
| `apps/backend/tests/test_checkin_pipeline.py` | Send / reply / missed |
| `apps/backend/tests/test_whatsapp_webhook.py` | GET challenge + POST signature |

---

## Task 1: Settings + `.env.example`

**Files:**
- Create: `apps/backend/src/nomi_backend/messaging/__init__.py`
- Create: `apps/backend/src/nomi_backend/messaging/settings.py`
- Create: `.env.example` (repo root)
- Test: `apps/backend/tests/test_messaging_settings.py`

**Interfaces:**
- Consumes: `os.environ`.
- Produces: `@dataclass(frozen=True) MessagingSettings` with fields
  `provider: str`, `access_token: str`, `phone_number_id: str`,
  `verify_token: str`, `app_secret: str`, `graph_api_version: str`,
  `default_checkin_body: str`.
- `MessagingSettings.from_env() -> MessagingSettings`.
- Defaults: `provider="mock"`, `graph_api_version="v21.0"`,
  `default_checkin_body` = the spec's gentle check-in copy.
- If `provider == "whatsapp"`, require `WHATSAPP_ACCESS_TOKEN` and
  `WHATSAPP_PHONE_NUMBER_ID`; raise `RuntimeError` naming the missing
  variable, never interpolating its value.
- Webhook fields (`verify_token`, `app_secret`) may be empty strings in mock
  mode.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_messaging_settings.py`:

```python
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.messaging.settings import MessagingSettings


class MessagingSettingsTest(unittest.TestCase):
    def test_defaults_to_mock_provider(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = MessagingSettings.from_env()
        self.assertEqual(settings.provider, "mock")
        self.assertEqual(settings.graph_api_version, "v21.0")
        self.assertIn("Nomi", settings.default_checkin_body)

    def test_whatsapp_provider_requires_token_and_phone_id(self) -> None:
        env = {"NOMI_MESSAGING_PROVIDER": "whatsapp"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as raised:
                MessagingSettings.from_env()
        self.assertIn("WHATSAPP_ACCESS_TOKEN", str(raised.exception))

    def test_whatsapp_provider_loads_credentials(self) -> None:
        env = {
            "NOMI_MESSAGING_PROVIDER": "whatsapp",
            "WHATSAPP_ACCESS_TOKEN": "token-placeholder",
            "WHATSAPP_PHONE_NUMBER_ID": "123456",
            "WHATSAPP_VERIFY_TOKEN": "verify-placeholder",
            "WHATSAPP_APP_SECRET": "secret-placeholder",
            "WHATSAPP_GRAPH_API_VERSION": "v21.0",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = MessagingSettings.from_env()
        self.assertEqual(settings.provider, "whatsapp")
        self.assertEqual(settings.access_token, "token-placeholder")
        self.assertEqual(settings.phone_number_id, "123456")
        self.assertEqual(settings.verify_token, "verify-placeholder")
        self.assertEqual(settings.app_secret, "secret-placeholder")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_messaging_settings.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.messaging'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/messaging/__init__.py`:

```python
from __future__ import annotations

from .settings import MessagingSettings

__all__ = ["MessagingSettings"]
```

Create `apps/backend/src/nomi_backend/messaging/settings.py` implementing
`from_env()` as specified. Default check-in body:

```text
Hi, this is Nomi checking in. How are you today? Reply with a number from 1 (low) to 5 (good), or any short reply so we know you saw this.
```

Create repo-root `.env.example`:

```
NOMI_MESSAGING_PROVIDER=mock
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_APP_SECRET=
WHATSAPP_GRAPH_API_VERSION=v21.0
NOMI_CHECKIN_BODY=
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_messaging_settings.py -v`

Expected: PASS.

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/messaging/__init__.py \
        apps/backend/src/nomi_backend/messaging/settings.py \
        apps/backend/tests/test_messaging_settings.py \
        .env.example
```

Do not commit — leave that to the user (project rule).

---

## Task 2: Messaging protocol types

**Files:**
- Create: `apps/backend/src/nomi_backend/messaging/protocol.py`
- Modify: `apps/backend/src/nomi_backend/messaging/__init__.py`
- Test: `apps/backend/tests/test_messaging_protocol.py`

**Interfaces:**
- `ContactRole` enum: `SENIOR="senior"`, `CAREGIVER="caregiver"`.
- Frozen `Recipient(senior_id: str | None, wa_id: str, role: ContactRole)`.
- Frozen `OutboundMessage(provider_message_id: str, recipient: Recipient, sent_at: datetime, correlation_id: str | None)`.
- `class MessagingError(Exception)`.
- `class MessagingProvider(Protocol)` with `send_text(self, recipient, body, *, correlation_id: str | None = None) -> OutboundMessage`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_messaging_protocol.py` asserting enum values,
that `Recipient` / `OutboundMessage` are frozen (assignment raises
`FrozenInstanceError` / `AttributeError`), and that `MessagingError` is an
`Exception`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_messaging_protocol.py -v`

Expected: FAIL — cannot import protocol names from `nomi_backend.messaging`.

- [ ] **Step 3: Write minimal implementation**

Implement `protocol.py` and export the types from `__init__.py`.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS.

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/messaging/protocol.py \
        apps/backend/src/nomi_backend/messaging/__init__.py \
        apps/backend/tests/test_messaging_protocol.py
```

Do not commit.

---

## Task 3: Mock provider + factory

**Files:**
- Create: `apps/backend/src/nomi_backend/messaging/mock_provider.py`
- Create: `apps/backend/src/nomi_backend/messaging/factory.py`
- Modify: `apps/backend/src/nomi_backend/messaging/__init__.py`
- Test: `apps/backend/tests/test_mock_provider.py`

**Interfaces:**
- `MockMessagingProvider.send_text` appends to `self.sent: list[OutboundMessage]`,
  assigns `provider_message_id=f"mock-wamid-{n}"` starting at 1, `sent_at` timezone-aware UTC.
- `build_messaging_provider(settings) -> MessagingProvider`: `mock` → mock;
  `whatsapp` → `WhatsAppCloudProvider` (import inside the branch so Task 3
  can still construct mock without the Graph client existing — or stub the
  whatsapp branch to raise `NotImplementedError` until Task 4).
- Unknown `settings.provider` → `ValueError`.

- [ ] **Step 1: Write the failing test**

Cover: two sends produce `mock-wamid-1` then `mock-wamid-2`; `correlation_id`
is stored; `sent` list length matches; `build_messaging_provider` with
`provider="mock"` returns `MockMessagingProvider`; unknown provider raises
`ValueError`.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/messaging/mock_provider.py \
        apps/backend/src/nomi_backend/messaging/factory.py \
        apps/backend/src/nomi_backend/messaging/__init__.py \
        apps/backend/tests/test_mock_provider.py
```

Do not commit.

---

## Task 4: WhatsApp Cloud provider (httpx mocked)

**Files:**
- Modify: `apps/backend/pyproject.toml` (add `"httpx>=0.27,<1.0"` to dependencies)
- Create: `apps/backend/src/nomi_backend/messaging/whatsapp_cloud.py`
- Modify: `apps/backend/src/nomi_backend/messaging/factory.py` (wire `whatsapp`)
- Test: `apps/backend/tests/test_whatsapp_cloud.py`

**Interfaces:**
- `WhatsAppCloudProvider(settings: MessagingSettings, *, client: httpx.Client | None = None)`.
- `send_text` POSTs to
  `https://graph.facebook.com/{graph_api_version}/{phone_number_id}/messages`
  with headers `Authorization: Bearer {access_token}` and
  `Content-Type: application/json`.
- JSON body:
  ```json
  {
    "messaging_product": "whatsapp",
    "to": "<recipient.wa_id>",
    "type": "text",
    "text": {"body": "<body>"}
  }
  ```
- Success: parse `messages[0].id` as `provider_message_id`.
- Non-2xx or missing id: raise `MessagingError` (no token in the message).
- Inject `client` in tests; production constructs `httpx.Client(timeout=10.0)`.

- [ ] **Step 1: Write the failing test**

Use `unittest.mock.Mock` as `client`. `client.post.return_value` has
`status_code=200`, `json.return_value={"messages": [{"id": "wamid.abc"}]}`.
Assert URL, Authorization header, JSON `to` / `text.body`.
A 400 response raises `MessagingError`.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — module missing.

- [ ] **Step 3: Add `httpx` and write the client**

Install is local (`pip install httpx` in the backend env if needed). Pin in
`pyproject.toml`.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: PASS (existing tests plus messaging).

- [ ] **Step 6: Stage the changes**

```bash
git add apps/backend/pyproject.toml \
        apps/backend/src/nomi_backend/messaging/whatsapp_cloud.py \
        apps/backend/src/nomi_backend/messaging/factory.py \
        apps/backend/tests/test_whatsapp_cloud.py
```

Do not commit.

---

## Task 5: Check-in models, wellbeing parse, in-memory store

**Files:**
- Create: `apps/backend/src/nomi_backend/checkins/__init__.py`
- Create: `apps/backend/src/nomi_backend/checkins/models.py`
- Create: `apps/backend/src/nomi_backend/checkins/wellbeing.py`
- Create: `apps/backend/src/nomi_backend/checkins/store.py`
- Create: `infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql`
- Test: `apps/backend/tests/test_checkin_store.py`

**Interfaces:**
- `CheckInStatus`: `SENT="sent"`, `RESPONDED="responded"`, `MISSED="missed"`.
- Frozen `SeniorContact(senior_id, wa_id, role: ContactRole, phone_e164: str | None = None)`.
- Frozen `CheckIn` with fields from the spec (`id`, `senior_id`, `sent_at`,
  `outbound_wamid`, `status`, `response_wamid`, `response_received_at`,
  `wellbeing_score`). Because it is frozen, the store replaces rows rather
  than mutating them.
- Frozen `WhatsAppEvent(inbound_wamid, wa_id, received_at, checkin_id, ignored_reason)`.
- `parse_wellbeing_score(text: str | None) -> float | None`: stripped exact
  `1`–`5` only.
- `InMemoryCheckInStore` implements the protocol in the spec.
  `record_inbound_event` returns `False` on duplicate `inbound_wamid`.
  `get_open_checkin` returns the latest `status=sent` for that senior, or `None`.
  `interactions_for` maps `responded` → `checkin_response` and `missed` →
  `checkin_missed` `SeniorInteraction` with `source="nomi"`.

**SQL migration** creates `senior_contacts`, `nomi_checkins`, `whatsapp_events`
as in the spec (text `senior_id`, unique `wa_id`, unique `inbound_wamid`).
Do not touch the baseline-layer migration.

- [ ] **Step 1: Write the failing test**

Cover: upsert + get by wa_id; unknown wa_id is `None`; duplicate event
returns `False` the second time; `interactions_for` empty until a responded
or missed check-in exists; wellbeing parse ` " 3 " ` → `3.0`, `"ok"` →
`None`, `None` → `None`.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — package missing.

- [ ] **Step 3: Write minimal implementation + migration**

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/checkins \
        apps/backend/tests/test_checkin_store.py \
        infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql
```

Do not commit.

---

## Task 6: Check-in pipeline (send, reply, missed)

**Files:**
- Create: `apps/backend/src/nomi_backend/checkins/pipeline.py`
- Modify: `apps/backend/src/nomi_backend/checkins/__init__.py`
- Test: `apps/backend/tests/test_checkin_pipeline.py`

**Interfaces:**
- `CheckInService(store, provider, settings)`.
- `send_checkin(senior_id, *, body=None) -> CheckIn` per spec: resolve senior
  contact, reuse existing open check-in, send then persist `status=sent`.
  Missing contact → `ContactNotFound` (domain exception in `pipeline.py` or
  `models.py`). Provider failure → do not persist an open check-in.
- `handle_inbound_message(wa_id, wamid, received_at, text) -> SeniorInteraction | None`
  per spec.
- `mark_missed(checkin_id, *, as_of) -> SeniorInteraction`.
- `send_verification_prompt(service, senior_id, body) -> OutboundMessage`.
- `send_caregiver_alert(service, caregiver_senior_id, body) -> OutboundMessage`
  looks up `role=caregiver`.

Seed the store in tests with:

```python
store.upsert_contact(SeniorContact("senior-1", "6581111111", ContactRole.SENIOR))
store.upsert_contact(SeniorContact("senior-1", "6582222222", ContactRole.CAREGIVER))
```

- [ ] **Step 1: Write the failing test**

Required cases:
1. Send then inbound reply `"4"` → interaction with latency minutes matching
   `received_at - sent_at`, `wellbeing_score=4.0`, `checkin_id` set,
   `source="nomi"`.
2. Duplicate `wamid` → second call returns `None`; still one interaction.
3. Unknown `wa_id` → `None`.
4. Second `send_checkin` while open returns the same check-in id (no extra send).
5. `mark_missed` → `missed_checkin=True`, no `response_received_at`.
6. Free-text `"I'm fine"` → interaction stored, `wellbeing_score is None`.
7. `send_caregiver_alert` uses caregiver `wa_id` `6582222222`.
8. Provider `MessagingError` → no open check-in afterwards.

Use `MockMessagingProvider` and a fixed `datetime` via an optional
`clock` callable on `CheckInService` (`lambda: datetime(...)`) so tests are
deterministic. If adding `clock` , default it to
`lambda: datetime.now(timezone.utc)`.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `CheckInService` missing.

- [ ] **Step 3: Write minimal implementation**

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/checkins/pipeline.py \
        apps/backend/src/nomi_backend/checkins/__init__.py \
        apps/backend/tests/test_checkin_pipeline.py
```

Do not commit.

---

## Task 7: Webhook GET verification + POST signature

**Files:**
- Modify: `apps/backend/src/nomi_backend/api/app.py`
- Test: `apps/backend/tests/test_whatsapp_webhook.py`

**Interfaces:**
- Construct `MessagingSettings.from_env()`, `build_messaging_provider`,
  `InMemoryCheckInStore`, and `CheckInService` at module level (same pattern
  as today's `repository = DemoBaselineRepository()`). For tests, import the
  handlers and/or use `fastapi.testclient.TestClient`.
- `GET /webhooks/whatsapp`: compare `hub.verify_token` to
  `settings.verify_token`; return `PlainTextResponse(challenge)` or 403.
- Helper `verify_meta_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool`
  lives in `messaging/whatsapp_cloud.py` or `checkins/pipeline.py`. Compare
  using `hmac.compare_digest`. Expected header format `sha256=<hex>`.
- `POST /webhooks/whatsapp`: 403 on bad/missing signature when `app_secret`
  is non-empty. On success, parse messages and call `handle_inbound_message`.
  Always 200 `{"ok": true}` after a valid signature.
- Ignore `statuses` arrays.

Prefer `TestClient` here because signature tests need the raw body. Existing
anomaly tests that call handlers directly must keep passing — do not break
`get_latest_anomaly`.

Seed the module-level store in tests by calling
`app.store.upsert_contact(...)` if `store` is exported from `app.py`, or
add a test-only reset helper. Exporting `store` and `checkin_service` from
`app.py` is acceptable.

- [ ] **Step 1: Write the failing test**

Cases:
1. GET with matching verify token returns the challenge string and 200.
2. GET with wrong token returns 403.
3. POST with valid HMAC and a text message for a known senior with an open
   check-in creates an interaction.
4. POST with invalid HMAC returns 403 and creates no interaction.
5. POST valid signature + duplicate `wamid` still 200.
6. POST valid signature + `statuses` only still 200, no interaction.

HMAC helper for tests:

```python
import hashlib
import hmac

def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"
```

Patch env so `from_env()` sees a known `WHATSAPP_APP_SECRET` and
`WHATSAPP_VERIFY_TOKEN`. Because `app.py` currently imports at module load,
construct the TestClient **after** patching env, or load settings inside
the request handlers via a getter. **Preferred:** lazy `get_settings()` so
tests can patch env without reimport tricks.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — route missing or 404.

- [ ] **Step 3: Write routes + signature helper**

Keep existing GET `/api/v1/seniors*` routes unchanged.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Run the full suite**

Expected: PASS, including `test_anomaly_detector.py`.

- [ ] **Step 6: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/api/app.py \
        apps/backend/src/nomi_backend/messaging/whatsapp_cloud.py \
        apps/backend/tests/test_whatsapp_webhook.py
```

Do not commit.

---

## Task 8: Outbound check-in HTTP route

**Files:**
- Modify: `apps/backend/src/nomi_backend/api/app.py`
- Modify: `apps/backend/tests/test_whatsapp_webhook.py` (or new
  `test_checkin_api.py` if the webhook file is getting large)

**Interfaces:**
- `POST /api/v1/checkins` JSON `{"senior_id": str, "body": str | optional}`.
- 201 `{id, senior_id, status, sent_at, outbound_wamid}`.
- 404 `{"detail": "Senior not found."}` on `ContactNotFound` (match existing
  404 wording style).
- 503 on `MessagingError`.

- [ ] **Step 1: Write the failing test**

Seed a senior contact on the app store. POST `{"senior_id": "senior-1"}`.
Expect 201 and `status == "sent"`. Unknown senior → 404.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — 404/405 on the new path.

- [ ] **Step 3: Implement the route**

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/api/app.py \
        apps/backend/tests/test_whatsapp_webhook.py
```

Do not commit.

---

## Task 9: Package exports + finish-line implementation note

**Files:**
- Modify: messaging and checkins `__init__.py` so P4 can import:
  `CheckInService`, `InMemoryCheckInStore`, `send_verification_prompt`,
  `send_caregiver_alert`, `ContactNotFound`, `MessagingProvider`,
  `build_messaging_provider`, `MessagingSettings`.
- Create: `docs/workstreams/P3/implementation-notes.md` with files changed,
  routes, migration, env vars, assumptions, tests, and P4/P6 integration
  (the brief's finish-line documentation).

- [ ] **Step 1: Confirm public imports**

Add a short test in `test_checkin_pipeline.py` (or protocol test) that
`from nomi_backend.checkins import CheckInService, send_caregiver_alert`
and `from nomi_backend.messaging import build_messaging_provider` work.

- [ ] **Step 2: Run the full suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: PASS.

- [ ] **Step 3: Write `docs/workstreams/P3/implementation-notes.md`**

Include:
- files changed
- API/schema changes
- environment variables
- assumptions (in-memory store at runtime until P6 wires Supabase; demo
  GET endpoints unchanged; text vs uuid `senior_id`)
- tests added
- how P4 calls helpers
- how P6 should expose `/webhooks/whatsapp` and apply the migration

- [ ] **Step 4: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/messaging/__init__.py \
        apps/backend/src/nomi_backend/checkins/__init__.py \
        apps/backend/tests \
        docs/workstreams/P3/implementation-notes.md
```

Do not commit.

---

## Post-Implementation

- [ ] Confirm `git status` shows only P3 files: `messaging/`, `checkins/`,
  `api/app.py`, `pyproject.toml`, new tests, `.env.example`, the new SQL
  migration, and `docs/workstreams/P3/**`. No edits to
  `baseline/calculator.py`, `detection/**`, `demo_repository.py`, frontend,
  or `202608300001_baseline_layer.sql`.
- [ ] Confirm no secrets in the diff (`git grep` for real tokens should be
  empty; `.env.example` has empty placeholders).
- [ ] Hand off to the user for commit. Point P4 at `CheckInService` helpers
  and P6 at [meta-cloud-api-setup.md](../meta-cloud-api-setup.md).
