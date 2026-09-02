from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.messaging.protocol import (
    ContactRole,
    MessagingProvider,
    OutboundMessage,
    Recipient,
)
from nomi_backend.messaging.settings import MessagingSettings

from .models import CheckIn, CheckInStatus, WhatsAppEvent
from .store import CheckInStore
from .wellbeing import parse_wellbeing_score


class ContactNotFound(Exception):
    """Raised when a senior or caregiver contact cannot be resolved."""


class CheckInService:
    def __init__(
        self,
        store: CheckInStore,
        provider: MessagingProvider,
        settings: MessagingSettings,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.settings = settings
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)

    def send_checkin(self, senior_id: str, *, body: str | None = None) -> CheckIn:
        contact = self.store.get_contact(senior_id, ContactRole.SENIOR)
        if contact is None:
            raise ContactNotFound(f"No senior contact for {senior_id}")

        open_checkin = self.store.get_open_checkin(senior_id)
        if open_checkin is not None:
            return open_checkin

        checkin_id = str(uuid.uuid4())
        result = self.provider.send_text(
            Recipient(senior_id, contact.wa_id, ContactRole.SENIOR),
            body or self.settings.default_checkin_body,
            correlation_id=checkin_id,
        )
        checkin = CheckIn(
            id=checkin_id,
            senior_id=senior_id,
            sent_at=self._clock(),
            outbound_wamid=result.provider_message_id,
            status=CheckInStatus.SENT,
            response_wamid=None,
            response_received_at=None,
            wellbeing_score=None,
        )
        return self.store.create_checkin(checkin)

    def handle_inbound_message(
        self,
        *,
        wa_id: str,
        wamid: str,
        received_at: datetime,
        text: str | None,
    ) -> SeniorInteraction | None:
        contact = self.store.get_contact_by_wa_id(wa_id)
        ignored_reason: str | None = None
        open_checkin: CheckIn | None = None

        if contact is None:
            ignored_reason = "unknown_sender"
        elif contact.role is not ContactRole.SENIOR:
            ignored_reason = "not_senior"
        else:
            open_checkin = self.store.get_open_checkin(contact.senior_id)
            if open_checkin is None:
                ignored_reason = "no_open_checkin"

        recorded = self.store.record_inbound_event(
            WhatsAppEvent(
                inbound_wamid=wamid,
                wa_id=wa_id,
                received_at=received_at,
                checkin_id=open_checkin.id if ignored_reason is None and open_checkin else None,
                ignored_reason=ignored_reason,
            )
        )
        if not recorded:
            return None
        if ignored_reason is not None or open_checkin is None:
            return None

        wellbeing_score = parse_wellbeing_score(text)
        closed = replace(
            open_checkin,
            status=CheckInStatus.RESPONDED,
            response_wamid=wamid,
            response_received_at=received_at,
            wellbeing_score=wellbeing_score,
        )
        self.store.save_checkin(closed)
        interaction = SeniorInteraction(
            senior_id=closed.senior_id,
            occurred_at=received_at,
            interaction_type="checkin_response",
            missed_checkin=False,
            checkin_sent_at=closed.sent_at,
            response_received_at=received_at,
            wellbeing_score=wellbeing_score,
            checkin_id=closed.id,
            source="nomi",
        )
        return self.store.save_interaction(interaction)

    def mark_missed(self, checkin_id: str, *, as_of: datetime) -> SeniorInteraction:
        checkin = self.store.get_checkin(checkin_id)
        if checkin is None:
            raise ValueError(f"Unknown check-in {checkin_id}")
        if checkin.status is not CheckInStatus.SENT:
            raise ValueError(f"Check-in {checkin_id} is not open")

        missed = replace(
            checkin,
            status=CheckInStatus.MISSED,
            response_wamid=None,
            response_received_at=None,
            wellbeing_score=None,
        )
        self.store.save_checkin(missed)
        interaction = SeniorInteraction(
            senior_id=missed.senior_id,
            occurred_at=as_of,
            interaction_type="checkin_missed",
            missed_checkin=True,
            checkin_sent_at=missed.sent_at,
            response_received_at=None,
            wellbeing_score=None,
            checkin_id=missed.id,
            source="nomi",
        )
        return self.store.save_interaction(interaction)


def send_verification_prompt(
    service: CheckInService, senior_id: str, body: str
) -> OutboundMessage:
    contact = service.store.get_contact(senior_id, ContactRole.SENIOR)
    if contact is None:
        raise ContactNotFound(f"No senior contact for {senior_id}")
    return service.provider.send_text(
        Recipient(senior_id, contact.wa_id, ContactRole.SENIOR),
        body,
    )


def send_caregiver_alert(
    service: CheckInService, caregiver_senior_id: str, body: str
) -> OutboundMessage:
    contact = service.store.get_contact(caregiver_senior_id, ContactRole.CAREGIVER)
    if contact is None:
        raise ContactNotFound(f"No caregiver contact for {caregiver_senior_id}")
    return service.provider.send_text(
        Recipient(caregiver_senior_id, contact.wa_id, ContactRole.CAREGIVER),
        body,
    )
