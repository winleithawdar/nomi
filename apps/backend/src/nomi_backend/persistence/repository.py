from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nomi_backend.persistence.schema import Base, CaregiverAlertRecord, VerificationRequestRecord
from nomi_backend.verification.models import (
  AlertStatus,
  CaregiverAlert,
  EscalationDecision,
  VerificationOutcome,
  VerificationRequest,
  VerificationStatus,
)
from nomi_backend.verification.serialization import detection_from_dict, detection_to_dict


class VerificationRepository:
  def __init__(self, session: Session) -> None:
    self.session = session

  def create_tables(self) -> None:
    Base.metadata.create_all(self.session.get_bind())

  def save_verification(self, verification: VerificationRequest) -> VerificationRequest:
    record = self._get_verification_record(verification.id)
    if record is None:
      record = VerificationRequestRecord(id=verification.id)
      self.session.add(record)
    self._apply_verification_record(record, verification)
    self.session.commit()
    self.session.refresh(record)
    return self._verification_from_record(record)

  def save_alert(self, alert: CaregiverAlert, detection_payload: dict) -> CaregiverAlert:
    record = self.session.get(CaregiverAlertRecord, alert.id)
    if record is None:
      record = CaregiverAlertRecord(id=alert.id)
      self.session.add(record)
    record.senior_id = alert.senior_id
    record.verification_request_id = alert.verification_request_id
    record.what_changed = alert.what_changed
    record.context = alert.context
    record.verification_outcome = alert.verification_outcome
    record.suggested_action = alert.suggested_action
    record.detection_summary = alert.detection_summary
    record.detection_payload = detection_payload
    record.status = alert.status.value
    record.created_at = alert.created_at
    record.delivered_at = alert.delivered_at
    self.session.commit()
    self.session.refresh(record)
    return self._alert_from_record(record)

  def get_verification(self, verification_id: str) -> VerificationRequest | None:
    record = self._get_verification_record(verification_id)
    if record is None:
      return None
    return self._verification_from_record(record)

  def get_active_verification(self, senior_id: str) -> VerificationRequest | None:
    stmt = (
      select(VerificationRequestRecord)
      .where(
        VerificationRequestRecord.senior_id == senior_id,
        VerificationRequestRecord.status == VerificationStatus.AWAITING_RESPONSE.value,
      )
      .order_by(VerificationRequestRecord.created_at.desc())
      .limit(1)
    )
    record = self.session.scalar(stmt)
    if record is None:
      return None
    return self._verification_from_record(record)

  def get_latest_reassuring_verification(self, senior_id: str) -> VerificationRequest | None:
    stmt = (
      select(VerificationRequestRecord)
      .where(
        VerificationRequestRecord.senior_id == senior_id,
        VerificationRequestRecord.status == VerificationStatus.RESOLVED_REASSURING.value,
      )
      .order_by(VerificationRequestRecord.resolved_at.desc())
      .limit(1)
    )
    record = self.session.scalar(stmt)
    if record is None:
      return None
    return self._verification_from_record(record)

  def list_verifications(self, senior_id: str, *, limit: int = 20) -> list[VerificationRequest]:
    stmt = (
      select(VerificationRequestRecord)
      .where(VerificationRequestRecord.senior_id == senior_id)
      .order_by(VerificationRequestRecord.created_at.desc())
      .limit(limit)
    )
    return [self._verification_from_record(record) for record in self.session.scalars(stmt)]

  def list_alerts(
    self,
    senior_id: str,
    *,
    limit: int = 20,
    status: AlertStatus | None = None,
  ) -> list[CaregiverAlert]:
    stmt = select(CaregiverAlertRecord).where(CaregiverAlertRecord.senior_id == senior_id)
    if status is not None:
      stmt = stmt.where(CaregiverAlertRecord.status == status.value)
    stmt = stmt.order_by(CaregiverAlertRecord.created_at.desc()).limit(limit)
    return [self._alert_from_record(record) for record in self.session.scalars(stmt)]

  def list_all_alerts(
    self,
    *,
    senior_id: str | None = None,
    status: AlertStatus | None = None,
    limit: int = 20,
  ) -> list[CaregiverAlert]:
    stmt = select(CaregiverAlertRecord)
    if senior_id is not None:
      stmt = stmt.where(CaregiverAlertRecord.senior_id == senior_id)
    if status is not None:
      stmt = stmt.where(CaregiverAlertRecord.status == status.value)
    stmt = stmt.order_by(CaregiverAlertRecord.created_at.desc()).limit(limit)
    return [self._alert_from_record(record) for record in self.session.scalars(stmt)]

  def get_alert(self, alert_id: str) -> CaregiverAlert | None:
    record = self.session.get(CaregiverAlertRecord, alert_id)
    if record is None:
      return None
    return self._alert_from_record(record)

  def mark_alert_delivered(self, alert_id: str, delivered_at: datetime) -> CaregiverAlert | None:
    record = self.session.get(CaregiverAlertRecord, alert_id)
    if record is None:
      return None
    record.status = AlertStatus.DELIVERED.value
    record.delivered_at = delivered_at
    self.session.commit()
    self.session.refresh(record)
    return self._alert_from_record(record)

  def _get_verification_record(self, verification_id: str) -> VerificationRequestRecord | None:
    return self.session.get(VerificationRequestRecord, verification_id)

  def _apply_verification_record(
    self,
    record: VerificationRequestRecord,
    verification: VerificationRequest,
  ) -> None:
    record.senior_id = verification.senior_id
    record.detection_payload = detection_to_dict(verification.detection)
    record.status = verification.status.value
    record.outcome = verification.outcome.value if verification.outcome else None
    record.escalation_decision = verification.escalation_decision.value
    record.check_in_message = verification.check_in_message
    record.message_sent_at = verification.message_sent_at
    record.response_received_at = verification.response_received_at
    record.response_text = verification.response_text
    record.created_at = verification.created_at
    record.resolved_at = verification.resolved_at

  def _verification_from_record(self, record: VerificationRequestRecord) -> VerificationRequest:
    return VerificationRequest(
      id=record.id,
      senior_id=record.senior_id,
      detection=detection_from_dict(record.detection_payload),
      status=VerificationStatus(record.status),
      outcome=VerificationOutcome(record.outcome) if record.outcome else None,
      escalation_decision=EscalationDecision(record.escalation_decision),
      check_in_message=record.check_in_message,
      created_at=record.created_at,
      message_sent_at=record.message_sent_at,
      response_received_at=record.response_received_at,
      response_text=record.response_text,
      resolved_at=record.resolved_at,
    )

  def _alert_from_record(self, record: CaregiverAlertRecord) -> CaregiverAlert:
    return CaregiverAlert(
      id=record.id,
      senior_id=record.senior_id,
      verification_request_id=record.verification_request_id,
      what_changed=record.what_changed,
      context=record.context,
      verification_outcome=record.verification_outcome,
      suggested_action=record.suggested_action,
      detection_summary=record.detection_summary,
      status=AlertStatus(record.status),
      created_at=record.created_at,
      delivered_at=record.delivered_at,
    )
