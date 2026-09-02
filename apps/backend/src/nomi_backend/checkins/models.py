from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from nomi_backend.messaging.protocol import ContactRole


class CheckInStatus(str, Enum):
    SENT = "sent"
    RESPONDED = "responded"
    MISSED = "missed"


@dataclass(frozen=True)
class SeniorContact:
    senior_id: str
    wa_id: str
    role: ContactRole
    phone_e164: str | None = None


@dataclass(frozen=True)
class CheckIn:
    id: str
    senior_id: str
    sent_at: datetime
    outbound_wamid: str | None
    status: CheckInStatus
    response_wamid: str | None
    response_received_at: datetime | None
    wellbeing_score: float | None


@dataclass(frozen=True)
class WhatsAppEvent:
    inbound_wamid: str
    wa_id: str
    received_at: datetime
    checkin_id: str | None
    ignored_reason: str | None
