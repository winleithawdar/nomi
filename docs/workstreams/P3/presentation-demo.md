# Caregiver Presentation Demo

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

## Fresh tab — live Needs you now (recommended hook)

First load of **This check in** stays empty until the caregiver sends a check-in. There is no need to delete the DB.
First open **Recent update** is **Changed from usual**; a live **Send check-in** becomes **Needs you now**.

1. Open a **new browser tab** → **People → Mdm Tan**. **This check in** should be empty — no live session yet.
2. Click **Send Nomi check-in** (Telegram webhook + ngrok running).
3. In Telegram, reply exactly:

| Turn | You type |
|---|---|
| 1 | `1` |
| 2 | `worse` |
| 3 | `Dizzy, cannot stand up properly. Need help.` |

4. Wait ~3s (card polls) or refresh. **This check in** shows **Needs you now**, suggested step **Call or visit when you can.**, and the **full check-in conversation** (same wording as Telegram).

Click Sep 3 rows for instant historical scenarios (breakfast / lunch / dinner).

## Script (~2 minutes)

1. Open `http://localhost:3000` at phone width. **Home** — Sarah’s view. Mdm Tan has a personal baseline (not a risk score).
2. **People → Mdm Tan** — scroll to **Recent check-ins** and click Sep 3 rows to show **As usual** → **Changed from usual** → **Needs you now** with meal-specific threads.
3. For the live moment, use the **Fresh tab** flow above.
4. Charts on this page stay on **demo** history so they cannot go blank. Tonight’s Telegram thread scores the meal card; it does not rewrite Isolation Forest / CUSUM charts.

## Judge one-liner

*Three tracks every meal — how fast she answered, the 1–5 she typed, and listed words plus TF-IDF vs her last meals. The label is the highest track. That is the whole classifier.*

## Do not claim

- Clinical diagnosis, depression, or population risk scores
- That TF-IDF is medically validated (it is auditable, not a hospital tool)
- That we scan her whole Telegram inbox — only Nomi’s meal thread
