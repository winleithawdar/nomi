# Frontend

Mobile-first Next.js caregiver app for Nomi. Server components load senior
baselines, detections, verification state, and caregiver alerts from FastAPI.

Create `.env.local`:

```env
NOMI_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_NOMI_API_BASE_URL=http://127.0.0.1:8000
```

`NOMI_API_BASE_URL` is server-only. `NEXT_PUBLIC_NOMI_API_BASE_URL` is required
so the live check-in panel can poll FastAPI from the browser (CORS is already
allowed). Server components still use `apiGet`.

Then run:

```bash
npm ci
npm run dev
```

Open `http://localhost:3000`. The app is designed for a phone-width caregiver
view: Home, People, and Alerts in the bottom tab bar.
