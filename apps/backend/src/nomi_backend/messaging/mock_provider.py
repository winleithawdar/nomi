from __future__ import annotations

from datetime import datetime, timezone

from .protocol import OutboundMessage, Recipient


class MockMessagingProvider:
    """Records outbound sends in memory with deterministic mock-wamid-{n} ids."""

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    def send_text(
        self,
        recipient: Recipient,
        body: str,
        *,
        correlation_id: str | None = None,
    ) -> OutboundMessage:
        message = OutboundMessage(
            provider_message_id=f"mock-wamid-{len(self.sent) + 1}",
            recipient=recipient,
            sent_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
        )
        self.sent.append(message)
        return message
