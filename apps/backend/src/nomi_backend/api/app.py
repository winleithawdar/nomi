from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from nomi_backend.api.verification import router as verification_router
from nomi_backend.checkins import (
    CheckInService,
    DatabaseCheckInStore,
    InMemoryCheckInStore,
)
from nomi_backend.checkins.models import CheckIn, SeniorContact
from nomi_backend.checkins.pipeline import ContactNotFound
from nomi_backend.messaging.factory import build_messaging_provider
from nomi_backend.messaging.protocol import ContactRole, MessagingError
from nomi_backend.messaging.settings import MessagingSettings
from nomi_backend.messaging.telegram_bot import verify_telegram_secret
from nomi_backend.messaging.whatsapp_cloud import verify_meta_signature
from nomi_backend.persistence.database import SessionLocal
from nomi_backend.services.demo_repository import DemoBaselineRepository
from nomi_backend.services.database_repository import DatabaseBaselineRepository
from nomi_backend.services.verification_service import VerificationService
from nomi_backend.verification.models import VerificationOutcome, VerificationProcessResult

logger = logging.getLogger(__name__)

DEMO_SENIOR_ID = "senior-1"


def _load_env_file() -> None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return
        if (parent / ".git").exists():
            load_dotenv(parent / ".env", override=False)
            return


_load_env_file()


async def _scheduler_loop() -> None:
    from nomi_backend.checkins.scheduler import run_due

    while True:
        try:
            run_due(store, get_checkin_service(), datetime.now(timezone.utc))
        except Exception:
            pass
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = None
    if os.getenv("NOMI_SCHEDULER_ENABLED", "1") != "0":
        task = asyncio.create_task(_scheduler_loop())
    yield
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Nomi Backend API",
    version="0.2.0",
    description="Baseline, detection, and verification endpoints for Nomi.",
    lifespan=lifespan,
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

data_mode = os.getenv("NOMI_DATA_MODE", "demo").lower()
repository = (
    DatabaseBaselineRepository()
    if data_mode == "database"
    else DemoBaselineRepository()
)
store = (
    DatabaseCheckInStore(SessionLocal)
    if data_mode == "database"
    else InMemoryCheckInStore()
)
_checkin_service: CheckInService | None = None


def get_settings() -> MessagingSettings:
    return MessagingSettings.from_env()


def seed_demo_contact_from_env() -> None:
    senior_chat_id = (
        os.environ.get("NOMI_DEMO_SENIOR_CHAT_ID", "").strip()
        or os.environ.get("NOMI_DEMO_SENIOR_WA_ID", "").strip()
    )
    if senior_chat_id:
        store.upsert_contact(
            SeniorContact(DEMO_SENIOR_ID, senior_chat_id, ContactRole.SENIOR)
        )
    caregiver_chat_id = os.environ.get("NOMI_DEMO_CAREGIVER_CHAT_ID", "").strip()
    if caregiver_chat_id:
        store.upsert_contact(
            SeniorContact(DEMO_SENIOR_ID, caregiver_chat_id, ContactRole.CAREGIVER)
        )


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
    """Rebuild the service; clear only the disposable in-memory test store."""
    global _checkin_service
    if isinstance(store, InMemoryCheckInStore):
        store.__init__()
    _checkin_service = None
    seed_demo_contact_from_env()
    return get_checkin_service()

