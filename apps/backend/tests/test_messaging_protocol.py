from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.messaging import (
    ContactRole,
    MessagingError,
    OutboundMessage,
    Recipient,
)


class MessagingProtocolTest(unittest.TestCase):
    def test_contact_role_values(self) -> None:
        self.assertEqual(ContactRole.SENIOR.value, "senior")
        self.assertEqual(ContactRole.CAREGIVER.value, "caregiver")

    def test_recipient_is_frozen(self) -> None:
        recipient = Recipient(
            senior_id="senior-1",
            wa_id="15551234567",
            role=ContactRole.SENIOR,
        )
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            recipient.wa_id = "15557654321"  # type: ignore[misc]

    def test_outbound_message_is_frozen(self) -> None:
        recipient = Recipient(
            senior_id=None,
            wa_id="15551234567",
            role=ContactRole.CAREGIVER,
        )
        message = OutboundMessage(
            provider_message_id="wamid.example",
            recipient=recipient,
            sent_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
            correlation_id="corr-1",
        )
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            message.provider_message_id = "wamid.other"  # type: ignore[misc]

    def test_messaging_error_is_exception(self) -> None:
        self.assertTrue(issubclass(MessagingError, Exception))


if __name__ == "__main__":
    unittest.main()
