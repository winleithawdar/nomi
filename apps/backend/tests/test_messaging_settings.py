from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.messaging.settings import MessagingSettings


class MessagingSettingsTest(unittest.TestCase):
    def test_defaults_to_mock_provider(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = MessagingSettings.from_env()
        self.assertEqual(settings.provider, "mock")
        self.assertEqual(settings.graph_api_version, "v21.0")
        self.assertIn("Nomi", settings.default_checkin_body)

    def test_whatsapp_provider_requires_token_and_phone_id(self) -> None:
        env = {"NOMI_MESSAGING_PROVIDER": "whatsapp"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError) as raised:
                MessagingSettings.from_env()
        self.assertIn("WHATSAPP_ACCESS_TOKEN", str(raised.exception))

    def test_whatsapp_provider_loads_credentials(self) -> None:
        env = {
            "NOMI_MESSAGING_PROVIDER": "whatsapp",
            "WHATSAPP_ACCESS_TOKEN": "token-placeholder",
            "WHATSAPP_PHONE_NUMBER_ID": "123456",
            "WHATSAPP_VERIFY_TOKEN": "verify-placeholder",
            "WHATSAPP_APP_SECRET": "secret-placeholder",
            "WHATSAPP_GRAPH_API_VERSION": "v21.0",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = MessagingSettings.from_env()
        self.assertEqual(settings.provider, "whatsapp")
        self.assertEqual(settings.access_token, "token-placeholder")
        self.assertEqual(settings.phone_number_id, "123456")
        self.assertEqual(settings.verify_token, "verify-placeholder")
        self.assertEqual(settings.app_secret, "secret-placeholder")


if __name__ == "__main__":
    unittest.main()
