from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol


class ContactRole(str, Enum):
    SENIOR = "senior"
    CAREGIVER = "caregiver"


@dataclass(frozen=True)
class Recipient:
    senior_id: str | None
    wa_id: str
    role: ContactRole


@dataclass(frozen=True)
class OutboundMessage:
    provider_message_id: str
    recipient: Recipient
    sent_at: datetime
    correlation_id: str | None


class MessagingError(Exception):
    """Raised when the provider cannot send. Never includes secrets."""


class MessagingProvider(Protocol):
    def send_text(
        self,
        recipient: Recipient,
        body: str,
        *,
        correlation_id: str | None = None,
    ) -> OutboundMessage: ...
