# Nomi Demo Guide

How to run and present the Nomi MVP: a WhatsApp-first caregiver support system that
learns each senior’s personal behavioural baseline and notices meaningful deviations.

**Core flow:** `LEARN → NOTICE → VERIFY → SUPPORT`

This guide matches the merged `main` branch and the Team 404 proposal features:

1. Personal Behaviour Model
2. Progressive Verification
3. Contextual Caregiver Alerts
4. Consent and Privacy by Design

For the storyline judges should hear, see [`SCENARIO.md`](./SCENARIO.md).

---

## 1. What you need

| Component | Role |
|---|---|
| FastAPI backend | Baseline, detection, verification, WhatsApp webhook, alerts |
| Next.js frontend | Caregiver dashboard |
| Mock messaging (default) | Demo without real Meta WhatsApp credentials |
| Optional Supabase | Persistent PostgreSQL when `NOMI_DATA_MODE=database` |

Default demo mode works **without Supabase**.

---

## 2. Quick start (local)

From the repo root:

### Step A — Environment

```bash
cp .env.example .env
```

Keep these defaults for a local demo:

```env
NOMI_MESSAGING_PROVIDER=mock
NOMI_DATA_MODE=demo
DATABASE_URL=sqlite:///./nomi_verification.db
NOMI_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
NOMI_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_NOMI_API_BASE_URL=http://127.0.0.1:8000
WHATSAPP_APP_SECRET=local-demo-secret
```

### Step B — Backend

```bash
cd apps/backend
python -m pip install -e .
uvicorn nomi_backend.api:app --reload
```

Check health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Step C — Frontend

In a second terminal:

```bash
cd apps/frontend
# create .env.local with: NOMI_API_BASE_URL=http://127.0.0.1:8000
npm ci
npm run dev
```

Open the caregiver dashboard: [http://localhost:3000](http://localhost:3000)

### Step D — Run the scripted demo

With backend running, from the **repo root**:

```bash
# Full path: detection → verification → caregiver alert (no-response branch)
python scripts/run_demo_scenario.py --outcome no-response

# Or show a senior resolving concern without alerting caregiver
python scripts/run_demo_scenario.py --outcome reassuring

# Or show senior asking for help
python scripts/run_demo_scenario.py --outcome help-needed
```

Then refresh the dashboard and open **Mdm Tan (`senior-1`)**.

---

## 3. Feature map (proposal → product)

| Proposal feature | What to show | Where |
|---|---|---|
| **Personal Behaviour Model** | Rolling personal baseline for response latency, missed check-ins, interaction frequency, wellbeing | Dashboard → Senior detail |
| **Isolation Forest (anomaly)** | Sudden unusual combination of signals | `GET /api/v1/seniors/senior-1/detections/anomaly` + senior page |
| **Change-point detection** | Sustained / gradual shift | `GET /api/v1/seniors/senior-1/detections/change` |
| **Progressive Verification** | Senior check-in before caregiver alert | Verification status panel / scripted demo |
| **Contextual Caregiver Alerts** | What changed, context, outcome, suggested action | Alerts feed on dashboard + WhatsApp (or mock) |
| **Consent / Privacy** | Opt-in relationship; no cameras/wearables; Nomi-only interactions | Seeded consent link; explain verbally |

Nomi **does not** diagnose illness, predict medical conditions, or replace emergency services.

---

## 4. How to use the caregiver dashboard

1. Open [http://localhost:3000/dashboard](http://localhost:3000/dashboard).
2. Review seniors monitored (demo includes **Mdm Tan**, **Mr Rahman**, **Auntie Lee**).
3. Click **Mdm Tan** (`senior-1`) — she is the primary MVP persona.
4. On the senior detail page, walk through:
   - personal baseline status and observation count
   - recent check-in / response latency trend
   - latest anomaly / change detection summary
   - active verification (if any)
   - caregiver alerts with explanation and suggested next step
5. Emphasize: alerts explain **what changed relative to her normal**, not a medical diagnosis.

---

## 5. How to use the backend APIs (live demo / Postman)

Base URL: `http://127.0.0.1:8000`

| Step | Method | Path | Purpose |
|---|---|---|---|
| Health | `GET` | `/health` | Deployment check |
| List seniors | `GET` | `/api/v1/seniors` | Dashboard list |
| Senior detail | `GET` | `/api/v1/seniors/senior-1` | Baseline + series |
| Anomaly | `GET` | `/api/v1/seniors/senior-1/detections/anomaly` | Sudden change |
| Sustained change | `GET` | `/api/v1/seniors/senior-1/detections/change` | Gradual change |
| Start verification | `POST` | `/api/v1/verifications` | Senior-first check-in |
| Senior response | `POST` | `/api/v1/verifications/{id}/response` | `reassuring` or `help_needed` |
| Timeout | `POST` | `/api/v1/verifications/{id}/no-response` | Escalation rules |
| Verification status | `GET` | `/api/v1/seniors/senior-1/verification-status` | Active check-in / latest alert |
| Alerts | `GET` | `/api/v1/alerts` | Caregiver alert feed |
| Send check-in | `POST` | `/api/v1/checkins` | Outbound check-in (P3) |
| WhatsApp webhook | `POST` | `/webhooks/whatsapp` | Inbound Meta events |

---

## 6. WhatsApp path (optional live messaging)

Default `NOMI_MESSAGING_PROVIDER=mock` is enough for most demos.

For a real Meta Cloud API round-trip (P3):

1. Follow `docs/workstreams/P3/meta-cloud-api-setup.md`.
2. Set `WHATSAPP_*` vars in `.env`.
3. Deploy FastAPI on **public HTTPS** with webhook at `/webhooks/whatsapp` (P6).
4. Apply Supabase migrations (see `docs/database-setup.md`).
5. Optionally run:

```bash
python scripts/run_persistent_pipeline_demo.py
```

That script exercises: contacts → check-in → signed webhook reply → detection → verification → alert.

---

## 7. Suggested 3–5 minute presentation order

1. **Problem** — gap before anyone knows help may be needed (not only emergencies).
2. **LEARN** — show Mdm Tan’s personal baseline on the dashboard.
3. **NOTICE** — show anomaly / slower responses vs her usual pattern.
4. **VERIFY** — Nomi checks with the senior first (reassuring can stop here).
5. **SUPPORT** — if unresolved, caregiver gets a contextual WhatsApp/dashboard alert.
6. **Boundary** — behavioural awareness only; no medical diagnosis or emergency certainty.

Full narrative script: [`SCENARIO.md`](./SCENARIO.md).

---

## 8. Troubleshooting

| Issue | Fix |
|---|---|
| Frontend empty / errors | Confirm backend is on `:8000` and `NOMI_API_BASE_URL` is set |
| CORS errors | Add frontend origin to `NOMI_CORS_ORIGINS` |
| Demo script says no detection | Use `--senior-id senior-1` (seeded with an unusual late response) |
| Persistent WhatsApp demo fails | Set `WHATSAPP_APP_SECRET` and restart FastAPI |
| Need database mode | See `docs/database-setup.md` and set `NOMI_DATA_MODE=database` |

---

## 9. Related files

| Path | Purpose |
|---|---|
| `scripts/run_demo_scenario.py` | Fast detection → verification → alert demo |
| `scripts/run_persistent_pipeline_demo.py` | Full check-in + webhook + alert path |
| `docs/workstreams/P6/integration-handoff.md` | API contracts and env vars |
| `docs/database-setup.md` | Supabase setup |
| `.env.example` | Environment placeholders |
