# Supabase database setup

Nomi uses the Supabase PostgreSQL database through SQLAlchemy. The browser never receives
the database password; only the FastAPI backend connects to PostgreSQL.

## 1. Create the project

1. Create a Supabase project.
2. Open **Project Settings > Database** and copy the transaction-pooler connection string.
3. Replace the password placeholder and keep `sslmode=require` in the URL.

Example (do not commit the real value):

```env
DATABASE_URL=postgresql+psycopg://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:6543/postgres?sslmode=require
NOMI_DATA_MODE=database
```

## 2. Apply migrations in order

Open **SQL Editor**, then run these files from oldest to newest:

1. `infra/supabase/migrations/202608300001_baseline_layer.sql`
2. `infra/supabase/migrations/202609010001_whatsapp_checkin_pipeline.sql`
3. `infra/supabase/migrations/202609010001_verification_escalation.sql`
4. `infra/supabase/migrations/202609020001_integration_profiles_and_seed.sql`
5. `infra/supabase/migrations/202609020002_persistent_checkin_pipeline.sql`

The last two migrations align `senior_id`, add profile/consent data, make check-ins and webhook
events restart-safe, and insert idempotent demo data.

## 3. Configure each app

Backend environment:

```env
DATABASE_URL=postgresql+psycopg://...
NOMI_DATA_MODE=database
NOMI_MESSAGING_PROVIDER=mock
NOMI_CORS_ORIGINS=http://localhost:3000
WHATSAPP_APP_SECRET=local-demo-secret
```

Frontend environment:

```env
NOMI_API_BASE_URL=http://127.0.0.1:8000
```

For deployment, replace both localhost URLs with the public HTTPS frontend/backend URLs.
`NOMI_API_BASE_URL` is server-side and is the preferred frontend setting. The
`NEXT_PUBLIC_NOMI_API_BASE_URL` fallback exists only when a public browser-side URL is needed.

## 4. Verify the connection

Start FastAPI, then check:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/api/v1/seniors
```

The second response should include `Mdm Tan`, `Mr Rahman`, and `Auntie Lee`. If it returns a
500 error, check the backend terminal first. The most common causes are a missing migration,
an incorrectly encoded database password, or a connection string without `sslmode=require`.

## 5. Test the persisted pipeline

After applying migration `202609020002_persistent_checkin_pipeline.sql`, restart FastAPI and
run from the repository root:

```bash
python scripts/run_persistent_pipeline_demo.py
```

This registers mock contacts, stores a check-in, posts signed webhook replies, runs detection,
resolves verification as help-needed, sends through the mock provider, and marks the caregiver
alert delivered. Confirm new rows in `nomi_checkins`, `whatsapp_events`,
`senior_interactions`, `verification_requests`, and `caregiver_alerts`.

## 6. Safety before production

The current MVP connects through a trusted backend and does not expose Supabase directly to
the browser. Before any browser-direct Supabase access is added, enable Row Level Security and
define caregiver-specific policies. Never put the database password or service-role key in a
`NEXT_PUBLIC_*` variable.