app.include_router(verification_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nomi-backend", "version": app.version}


seed_demo_contact_from_env()


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


class UpsertContactRequest(BaseModel):
    senior_id: str
    wa_id: str | None = None
    chat_id: str | None = None
    role: str
    phone_e164: str | None = None


@app.post("/api/v1/contacts", status_code=201)
def upsert_contact(payload: UpsertContactRequest) -> dict:
    try:
        role = ContactRole(payload.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="role must be senior or caregiver",
        )
    resolved_id = (payload.chat_id or "").strip() or (payload.wa_id or "").strip()
    if not resolved_id:
        raise HTTPException(status_code=400, detail="wa_id or chat_id is required")
    contact = store.upsert_contact(
        SeniorContact(
            payload.senior_id,
            resolved_id,
            role,
            phone_e164=payload.phone_e164,
        )
    )
    return {
        "senior_id": contact.senior_id,
        "wa_id": contact.wa_id,
        "role": contact.role.value,
        "phone_e164": contact.phone_e164,
    }


@app.post("/api/v1/checkins/run-due")
def run_due_checkins() -> dict:
    from nomi_backend.checkins.scheduler import run_due

    sent = run_due(store, get_checkin_service(), datetime.now(timezone.utc))
    return {"sent": sent}


@app.get("/api/v1/seniors/{senior_id}/schedule")
def get_senior_schedule(senior_id: str) -> dict:
    from nomi_backend.checkins.scheduler import TIMEZONE_NAME, next_meal

    if not senior_id.strip():
        raise HTTPException(status_code=400, detail="senior_id is required")
    meal, when = next_meal(datetime.now(timezone.utc))
    return {
        "next_meal": meal,
        "next_at_iso": when.isoformat(),
        "timezone": TIMEZONE_NAME,
    }


@app.get("/api/v1/seniors/{senior_id}/sessions/latest")
def get_latest_session(senior_id: str) -> dict:
    from nomi_backend.checkins.sessions import latest_scored_session_payload

    if not senior_id.strip():
        raise HTTPException(status_code=400, detail="senior_id is required")
    return {"session": latest_scored_session_payload(senior_id)}


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


def _open_checkin_payload(checkin: CheckIn | None) -> dict | None:
    if checkin is None:
        return None
    return {
        "id": checkin.id,
        "status": checkin.status.value,
        "sent_at": checkin.sent_at.isoformat(),
    }


def _latest_checkin_payload(checkin: CheckIn | None) -> dict | None:
    if checkin is None:
        return None
    received_at = checkin.response_received_at
    return {
        "id": checkin.id,
        "status": checkin.status.value,
        "sent_at": checkin.sent_at.isoformat(),
        "response_received_at": received_at.isoformat() if received_at else None,
        "wellbeing_score": checkin.wellbeing_score,
    }


@app.get("/api/v1/seniors/{senior_id}/live-checkin")
def get_live_checkin(senior_id: str) -> dict:
    if not senior_id.strip():
        raise HTTPException(status_code=400, detail="senior_id is required")
    contact = store.get_contact(senior_id, ContactRole.SENIOR)
    return {
        "senior_id": senior_id,
        "contact_configured": contact is not None,
        "open_checkin": _open_checkin_payload(store.get_open_checkin(senior_id)),
        "latest": _latest_checkin_payload(store.latest_checkin(senior_id)),
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
    contact = store.get_contact_by_wa_id(wa_id)
    open_checkin = (
        store.get_open_checkin(contact.senior_id)
        if contact is not None and contact.role is ContactRole.SENIOR
        else None
    )

    if open_checkin is not None:
        interaction = service.handle_inbound_message(
            wa_id=wa_id,
            wamid=wamid,
            received_at=received_at,
            text=text,
        )
        if interaction is not None:
            _process_new_interaction(interaction)
        return

    if contact is not None and contact.role is ContactRole.SENIOR:
        if _handle_verification_reply(
            service,
            senior_id=contact.senior_id,
            wa_id=wa_id,
            wamid=wamid,
            received_at=received_at,
            text=text,
        ):
            return

    # Preserve P3's audit record for unknown senders or messages with no open flow.
    service.handle_inbound_message(
        wa_id=wa_id,
        wamid=wamid,
        received_at=received_at,
        text=text,
    )
    _continue_session(service, wa_id=wa_id, wamid=wamid, text=text)


@app.post("/webhooks/telegram")
async def receive_telegram_webhook(request: Request) -> dict:
    settings = get_settings()
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not verify_telegram_secret(header, settings.telegram_webhook_secret):
        raise HTTPException(status_code=403, detail="Forbidden")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": True}

    _process_telegram_update(payload)
    return {"ok": True}


def _process_telegram_update(payload: Any) -> None:
    if not isinstance(payload, dict):
        return
    message = payload.get("message")
    if not isinstance(message, dict):
        return
    text = message.get("text")
    if not isinstance(text, str):
        return
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return
    chat_id_raw = chat.get("id")
    message_id_raw = message.get("message_id")
    if chat_id_raw is None or message_id_raw is None:
        return
    try:
        received_at = datetime.fromtimestamp(
            int(message.get("date")),
            tz=timezone.utc,
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return

    chat_id = str(chat_id_raw)
    message_id = str(message_id_raw)
    service = get_checkin_service()
    service.handle_inbound_message(
        wa_id=chat_id,
        wamid=message_id,
        received_at=received_at,
        text=text,
    )
    _continue_session(service, wa_id=chat_id, wamid=message_id, text=text)
    _try_record_verification_reply(service, chat_id, text)


def _continue_session(
    service: CheckInService,
    *,
    wa_id: str,
    wamid: str,
    text: str | None,
) -> None:
    if not isinstance(text, str):
        return
    try:
        from nomi_backend.checkins.sessions import handle_session_inbound

        handle_session_inbound(
            service,
            wa_id=wa_id,
            wamid=wamid,
            text=text,
        )
    except Exception:
        return


def _try_record_verification_reply(
    service: CheckInService,
    chat_id: str,
    text: str,
) -> None:
    contact = service.store.get_contact_by_wa_id(chat_id)
    if contact is None or contact.role is not ContactRole.SENIOR:
        return
    try:
        from nomi_backend.api.verification import _deliver_verification_messages
        from nomi_backend.checkins.verification_reply import map_verification_reply
        from nomi_backend.persistence.database import SessionLocal
        from nomi_backend.services.verification_service import VerificationService

        session = SessionLocal()
        try:
            verification_service = VerificationService.from_session(session)
            active = verification_service.repository.get_active_verification(
                contact.senior_id
            )
            if active is None:
                return
            outcome = map_verification_reply(text)
            result = verification_service.record_response(
                active.id,
                outcome,
                response_text=None,
            )
            if result is not None:
                _deliver_verification_messages(result, verification_service)
        finally:
            session.close()
    except Exception:
        return
