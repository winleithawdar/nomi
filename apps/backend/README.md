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

## Run API

```bash
pip install -e .
uvicorn nomi_backend.api:app --reload
```

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./nomi_verification.db` | SQLAlchemy connection for verification/alert persistence |

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
| `GET` | `/api/v1/verifications/{id}/check-in-message` | P3: outbound senior check-in text |
| `GET` | `/api/v1/alerts` | P5: dashboard alert feed (optional filters) |
| `GET` | `/api/v1/alerts/{id}/caregiver-message` | P3: outbound caregiver alert text |
| `GET` | `/api/v1/alerts/{id}` | Alert detail |
| `POST` | `/api/v1/alerts/{id}/delivered` | P3: mark alert delivered |

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
