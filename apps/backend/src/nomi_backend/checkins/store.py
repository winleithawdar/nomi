from __future__ import annotations

from typing import Protocol

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.messaging.protocol import ContactRole

from .models import CheckIn, CheckInStatus, SeniorContact, WhatsAppEvent


class CheckInStore(Protocol):
    def get_contact_by_wa_id(self, wa_id: str) -> SeniorContact | None: ...

    def get_contact(self, senior_id: str, role: ContactRole) -> SeniorContact | None: ...

    def upsert_contact(self, contact: SeniorContact) -> SeniorContact: ...

    def create_checkin(self, checkin: CheckIn) -> CheckIn: ...

    def get_open_checkin(self, senior_id: str) -> CheckIn | None: ...

    def get_checkin(self, checkin_id: str) -> CheckIn | None: ...

    def save_checkin(self, checkin: CheckIn) -> CheckIn: ...

    def record_inbound_event(self, event: WhatsAppEvent) -> bool:
        """Return False if inbound_wamid already seen (duplicate)."""

    def interactions_for(self, senior_id: str) -> list[SeniorInteraction]: ...


class InMemoryCheckInStore:
    def __init__(self) -> None:
        self._contacts_by_wa_id: dict[str, SeniorContact] = {}
        self._contacts_by_senior_role: dict[tuple[str, ContactRole], SeniorContact] = {}
        self._checkins: dict[str, CheckIn] = {}
        self._events: dict[str, WhatsAppEvent] = {}

    def get_contact_by_wa_id(self, wa_id: str) -> SeniorContact | None:
        return self._contacts_by_wa_id.get(wa_id)

    def get_contact(self, senior_id: str, role: ContactRole) -> SeniorContact | None:
        return self._contacts_by_senior_role.get((senior_id, role))

    def upsert_contact(self, contact: SeniorContact) -> SeniorContact:
        existing_by_wa = self._contacts_by_wa_id.get(contact.wa_id)
        if existing_by_wa is not None:
            self._contacts_by_senior_role.pop(
                (existing_by_wa.senior_id, existing_by_wa.role),
                None,
            )
        existing_by_role = self._contacts_by_senior_role.get(
            (contact.senior_id, contact.role)
        )
        if existing_by_role is not None:
            self._contacts_by_wa_id.pop(existing_by_role.wa_id, None)
        self._contacts_by_wa_id[contact.wa_id] = contact
        self._contacts_by_senior_role[(contact.senior_id, contact.role)] = contact
        return contact

    def create_checkin(self, checkin: CheckIn) -> CheckIn:
        self._checkins[checkin.id] = checkin
        return checkin

    def get_open_checkin(self, senior_id: str) -> CheckIn | None:
        open_rows = [
            checkin
            for checkin in self._checkins.values()
            if checkin.senior_id == senior_id and checkin.status is CheckInStatus.SENT
        ]
        if not open_rows:
            return None
        return max(open_rows, key=lambda checkin: checkin.sent_at)

    def get_checkin(self, checkin_id: str) -> CheckIn | None:
        return self._checkins.get(checkin_id)

    def save_checkin(self, checkin: CheckIn) -> CheckIn:
        self._checkins[checkin.id] = checkin
        return checkin

    def record_inbound_event(self, event: WhatsAppEvent) -> bool:
        if event.inbound_wamid in self._events:
            return False
        self._events[event.inbound_wamid] = event
        return True

    def interactions_for(self, senior_id: str) -> list[SeniorInteraction]:
        interactions: list[SeniorInteraction] = []
        for checkin in self._checkins.values():
            if checkin.senior_id != senior_id:
                continue
            mapped = _interaction_from_checkin(checkin)
            if mapped is not None:
                interactions.append(mapped)
        interactions.sort(key=lambda item: item.occurred_at)
        return interactions


def _interaction_from_checkin(checkin: CheckIn) -> SeniorInteraction | None:
    if checkin.status is CheckInStatus.SENT:
        return None
    if checkin.status is CheckInStatus.RESPONDED:
        occurred_at = checkin.response_received_at
        if occurred_at is None:
            occurred_at = checkin.sent_at
        return SeniorInteraction(
            senior_id=checkin.senior_id,
            occurred_at=occurred_at,
            interaction_type="checkin_response",
            missed_checkin=False,
            checkin_sent_at=checkin.sent_at,
            response_received_at=checkin.response_received_at,
            wellbeing_score=checkin.wellbeing_score,
            checkin_id=checkin.id,
            source="nomi",
        )
    return SeniorInteraction(
        senior_id=checkin.senior_id,
        occurred_at=checkin.sent_at,
        interaction_type="checkin_missed",
        missed_checkin=True,
        checkin_sent_at=checkin.sent_at,
        response_received_at=None,
        wellbeing_score=checkin.wellbeing_score,
        checkin_id=checkin.id,
        source="nomi",
    )
