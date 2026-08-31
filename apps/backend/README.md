# Backend

Python services for Nomi: personal baseline calculation, explainable notice detection, and a FastAPI demo API.

## Structure

```text
apps/backend/
├── src/nomi_backend/
│   ├── api/           # FastAPI app
│   ├── baseline/      # Personal baseline models and calculator
│   ├── notice/        # Change-from-usual detector
│   └── services/      # Demo in-memory repository
└── tests/
```

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m unittest discover tests
uvicorn nomi_backend.api.app:app --host 127.0.0.1 --port 43124 --reload
```

## API

- `GET /health`
- `GET /api/v1/seniors`
- `GET /api/v1/seniors/{senior_id}`

The demo repository does not require Supabase. Use `infra/supabase/migrations` when wiring a real database.
