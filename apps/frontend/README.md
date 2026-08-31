# Frontend

Next.js caregiver dashboard for Nomi.

The dashboard reads baseline and notice data from the FastAPI backend. It is mobile-responsive and uses a calm, clinical-adjacent visual language without danger labels.

## Run

Copy `.env.example` to `.env.local`, start the backend on port `43124`, then:

```bash
npm install
npm run dev -- --port 43123 --hostname 127.0.0.1
```

Open [http://127.0.0.1:43123](http://127.0.0.1:43123).

## Routes

- `/` redirects to `/dashboard`
- `/dashboard` caregiver overview
- `/seniors` people you support
- `/seniors/[id]` personal baseline and notice view
