# Frontend

This is the Next.js caregiver dashboard for Nomi. Server components load senior baselines,
detections, verification state, and caregiver alerts from FastAPI.

Create `.env.local`:

```env
NOMI_API_BASE_URL=http://127.0.0.1:8000
```

Then run `npm ci` and `npm run dev`.
