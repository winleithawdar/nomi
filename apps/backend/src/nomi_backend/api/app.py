from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from nomi_backend.api.verification import router as verification_router
from nomi_backend.checkins import CheckInService, InMemoryCheckInStore
from nomi_backend.checkins.pipeline import ContactNotFound
from nomi_backend.messaging.factory import build_messaging_provider
from nomi_backend.messaging.protocol import MessagingError
from nomi_backend.messaging.settings import MessagingSettings
from nomi_backend.messaging.whatsapp_cloud import verify_meta_signature
from nomi_backend.services.demo_repository import DemoBaselineRepository
from nomi_backend.services.database_repository import DatabaseBaselineRepository

app = FastAPI(
    title="Nomi Backend API",
    version="0.2.0",
    description="Baseline, detection, and verification endpoints for Nomi.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "NOMI_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = (
    DatabaseBaselineRepository()
    if os.getenv("NOMI_DATA_MODE", "demo").lower() == "database"
    else DemoBaselineRepository()
)
store = InMemoryCheckInStore()
_checkin_service: CheckInService | None = None


def get_settings() -> MessagingSettings:
    return MessagingSettings.from_env()


def get_checkin_service() -> CheckInService:
    global _checkin_service
    if _checkin_service is None:
        settings = get_settings()
        _checkin_service = CheckInService(
            store,
            build_messaging_provider(settings),
            settings,
        )
    return _checkin_service


def reset_checkin_service() -> CheckInService:
    """Rebuild the check-in service from current env; reset store in place."""
    global _checkin_service
    store.__init__()
    _checkin_service = None
    return get_checkin_service()

app.include_router(verification_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nomi-backend", "version": app.version}


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


@app.get("/api/v1/seniors/{senior_id}/detections/change")
def get_latest_change(senior_id: str) -> dict:
    payload = repository.get_change_payload(senior_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Senior not found.")
    return payload


class CreateCheckInRequest(BaseModel):
    senior_id: str
    body: str | None = None


@app.post("/api/v1/checkins", status_code=201)
def create_checkin(payload: CreateCheckInRequest) -> dict:
    try:
        checkin = get_checkin_service().send_checkin(
            payload.senior_id,
            body=payload.body,
        )
    except ContactNotFound:
        raise HTTPException(status_code=404, detail="Senior not found.")
    except MessagingError:
        raise HTTPException(status_code=503, detail="Messaging provider unavailable.")
    return {
        "id": checkin.id,
        "senior_id": checkin.senior_id,
        "status": checkin.status.value,
        "sent_at": checkin.sent_at.isoformat(),
        "outbound_wamid": checkin.outbound_wamid,
    }


@app.get("/webhooks/whatsapp")
def verify_whatsapp_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    settings = get_settings()
    if (
        hub_mode == "subscribe"
        and settings.verify_token
        and hub_verify_token == settings.verify_token
    ):
        return PlainTextResponse(content=hub_challenge or "", status_code=200)
    raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/webhooks/whatsapp")
async def receive_whatsapp_webhook(request: Request) -> dict:
    raw_body = await request.body()
    settings = get_settings()
    signature = request.headers.get("x-hub-signature-256")
    if not verify_meta_signature(raw_body, signature, settings.app_secret):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": True}

    _process_whatsapp_payload(payload)
    return {"ok": True}


def _process_whatsapp_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    if payload.get("object") != "whatsapp_business_account":
        return

    service = get_checkin_service()
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            messages = value.get("messages")
            if not isinstance(messages, list):
                continue
            for message in messages:
                _handle_inbound_text_message(service, message)


def _handle_inbound_text_message(service: CheckInService, message: Any) -> None:
    if not isinstance(message, dict):
        return
    if message.get("type") != "text":
        return
    wa_id = message.get("from")
    wamid = message.get("id")
    if not isinstance(wa_id, str) or not isinstance(wamid, str):
        return
    text = None
    text_obj = message.get("text")
    if isinstance(text_obj, dict):
        body = text_obj.get("body")
        if isinstance(body, str):
            text = body
    try:
        received_at = datetime.fromtimestamp(
            int(message.get("timestamp")),
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return
    service.handle_inbound_message(
        wa_id=wa_id,
        wamid=wamid,
        received_at=received_at,
        text=text,
    )
