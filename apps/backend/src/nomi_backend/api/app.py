from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from nomi_backend.api.verification import (
    router as verification_router,
    set_result_delivery_hook,
)
from nomi_backend.checkins import (
    CheckInService,
    DatabaseCheckInStore,
    InMemoryCheckInStore,
    SeniorContact,
    WhatsAppEvent,
    parse_wellbeing_score,
    send_caregiver_alert,
    send_verification_prompt,
)
from nomi_backend.checkins.pipeline import ContactNotFound
from nomi_backend.messaging.factory import build_messaging_provider
from nomi_backend.messaging.protocol import ContactRole, MessagingError
from nomi_backend.messaging.settings import MessagingSettings
from nomi_backend.messaging.whatsapp_cloud import verify_meta_signature
from nomi_backend.persistence.database import SessionLocal
from nomi_backend.services.demo_repository import DemoBaselineRepository
from nomi_backend.services.database_repository import DatabaseBaselineRepository
from nomi_backend.services.verification_service import VerificationService
from nomi_backend.verification.models import VerificationOutcome, VerificationProcessResult

logger = logging.getLogger(__name__)

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


class UpsertContactRequest(BaseModel):
    wa_id: str
    phone_e164: str | None = None


class MarkMissedRequest(BaseModel):
    as_of: datetime | None = None


@app.put("/api/v1/seniors/{senior_id}/contacts/{role}")
def upsert_senior_contact(
    senior_id: str,
    role: ContactRole,
    payload: UpsertContactRequest,
) -> dict:
    """MVP administration endpoint for registering senior/caregiver WhatsApp IDs."""
    contact = store.upsert_contact(
        SeniorContact(
            senior_id=senior_id,
            wa_id=payload.wa_id,
            role=role,
            phone_e164=payload.phone_e164,
        )
    )
    return {
        "senior_id": contact.senior_id,
        "wa_id": contact.wa_id,
        "role": contact.role.value,
        "phone_e164": contact.phone_e164,
    }


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


@app.post("/api/v1/checkins/{checkin_id}/missed")
def mark_checkin_missed(checkin_id: str, payload: MarkMissedRequest) -> dict:
    try:
        interaction = get_checkin_service().mark_missed(
            checkin_id,
            as_of=payload.as_of or datetime.now(timezone.utc),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    _process_new_interaction(interaction)
    return {
        "checkin_id": checkin_id,
        "status": "missed",
        "interaction": {
            "senior_id": interaction.senior_id,
            "occurred_at": interaction.occurred_at.isoformat(),
            "missed_checkin": interaction.missed_checkin,
        },
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


def _process_new_interaction(interaction) -> None:
    if data_mode != "database":
        return
    change = repository.get_change_payload(interaction.senior_id)
    anomaly = repository.get_anomaly_payload(interaction.senior_id)
    detection = next(
        (
            item
            for item in (change, anomaly)
            if item is not None and item.get("detected") and item.get("status") == "ok"
        ),
        None,
    )
    if detection is None:
        return

    senior_detail = repository.get_senior_detail_payload(interaction.senior_id)
    senior_name = senior_detail["senior"]["name"] if senior_detail else None
    with SessionLocal() as session:
        verification_service = VerificationService.from_session(session)
        result = verification_service.start_from_detection_payload(
            detection,
            senior_name=senior_name,
        )
    if result is not None:
        _dispatch_verification_result(get_checkin_service(), result)


def _handle_verification_reply(
    service: CheckInService,
    *,
    senior_id: str,
    wa_id: str,
    wamid: str,
    received_at: datetime,
    text: str | None,
) -> bool:
    with SessionLocal() as session:
        verification_service = VerificationService.from_session(session)
        active = verification_service.repository.get_active_verification(senior_id)
        if active is None:
            return False
        recorded = store.record_inbound_event(
            WhatsAppEvent(
                inbound_wamid=wamid,
                wa_id=wa_id,
                received_at=received_at,
                checkin_id=None,
                ignored_reason=None,
                verification_request_id=active.id,
                event_type="verification_response",
            )
        )
        if not recorded:
            return True
        outcome = _verification_outcome_from_text(text)
        if outcome is None:
            logger.info("Verification reply could not be classified for %s", senior_id)
            return True
        result = verification_service.record_response(
            active.id,
            outcome,
            response_text=text,
        )
    if result is not None:
        _dispatch_verification_result(service, result, send_prompt=False)
    return True


def _verification_outcome_from_text(text: str | None) -> VerificationOutcome | None:
    score = parse_wellbeing_score(text)
    if score is not None:
        if score >= 4:
            return VerificationOutcome.REASSURING
        if score <= 2:
            return VerificationOutcome.HELP_NEEDED
    normalized = (text or "").strip().lower()
    reassuring_phrases = ("i'm fine", "im fine", "all good", "okay", "ok", "no help")
    help_phrases = ("help", "not okay", "not ok", "call me", "visit me")
    if any(phrase in normalized for phrase in help_phrases):
        return VerificationOutcome.HELP_NEEDED
    if any(phrase in normalized for phrase in reassuring_phrases):
        return VerificationOutcome.REASSURING
    return None


def _dispatch_verification_result(
    service: CheckInService,
    result: VerificationProcessResult,
    *,
    send_prompt: bool = True,
) -> None:
    try:
        if result.alert is not None:
            message = result.caregiver_message or "Nomi has an update requiring your attention."
            send_caregiver_alert(service, result.alert.senior_id, message)
            with SessionLocal() as session:
                VerificationService.from_session(session).mark_alert_delivered(result.alert.id)
        elif send_prompt:
            send_verification_prompt(
                service,
                result.verification.senior_id,
                result.verification.check_in_message,
            )
    except (ContactNotFound, MessagingError):
        # Meta webhooks must still return 200 so that delivery is not retried forever.
        logger.exception("Unable to deliver Nomi verification or caregiver message")


set_result_delivery_hook(
    lambda result, send_prompt: _dispatch_verification_result(
        get_checkin_service(),
        result,
        send_prompt=send_prompt,
    )
)
