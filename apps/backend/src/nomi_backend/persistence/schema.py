from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
  pass


class SeniorContactRecord(Base):
  __tablename__ = "senior_contacts"
  __table_args__ = (UniqueConstraint("senior_id", "role"),)

  id: Mapped[str] = mapped_column(
    Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
  )
  senior_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
  wa_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
  phone_e164: Mapped[str | None] = mapped_column(String, nullable=True)
  role: Mapped[str] = mapped_column(String, nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )


class NomiCheckInRecord(Base):
  __tablename__ = "nomi_checkins"

  id: Mapped[str] = mapped_column(String, primary_key=True)
  senior_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
  sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  outbound_wamid: Mapped[str | None] = mapped_column(String, nullable=True)
  status: Mapped[str] = mapped_column(String, nullable=False, index=True)
  response_wamid: Mapped[str | None] = mapped_column(String, nullable=True)
  response_received_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )
  wellbeing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )


class WhatsAppEventRecord(Base):
  __tablename__ = "whatsapp_events"

  inbound_wamid: Mapped[str] = mapped_column(String, primary_key=True)
  wa_id: Mapped[str] = mapped_column(String, nullable=False)
  received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  checkin_id: Mapped[str | None] = mapped_column(String, nullable=True)
  verification_request_id: Mapped[str | None] = mapped_column(String, nullable=True)
  event_type: Mapped[str] = mapped_column(String, nullable=False, default="checkin_response")
  ignored_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class SeniorInteractionRecord(Base):
  __tablename__ = "senior_interactions"

  id: Mapped[str] = mapped_column(
    Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
  )
  senior_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
  checkin_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
  occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  interaction_type: Mapped[str] = mapped_column(String, nullable=False)
  checkin_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  response_received_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
  )
  response_latency_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
  missed_checkin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  wellbeing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
  source: Mapped[str] = mapped_column(String, nullable=False, default="nomi")
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )


class VerificationRequestRecord(Base):
  __tablename__ = "verification_requests"

  id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
  senior_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  detection_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
  status: Mapped[str] = mapped_column(String(32), nullable=False)
  outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
  escalation_decision: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
  check_in_message: Mapped[str] = mapped_column(Text, nullable=False)
  message_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  response_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )
  updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
  )
  resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaregiverAlertRecord(Base):
  __tablename__ = "caregiver_alerts"

  id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
  senior_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  verification_request_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("verification_requests.id"), nullable=False, index=True
  )
  what_changed: Mapped[str] = mapped_column(Text, nullable=False)
  context: Mapped[str] = mapped_column(Text, nullable=False)
  verification_outcome: Mapped[str] = mapped_column(Text, nullable=False)
  suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
  detection_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
  detection_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
  status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )
  delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
