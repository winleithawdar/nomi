from __future__ import annotations

import sys
import unittest
from datetime import timezone
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.messaging import (
    ContactRole,
    MessagingError,
    Recipient,
    WhatsAppCloudProvider,
    build_messaging_provider,
)
from nomi_backend.messaging.settings import MessagingSettings

DUMMY_ACCESS_TOKEN = "dummy-access-token-do-not-leak"


def _settings() -> MessagingSettings:
    return MessagingSettings(
        provider="whatsapp",
        access_token=DUMMY_ACCESS_TOKEN,
        phone_number_id="123456789",
        verify_token="verify-placeholder",
        app_secret="secret-placeholder",
        graph_api_version="v21.0",
        default_checkin_body="check-in",
    )


def _recipient() -> Recipient:
    return Recipient(
        senior_id="senior-1",
        wa_id="15551234567",
        role=ContactRole.SENIOR,
    )


def _ok_client() -> Mock:
    client = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"messages": [{"id": "wamid.abc"}]}
    client.post.return_value = response
    return client


class WhatsAppCloudProviderTest(unittest.TestCase):
    def test_send_text_posts_to_graph_messages_endpoint(self) -> None:
        client = _ok_client()
        provider = WhatsAppCloudProvider(_settings(), client=client)
        message = provider.send_text(
            _recipient(),
            "Hello from Nomi",
            correlation_id="corr-1",
        )

        client.post.assert_called_once()
        args, kwargs = client.post.call_args
        url = args[0] if args else kwargs["url"]
        self.assertEqual(
            url,
            "https://graph.facebook.com/v21.0/123456789/messages",
        )
        headers = kwargs["headers"]
        self.assertEqual(headers["Authorization"], f"Bearer {DUMMY_ACCESS_TOKEN}")
        self.assertEqual(headers["Content-Type"], "application/json")
        payload = kwargs["json"]
        self.assertEqual(payload["messaging_product"], "whatsapp")
        self.assertEqual(payload["to"], "15551234567")
        self.assertEqual(payload["type"], "text")
        self.assertEqual(payload["text"]["body"], "Hello from Nomi")
        self.assertEqual(message.provider_message_id, "wamid.abc")
        self.assertEqual(message.correlation_id, "corr-1")
        self.assertIsNotNone(message.sent_at.tzinfo)
        self.assertEqual(message.sent_at.tzinfo, timezone.utc)

    def test_non_2xx_raises_messaging_error_without_token(self) -> None:
        client = Mock()
        response = Mock()
        response.status_code = 400
        response.json.return_value = {"error": {"message": "bad request"}}
        client.post.return_value = response
        provider = WhatsAppCloudProvider(_settings(), client=client)

        with self.assertRaises(MessagingError) as raised:
            provider.send_text(_recipient(), "Hello from Nomi")

        self.assertNotIn(DUMMY_ACCESS_TOKEN, str(raised.exception))

    def test_missing_message_id_raises_messaging_error_without_token(self) -> None:
        client = Mock()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"messages": []}
        client.post.return_value = response
        provider = WhatsAppCloudProvider(_settings(), client=client)

        with self.assertRaises(MessagingError) as raised:
            provider.send_text(_recipient(), "Hello from Nomi")

        self.assertNotIn(DUMMY_ACCESS_TOKEN, str(raised.exception))


class WhatsAppFactoryTest(unittest.TestCase):
    def test_whatsapp_provider_setting_returns_cloud_provider(self) -> None:
        provider = build_messaging_provider(_settings())
        self.assertIsInstance(provider, WhatsAppCloudProvider)


if __name__ == "__main__":
    unittest.main()
