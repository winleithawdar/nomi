from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.messaging.protocol import ContactRole
from nomi_backend.persistence.schema import (
    NomiCheckInRecord,
    SeniorContactRecord,
    SeniorInteractionRecord,
    WhatsAppEventRecord,
)

from .models import CheckIn, CheckInStatus, SeniorContact, WhatsAppEvent


class DatabaseCheckInStore:
    """Restart-safe CheckInStore backed by the shared SQLAlchemy database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_contact_by_wa_id(self, wa_id: str) -> SeniorContact | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(SeniorContactRecord).where(SeniorContactRecord.wa_id == wa_id)
            )
            return _contact_from_record(row) if row else None

    def get_contact(self, senior_id: str, role: ContactRole) -> SeniorContact | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(SeniorContactRecord).where(
                    SeniorContactRecord.senior_id == senior_id,
                    SeniorContactRecord.role == role.value,
                )
            )
            return _contact_from_record(row) if row else None

    def upsert_contact(self, contact: SeniorContact) -> SeniorContact:
        with self.session_factory() as session:
            conflicts = session.scalars(
                select(SeniorContactRecord).where(
                    or_(
                        SeniorContactRecord.wa_id == contact.wa_id,
                        (
                            (SeniorContactRecord.senior_id == contact.senior_id)
                            & (SeniorContactRecord.role == contact.role.value)
                        ),
                    )
                )
            ).all()
            for row in conflicts:
                session.delete(row)
            session.flush()
            session.add(
                SeniorContactRecord(
                    senior_id=contact.senior_id,
                    wa_id=contact.wa_id,
                    phone_e164=contact.phone_e164,
                    role=contact.role.value,
                )
            )
            session.commit()
        return contact

    def create_checkin(self, checkin: CheckIn) -> CheckIn:
        with self.session_factory() as session:
            session.add(_checkin_record(checkin))
            session.commit()
        return checkin

    def get_open_checkin(self, senior_id: str) -> CheckIn | None:
        with self.session_factory() as session:
            row = session.scalar(
                select(NomiCheckInRecord)
                .where(
                    NomiCheckInRecord.senior_id == senior_id,
                    NomiCheckInRecord.status == CheckInStatus.SENT.value,
                )
                .order_by(NomiCheckInRecord.sent_at.desc())
                .limit(1)
            )
            return _checkin_from_record(row) if row else None

    def get_checkin(self, checkin_id: str) -> CheckIn | None:
        with self.session_factory() as session:
            row = session.get(NomiCheckInRecord, checkin_id)
            return _checkin_from_record(row) if row else None

    def save_checkin(self, checkin: CheckIn) -> CheckIn:
        with self.session_factory() as session:
            row = session.get(NomiCheckInRecord, checkin.id)
            if row is None:
                row = _checkin_record(checkin)
                session.add(row)
            else:
                _apply_checkin(row, checkin)
            session.commit()
        return checkin

    def record_inbound_event(self, event: WhatsAppEvent) -> bool:
        with self.session_factory() as session:
            session.add(
                WhatsAppEventRecord(
                    inbound_wamid=event.inbound_wamid,
                    wa_id=event.wa_id,
                    received_at=event.received_at,
                    checkin_id=event.checkin_id,
                    verification_request_id=event.verification_request_id,
                    event_type=event.event_type,
                    ignored_reason=event.ignored_reason,
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
        return True

    def save_interaction(self, interaction: SeniorInteraction) -> SeniorInteraction:
        with self.session_factory() as session:
            row = None
            if interaction.checkin_id is not None:
                row = session.scalar(
                    select(SeniorInteractionRecord).where(
                        SeniorInteractionRecord.checkin_id == interaction.checkin_id
                    )
                )
            if row is None:
                row = SeniorInteractionRecord()
                session.add(row)
            row.senior_id = interaction.senior_id
            row.checkin_id = interaction.checkin_id
            row.occurred_at = interaction.occurred_at
            row.interaction_type = interaction.interaction_type
            row.checkin_sent_at = interaction.checkin_sent_at
            row.response_received_at = interaction.response_received_at
            row.response_latency_minutes = interaction.response_latency_minutes
            row.missed_checkin = interaction.missed_checkin
            row.wellbeing_score = interaction.wellbeing_score
            row.source = interaction.source
            session.commit()
        return interaction

    def interactions_for(self, senior_id: str) -> list[SeniorInteraction]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(SeniorInteractionRecord)
                .where(SeniorInteractionRecord.senior_id == senior_id)
                .order_by(SeniorInteractionRecord.occurred_at)
            ).all()
            return [_interaction_from_record(row) for row in rows]


def _contact_from_record(row: SeniorContactRecord) -> SeniorContact:
    return SeniorContact(
        senior_id=row.senior_id,
        wa_id=row.wa_id,
        role=ContactRole(row.role),
        phone_e164=row.phone_e164,
    )


def _checkin_record(checkin: CheckIn) -> NomiCheckInRecord:
    row = NomiCheckInRecord(id=checkin.id)
    _apply_checkin(row, checkin)
    return row


def _apply_checkin(row: NomiCheckInRecord, checkin: CheckIn) -> None:
    row.senior_id = checkin.senior_id
    row.sent_at = checkin.sent_at
    row.outbound_wamid = checkin.outbound_wamid
    row.status = checkin.status.value
    row.response_wamid = checkin.response_wamid
    row.response_received_at = checkin.response_received_at
    row.wellbeing_score = checkin.wellbeing_score


def _checkin_from_record(row: NomiCheckInRecord) -> CheckIn:
    return CheckIn(
        id=row.id,
        senior_id=row.senior_id,
        sent_at=_aware(row.sent_at),
        outbound_wamid=row.outbound_wamid,
        status=CheckInStatus(row.status),
        response_wamid=row.response_wamid,
        response_received_at=_aware(row.response_received_at),
        wellbeing_score=row.wellbeing_score,
    )


def _interaction_from_record(row: SeniorInteractionRecord) -> SeniorInteraction:
    return SeniorInteraction(
        senior_id=row.senior_id,
        occurred_at=_aware(row.occurred_at),
        interaction_type=row.interaction_type,
        missed_checkin=row.missed_checkin,
        checkin_sent_at=_aware(row.checkin_sent_at),
        response_received_at=_aware(row.response_received_at),
        wellbeing_score=row.wellbeing_score,
        checkin_id=row.checkin_id,
        source=row.source,
    )


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
