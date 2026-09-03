# P3 — Caregiver presentation demo

Keep ngrok, uvicorn, and `npm run dev` running. Phone-width (~390px).
Nomi is a personal check-in — not a diagnosis. Session scoring is
documented in [session-scoring.md](session-scoring.md).

## Keep running

- Backend: `uvicorn nomi_backend.api:app --reload` (port 8000)
- Tunnel: `ngrok http 8000`
- Frontend: `npm run dev` in `apps/frontend` (port 3000)

Frontend `.env.local` needs both `NOMI_API_BASE_URL` and
`NEXT_PUBLIC_NOMI_API_BASE_URL` pointing at `http://127.0.0.1:8000`.

Meals auto-send at **08:00 / 12:30 / 18:30 SGT** to the linked senior.
The existing **Send Nomi check-in** button is an extra ping, not a fourth meal.

On stage, fire the current meal without waiting:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/checkins/run-due
```

If ngrok restarts, `setWebhook` again (see [telegram-demo-setup.md](telegram-demo-setup.md)).

## Script (~2 minutes)

1. Open `http://localhost:3000` at phone width. **Home** — Sarah’s view. Mdm Tan has a personal baseline (not a risk score).
2. **People → Mdm Tan** — note **Next scheduled** (SGT meal clock).
3. **Send Nomi check-in** (or `run-due`). Senior Telegram: reply `4`, then answer the two follow-ups with ordinary words (`same`, `no`).
4. After the third reply, refresh Mdm Tan. Card shows **As usual**, three tracks 0/0/0 or similar, next step **No extra step.**
5. Send again. Senior: `3`, then `a bit tired today`, then `ok`. Card: **Changed from usual**. Walk judges: rhythm (if slow) / self-report 3 vs usual 4 / language `tired`. Label = **max**, not average.
6. Optional third send: `please help I fell` → **Needs you now** even if she answered quickly. Suggested step: call or visit. Reasons list `help` / `fell`.
7. Charts on this page stay on **demo** history so they cannot go blank. Tonight’s Telegram thread scores the meal card; it does not rewrite Isolation Forest / CUSUM charts.

## Judge one-liner

*Three tracks every meal — how fast she answered, the 1–5 she typed, and listed words plus TF-IDF vs her last meals. The label is the highest track. That is the whole classifier.*

## Do not claim

- Clinical diagnosis, depression, or population risk scores
- That TF-IDF is medically validated (it is auditable, not a hospital tool)
- That we scan her whole Telegram inbox — only Nomi’s meal thread
