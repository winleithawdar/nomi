from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from nomi_backend.api.app import app, get_checkin_service, reset_checkin_service, store
from nomi_backend.checkins.models import SeniorContact
from nomi_backend.checkins.sessions import FOLLOW_UP_1
from nomi_backend.messaging.protocol import ContactRole

WEBHOOK_SECRET = "dev-telegram-secret"
SENIOR_ID = "senior-1"
CHAT_ID = 987654321
CHAT_ID_STR = str(CHAT_ID)

TEXT_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 42,
        "chat": {"id": CHAT_ID, "type": "private"},
        "date": 1690000000,
        "text": "4",
    },
}

STICKER_UPDATE = {
    "update_id": 2,
    "message": {
        "message_id": 43,
        "chat": {"id": CHAT_ID, "type": "private"},
        "date": 1690000000,
        "sticker": {"file_id": "sticker-file"},
    },
}

CALLBACK_UPDATE = {
    "update_id": 3,
    "callback_query": {
        "id": "cb-1",
        "data": "ok",
        "from": {"id": CHAT_ID},
    },
}


class TelegramWebhookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._env = patch.dict(
            os.environ,
            {
                "NOMI_MESSAGING_PROVIDER": "mock",
                "TELEGRAM_WEBHOOK_SECRET": WEBHOOK_SECRET,
                "NOMI_SCHEDULER_ENABLED": "0",
            },
        )
        self._env.start()
        reset_checkin_service()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._env.stop()

    def _seed_open_checkin(self) -> None:
        store.upsert_contact(SeniorContact(SENIOR_ID, CHAT_ID_STR, ContactRole.SENIOR))
        get_checkin_service().send_checkin(SENIOR_ID)

    def test_secret_mismatch_returns_403(self) -> None:
        self._seed_open_checkin()
        response = self.client.post(
            "/webhooks/telegram",
            json=TEXT_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(store.interactions_for(SENIOR_ID), [])

    def test_valid_secret_text_closes_checkin(self) -> None:
        self._seed_open_checkin()
        response = self.client.post(
            "/webhooks/telegram",
            json=TEXT_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        interactions = store.interactions_for(SENIOR_ID)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].wellbeing_score, 4.0)
        self.assertEqual(interactions[0].interaction_type, "checkin_response")
        self.assertEqual(get_checkin_service().provider.bodies[-1], FOLLOW_UP_1)

    def test_unknown_sender_still_200(self) -> None:
        response = self.client.post(
            "/webhooks/telegram",
            json=TEXT_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(store.interactions_for(SENIOR_ID), [])

    def test_non_text_sticker_is_ignored(self) -> None:
        self._seed_open_checkin()
        response = self.client.post(
            "/webhooks/telegram",
            json=STICKER_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(store.interactions_for(SENIOR_ID), [])

    def test_callback_query_is_ignored(self) -> None:
        self._seed_open_checkin()
        response = self.client.post(
            "/webhooks/telegram",
            json=CALLBACK_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(store.interactions_for(SENIOR_ID), [])

    def test_invalid_json_still_200(self) -> None:
        response = self.client.post(
            "/webhooks/telegram",
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_post_contact_accepts_chat_id_alias(self) -> None:
        response = self.client.post(
            "/api/v1/contacts",
            json={
                "senior_id": SENIOR_ID,
                "chat_id": CHAT_ID_STR,
                "role": "senior",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "senior_id": SENIOR_ID,
                "wa_id": CHAT_ID_STR,
                "role": "senior",
                "phone_e164": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
