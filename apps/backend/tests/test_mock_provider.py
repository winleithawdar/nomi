from __future__ import annotations

import sys
import unittest
from datetime import timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.messaging import (
    ContactRole,
    MockMessagingProvider,
    Recipient,
    build_messaging_provider,
)
from nomi_backend.messaging.settings import MessagingSettings


def _recipient() -> Recipient:
    return Recipient(
        senior_id="senior-1",
        wa_id="15551234567",
        role=ContactRole.SENIOR,
    )


def _settings(*, provider: str) -> MessagingSettings:
    return MessagingSettings(
        provider=provider,
        access_token="token-placeholder",
        phone_number_id="123456",
        verify_token="verify-placeholder",
        app_secret="secret-placeholder",
        graph_api_version="v21.0",
        default_checkin_body="check-in",
    )


class MockMessagingProviderTest(unittest.TestCase):
    def test_two_sends_produce_sequential_mock_wamids(self) -> None:
        provider = MockMessagingProvider()
        first = provider.send_text(_recipient(), "hello")
        second = provider.send_text(_recipient(), "again")
        self.assertEqual(first.provider_message_id, "mock-wamid-1")
        self.assertEqual(second.provider_message_id, "mock-wamid-2")

    def test_correlation_id_is_stored_on_outbound_message(self) -> None:
        provider = MockMessagingProvider()
        message = provider.send_text(
            _recipient(),
            "hello",
            correlation_id="corr-42",
        )
        self.assertEqual(message.correlation_id, "corr-42")
        self.assertEqual(provider.sent[0].correlation_id, "corr-42")

    def test_sent_list_length_matches_send_count(self) -> None:
        provider = MockMessagingProvider()
        provider.send_text(_recipient(), "one")
        provider.send_text(_recipient(), "two")
        provider.send_text(_recipient(), "three")
        self.assertEqual(len(provider.sent), 3)

    def test_sent_at_is_timezone_aware_utc(self) -> None:
        provider = MockMessagingProvider()
        message = provider.send_text(_recipient(), "hello")
        self.assertIsNotNone(message.sent_at.tzinfo)
        self.assertEqual(message.sent_at.tzinfo, timezone.utc)


class BuildMessagingProviderTest(unittest.TestCase):
    def test_mock_provider_setting_returns_mock(self) -> None:
        provider = build_messaging_provider(_settings(provider="mock"))
        self.assertIsInstance(provider, MockMessagingProvider)

    def test_unknown_provider_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            build_messaging_provider(_settings(provider="sms"))


if __name__ == "__main__":
    unittest.main()
