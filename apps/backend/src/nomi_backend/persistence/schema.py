from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
  pass


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


class CheckInSessionRecord(Base):
  __tablename__ = "checkin_sessions"

  id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
  senior_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
  checkin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
  meal: Mapped[str] = mapped_column(String(16), nullable=False, default="extra")
  status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
  senior_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  assessment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )
  closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CheckInMessageRecord(Base):
  __tablename__ = "checkin_messages"

  id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
  session_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("checkin_sessions.id"), nullable=False, index=True
  )
  role: Mapped[str] = mapped_column(String(16), nullable=False)
  body: Mapped[str] = mapped_column(Text, nullable=False)
  created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), nullable=False, server_default=func.now()
  )
