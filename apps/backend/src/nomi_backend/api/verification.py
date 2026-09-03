from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from nomi_backend.persistence.database import SessionLocal, create_db_engine
from nomi_backend.persistence.schema import Base
from nomi_backend.services.verification_service import VerificationService
from nomi_backend.verification.models import (
    AlertStatus,
    VerificationOutcome,
    VerificationProcessResult,
    VerificationStatus,
)

router = APIRouter(prefix="/api/v1", tags=["verification"])

_db_engine = create_db_engine()
Base.metadata.create_all(_db_engine)

_result_delivery_hook: Callable[[VerificationProcessResult, bool], None] | None = None


def set_result_delivery_hook(
    hook: Callable[[VerificationProcessResult, bool], None] | None,
) -> None:
    global _result_delivery_hook
    _result_delivery_hook = hook


def _deliver_result(result: VerificationProcessResult, *, send_prompt: bool) -> None:
    if _result_delivery_hook is not None:
        _result_delivery_hook(result, send_prompt)


def get_db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_verification_service(
    session: Annotated[Session, Depends(get_db_session)],
) -> VerificationService:
    return VerificationService.from_session(session)


def _deliver_verification_messages(
    result: VerificationProcessResult,
    verification_service: VerificationService,
) -> None:
    """Best-effort outbound delivery. Never fails the verification API."""
    try:
        from nomi_backend.api.app import get_checkin_service
        from nomi_backend.checkins.pipeline import (
            ContactNotFound,
            send_caregiver_alert,
            send_verification_prompt,
        )
        from nomi_backend.messaging.protocol import MessagingError
    except Exception:
        return

    try:
        checkin_service = get_checkin_service()
        verification = result.verification
        if (
            verification.check_in_message
            and verification.status is VerificationStatus.AWAITING_RESPONSE
        ):
            send_verification_prompt(
                checkin_service,
                verification.senior_id,
                verification.check_in_message,
            )
        if result.alert is not None:
            body = verification_service.format_caregiver_message(result.alert)
            send_caregiver_alert(
                checkin_service,
                result.alert.senior_id,
                body,
            )
            verification_service.mark_alert_delivered(result.alert.id)
    except (ContactNotFound, MessagingError):
        return
    except Exception:
        return


class StartVerificationRequest(BaseModel):
    senior_id: str
    detection: dict[str, Any]
    senior_name: str | None = None


class RecordResponseRequest(BaseModel):
    outcome: VerificationOutcome
    response_text: str | None = None


class MarkAlertDeliveredRequest(BaseModel):
    delivered_at: str | None = None


@router.post("/verifications")
def start_verification(
    body: StartVerificationRequest,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P3: start senior-first verification after P1/P2 detection."""
    payload = dict(body.detection)
    payload["senior_id"] = body.senior_id
    result = service.start_from_detection_payload(payload, senior_name=body.senior_name)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Detection is not actionable for verification.",
        )
    _deliver_verification_messages(result, service)
    return result.to_dict()


@router.post("/verifications/{verification_id}/response")
def record_verification_response(
    verification_id: str,
    body: RecordResponseRequest,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P3: record the senior's reply to a verification check-in."""
    if body.outcome not in {VerificationOutcome.REASSURING, VerificationOutcome.HELP_NEEDED}:
        raise HTTPException(
            status_code=400,
            detail="Only reassuring or help_needed responses are accepted on this endpoint.",
        )
    result = service.record_response(
        verification_id,
        body.outcome,
        response_text=body.response_text,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Verification request not found.")
    _deliver_verification_messages(result, service)
    return result.to_dict()


@router.post("/verifications/{verification_id}/no-response")
def record_no_response(
    verification_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P3: apply no-response escalation rules after the check-in timeout."""
    result = service.handle_no_response(verification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Verification request not found.")
    _deliver_verification_messages(result, service)
    return result.to_dict()


@router.get("/verifications/{verification_id}")
def get_verification(
    verification_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    verification = service.repository.get_verification(verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="Verification request not found.")
    return verification.to_dict()


@router.get("/verifications/{verification_id}/check-in-message")
def get_check_in_message(
    verification_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P3: fetch the outbound senior check-in message for delivery."""
    verification = service.repository.get_verification(verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="Verification request not found.")
    return {
        "verification_id": verification.id,
        "senior_id": verification.senior_id,
        "message": verification.check_in_message,
        "status": verification.status.value,
    }


@router.get("/seniors/{senior_id}/verification-status")
def get_verification_status(
    senior_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P5: current verification state for a senior."""
    active = service.repository.get_active_verification(senior_id)
    latest_alert = service.repository.list_alerts(senior_id, limit=1)
    return {
        "senior_id": senior_id,
        "active_verification": active.to_dict() if active else None,
        "latest_alert": latest_alert[0].to_dict() if latest_alert else None,
    }


@router.get("/seniors/{senior_id}/verifications")
def list_verifications(
    senior_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """P5: verification history for a senior."""
    verifications = service.repository.list_verifications(senior_id, limit=limit)
    return {
        "senior_id": senior_id,
        "verifications": [item.to_dict() for item in verifications],
    }


@router.get("/seniors/{senior_id}/alerts")
def list_senior_alerts(
    senior_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
    limit: int = Query(default=20, ge=1, le=100),
    status: AlertStatus | None = None,
) -> dict:
    """P5: caregiver alert history for a senior."""
    alerts = service.repository.list_alerts(senior_id, limit=limit, status=status)
    return {
        "senior_id": senior_id,
        "alerts": [item.to_dict() for item in alerts],
    }


@router.get("/alerts")
def list_alerts(
    service: Annotated[VerificationService, Depends(get_verification_service)],
    senior_id: str | None = None,
    status: AlertStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """P5: dashboard-wide alert feed with optional filters."""
    alerts = service.repository.list_all_alerts(
        senior_id=senior_id,
        status=status,
        limit=limit,
    )
    return {"alerts": [item.to_dict() for item in alerts]}


@router.get("/alerts/{alert_id}")
def get_alert(
    alert_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P5: single caregiver alert detail."""
    alert = service.repository.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert.to_dict()


@router.get("/alerts/{alert_id}/caregiver-message")
def get_caregiver_message(
    alert_id: str,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P3: fetch formatted caregiver alert text for outbound delivery."""
    alert = service.repository.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return {
        "alert_id": alert.id,
        "senior_id": alert.senior_id,
        "message": service.format_caregiver_message(alert),
        "status": alert.status.value,
    }


@router.post("/alerts/{alert_id}/delivered")
def mark_alert_delivered(
    alert_id: str,
    body: MarkAlertDeliveredRequest,
    service: Annotated[VerificationService, Depends(get_verification_service)],
) -> dict:
    """P3: mark a caregiver alert as delivered after WhatsApp send."""
    alert = service.mark_alert_delivered(alert_id, delivered_at=body.delivered_at)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert.to_dict()
