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
    TelegramBotProvider,
    build_messaging_provider,
)
from nomi_backend.messaging.settings import MessagingSettings
from nomi_backend.messaging.telegram_bot import verify_telegram_secret

DUMMY_BOT_TOKEN = "dummy-telegram-bot-token-do-not-leak"


def _settings() -> MessagingSettings:
    return MessagingSettings(
        provider="telegram",
        access_token="",
        phone_number_id="",
        verify_token="",
        app_secret="",
        graph_api_version="v21.0",
        default_checkin_body="check-in",
        telegram_bot_token=DUMMY_BOT_TOKEN,
        telegram_webhook_secret="webhook-secret",
    )


def _recipient() -> Recipient:
    return Recipient(
        senior_id="senior-1",
        wa_id="123456789",
        role=ContactRole.SENIOR,
    )


def _ok_client() -> Mock:
    client = Mock()
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"ok": True, "result": {"message_id": 123}}
    client.post.return_value = response
    return client


class TelegramBotProviderTest(unittest.TestCase):
    def test_send_text_posts_to_send_message_endpoint(self) -> None:
        client = _ok_client()
        provider = TelegramBotProvider(_settings(), client=client)
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
            f"https://api.telegram.org/bot{DUMMY_BOT_TOKEN}/sendMessage",
        )
        payload = kwargs["json"]
        self.assertEqual(payload["chat_id"], "123456789")
        self.assertEqual(payload["text"], "Hello from Nomi")
        self.assertEqual(message.provider_message_id, "123")
        self.assertEqual(message.correlation_id, "corr-1")
        self.assertIsNotNone(message.sent_at.tzinfo)
        self.assertEqual(message.sent_at.tzinfo, timezone.utc)

    def test_non_2xx_raises_messaging_error_without_token(self) -> None:
        client = Mock()
        response = Mock()
        response.status_code = 400
        response.json.return_value = {"ok": False, "description": "bad request"}
        client.post.return_value = response
        provider = TelegramBotProvider(_settings(), client=client)

        with self.assertRaises(MessagingError) as raised:
            provider.send_text(_recipient(), "Hello from Nomi")

        self.assertNotIn(DUMMY_BOT_TOKEN, str(raised.exception))

    def test_missing_message_id_raises_messaging_error_without_token(self) -> None:
        client = Mock()
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"ok": True, "result": {}}
        client.post.return_value = response
        provider = TelegramBotProvider(_settings(), client=client)

        with self.assertRaises(MessagingError) as raised:
            provider.send_text(_recipient(), "Hello from Nomi")

        self.assertNotIn(DUMMY_BOT_TOKEN, str(raised.exception))


class TelegramSecretTest(unittest.TestCase):
    def test_empty_expected_allows_any_header(self) -> None:
        self.assertTrue(verify_telegram_secret(None, ""))
        self.assertTrue(verify_telegram_secret("anything", ""))

    def test_compare_digest_rejects_mismatch(self) -> None:
        self.assertFalse(verify_telegram_secret("wrong", "expected-secret"))
        self.assertFalse(verify_telegram_secret(None, "expected-secret"))
        self.assertTrue(verify_telegram_secret("expected-secret", "expected-secret"))


class TelegramFactoryTest(unittest.TestCase):
    def test_telegram_provider_setting_returns_bot_provider(self) -> None:
        provider = build_messaging_provider(_settings())
        self.assertIsInstance(provider, TelegramBotProvider)


if __name__ == "__main__":
    unittest.main()
