# Nomi

AI-powered senior-care support that learns each person's own usual pattern, then notices meaningful changes from that personal baseline.

Nomi does not diagnose illness. The first product slices are **Learn** (personal baseline) and **Notice** (explainable change from usual). Verify and caregiver escalation are intentionally not part of this slice.

## Repository layout

```text
nomi/
├── apps/
│   ├── backend/        # FastAPI + baseline + notice logic
│   └── frontend/       # Next.js caregiver dashboard
├── docs/
│   └── architecture/   # Product and technical design notes
└── infra/
    └── supabase/       # Database migrations
```

## Current status

- Personal baseline from Nomi check-ins: response latency, missed check-ins, interaction frequency, and optional wellbeing
- Explainable notice layer that compares latest observations with each senior's own baseline
- Demo FastAPI API with in-memory seniors (Mdm Tan, Mr Rahman, Auntie Lee)
- Caregiver dashboard for overview and per-senior baseline views
- Supabase migration for interaction storage and baseline snapshots

## Run locally

You need Node.js 20+ and Python 3.11+.

### 1. Backend API (port 43124)

```bash
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover tests
uvicorn nomi_backend.api.app:app --host 127.0.0.1 --port 43124 --reload
```

### 2. Caregiver dashboard (port 43123)

In a second terminal:

```bash
cd apps/frontend
cp .env.example .env.local
npm install
npm run dev -- --port 43123 --hostname 127.0.0.1
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123). The home page redirects to the caregiver overview.

## Product pipeline

1. **Learn** — build a personal baseline from Nomi interactions
2. **Notice** — describe sudden or gradual change against that baseline
3. **Verify** — check with the senior before alarming anyone (not in this slice)
4. **Support** — notify the caregiver with context if concern remains (not in this slice)
