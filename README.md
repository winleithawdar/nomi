# Nomi

AI-powered senior-care support focused on detecting meaningful changes from each senior's own normal pattern.

## Repository Layout

```text
nomi/
├── apps/
│   ├── backend/        # Python backend and baseline logic
│   └── frontend/       # Reserved for future Next.js caregiver dashboard
├── docs/
│   └── architecture/   # Product and technical design notes
└── infra/
    └── supabase/       # Database migrations and infrastructure assets
```

## Current Status

The repository currently includes only the first backend slice for the personal baseline layer:

- recent per-senior behavioural baseline calculation
- synthetic tests for cold start and rolling-window behavior
- initial Supabase migration for interaction storage and baseline snapshots

## Next Planned Additions

- `apps/frontend/` for the Next.js caregiver dashboard
- FastAPI endpoints and services inside `apps/backend/`
- additional anomaly detection layers once the baseline is in place
