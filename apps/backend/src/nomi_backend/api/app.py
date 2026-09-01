from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from nomi_backend.services.demo_repository import DemoBaselineRepository

app = FastAPI(
    title="Nomi Backend API",
    version="0.1.0",
    description="Read-only baseline endpoints for the caregiver frontend foundation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = DemoBaselineRepository()


@app.get("/api/v1/seniors")
def list_seniors() -> dict:
    return repository.list_seniors_payload()


@app.get("/api/v1/seniors/{senior_id}")
def get_senior_baseline(senior_id: str) -> dict:
    payload = repository.get_senior_detail_payload(senior_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Senior not found.")
    return payload


@app.get("/api/v1/seniors/{senior_id}/detections/anomaly")
def get_latest_anomaly(senior_id: str) -> dict:
    payload = repository.get_anomaly_payload(senior_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Senior not found.")
    return payload
