from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.checkins import (
    CheckInService,
    ContactNotFound,
    send_caregiver_alert,
    send_verification_prompt,
)
from nomi_backend.checkins.models import SeniorContact
from nomi_backend.checkins.store import InMemoryCheckInStore
from nomi_backend.messaging import (
    ContactRole,
    MessagingError,
    MessagingSettings,
    MockMessagingProvider,
    Recipient,
)

SENT_AT = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
RECEIVED_AT = SENT_AT + timedelta(minutes=12)


def _settings() -> MessagingSettings:
    return MessagingSettings(
        provider="mock",
        access_token="",
        phone_number_id="",
        verify_token="",
        app_secret="",
        graph_api_version="v21.0",
        default_checkin_body="Hi, this is Nomi checking in.",
    )


class _FailingProvider:
    def send_text(
        self,
        recipient: Recipient,
        body: str,
        *,
        correlation_id: str | None = None,
    ):
        raise MessagingError("provider send failed")


class CheckInPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCheckInStore()
        self.store.upsert_contact(
            SeniorContact("senior-1", "6581111111", ContactRole.SENIOR)
        )
        self.store.upsert_contact(
            SeniorContact("senior-1", "6582222222", ContactRole.CAREGIVER)
        )
        self.provider = MockMessagingProvider()
        self.service = CheckInService(
            self.store,
            self.provider,
            _settings(),
            clock=lambda: SENT_AT,
        )

    def test_send_then_inbound_reply_creates_interaction(self) -> None:
        checkin = self.service.send_checkin("senior-1")
        interaction = self.service.handle_inbound_message(
            wa_id="6581111111",
            wamid="wamid.in-1",
            received_at=RECEIVED_AT,
            text="4",
        )
        self.assertIsNotNone(interaction)
        assert interaction is not None
        self.assertEqual(interaction.source, "nomi")
        self.assertEqual(interaction.checkin_id, checkin.id)
        self.assertEqual(interaction.wellbeing_score, 4.0)
        self.assertEqual(interaction.interaction_type, "checkin_response")
        self.assertFalse(interaction.missed_checkin)
        self.assertEqual(interaction.occurred_at, RECEIVED_AT)
        self.assertEqual(interaction.response_received_at, RECEIVED_AT)
        self.assertEqual(interaction.checkin_sent_at, SENT_AT)
        self.assertEqual(interaction.response_latency_minutes, 12.0)
        stored = self.store.interactions_for("senior-1")
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].checkin_id, checkin.id)

    def test_duplicate_wamid_returns_none_and_keeps_one_interaction(self) -> None:
        self.service.send_checkin("senior-1")
        first = self.service.handle_inbound_message(
            wa_id="6581111111",
            wamid="wamid.in-dup",
            received_at=RECEIVED_AT,
            text="4",
        )
        second = self.service.handle_inbound_message(
            wa_id="6581111111",
            wamid="wamid.in-dup",
            received_at=RECEIVED_AT,
            text="4",
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(self.store.interactions_for("senior-1")), 1)

    def test_unknown_wa_id_returns_none(self) -> None:
        self.service.send_checkin("senior-1")
        result = self.service.handle_inbound_message(
            wa_id="6580000000",
            wamid="wamid.unknown",
            received_at=RECEIVED_AT,
            text="4",
        )
        self.assertIsNone(result)
        self.assertEqual(self.store.interactions_for("senior-1"), [])

    def test_second_send_checkin_while_open_does_not_resend(self) -> None:
        first = self.service.send_checkin("senior-1")
        second = self.service.send_checkin("senior-1")
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.provider.sent), 1)

    def test_mark_missed_emits_missed_interaction(self) -> None:
        checkin = self.service.send_checkin("senior-1")
        interaction = self.service.mark_missed(checkin.id, as_of=RECEIVED_AT)
        self.assertTrue(interaction.missed_checkin)
        self.assertEqual(interaction.interaction_type, "checkin_missed")
        self.assertIsNone(interaction.response_received_at)
        self.assertEqual(interaction.source, "nomi")
        self.assertEqual(interaction.checkin_id, checkin.id)

    def test_free_text_reply_stores_interaction_without_wellbeing(self) -> None:
        self.service.send_checkin("senior-1")
        interaction = self.service.handle_inbound_message(
            wa_id="6581111111",
            wamid="wamid.in-fine",
            received_at=RECEIVED_AT,
            text="I'm fine",
        )
        self.assertIsNotNone(interaction)
        assert interaction is not None
        self.assertIsNone(interaction.wellbeing_score)
        self.assertEqual(len(self.store.interactions_for("senior-1")), 1)
        self.assertIsNone(self.store.interactions_for("senior-1")[0].wellbeing_score)

    def test_send_caregiver_alert_uses_caregiver_wa_id(self) -> None:
        message = send_caregiver_alert(self.service, "senior-1", "Please check in.")
        self.assertEqual(message.recipient.wa_id, "6582222222")
        self.assertEqual(message.recipient.role, ContactRole.CAREGIVER)
        self.assertEqual(len(self.provider.sent), 1)

    def test_provider_error_does_not_leave_open_checkin(self) -> None:
        failing = CheckInService(
            self.store,
            _FailingProvider(),
            _settings(),
            clock=lambda: SENT_AT,
        )
        with self.assertRaises(MessagingError):
            failing.send_checkin("senior-1")
        self.assertIsNone(self.store.get_open_checkin("senior-1"))

    def test_send_verification_prompt_does_not_create_checkin(self) -> None:
        message = send_verification_prompt(self.service, "senior-1", "Are you OK?")
        self.assertEqual(message.recipient.wa_id, "6581111111")
        self.assertEqual(message.recipient.role, ContactRole.SENIOR)
        self.assertIsNone(self.store.get_open_checkin("senior-1"))
        self.assertEqual(self.store.interactions_for("senior-1"), [])

    def test_missing_senior_contact_raises_contact_not_found(self) -> None:
        with self.assertRaises(ContactNotFound):
            self.service.send_checkin("senior-missing")


if __name__ == "__main__":
    unittest.main()
