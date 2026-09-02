# Nomi

AI-powered senior-care support focused on detecting meaningful changes from each senior's own normal pattern.

## Repository Layout

```text
nomi/
├── apps/
│   ├── backend/        # FastAPI pipeline, detection, verification and persistence
│   └── frontend/       # Next.js caregiver dashboard
├── docs/
│   └── architecture/   # Product and technical design notes
└── infra/
    └── supabase/       # Database migrations and infrastructure assets
```

## Current Status

The repository includes an integrated MVP slice:

- personal baseline plus anomaly and longitudinal change detection
- senior-first verification and deterministic caregiver escalation
- Telegram Bot API live demo plus mock-provider fallback (WhatsApp Cloud API remains in the codebase)
- caregiver dashboard connected to FastAPI
- Supabase migrations and deterministic demo data

## Local run

```bash
cd apps/backend
python -m pip install -e .
uvicorn nomi_backend.api:app --reload
```

In a second terminal:

```bash
cd apps/frontend
npm ci
npm run dev
```

Open `http://localhost:3000`. The default `NOMI_DATA_MODE=demo` works without Supabase.
See `docs/database-setup.md` to switch to PostgreSQL, and run the full demo from the repo root:

```bash
python scripts/run_demo_scenario.py --outcome no-response
```
