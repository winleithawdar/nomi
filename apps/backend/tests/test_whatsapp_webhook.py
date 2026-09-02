from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from nomi_backend.api.app import app, get_checkin_service, reset_checkin_service, store
from nomi_backend.checkins.models import SeniorContact
from nomi_backend.messaging.protocol import ContactRole

VERIFY_TOKEN = "dev-verify"
APP_SECRET = "dev-secret"
CHALLENGE = "challenge-token-123"
SENIOR_ID = "senior-1"
WA_ID = "6581111111"

INBOUND_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "messages": [
                            {
                                "from": WA_ID,
                                "id": "wamid.inbound-1",
                                "timestamp": "1690000000",
                                "type": "text",
                                "text": {"body": "4"},
                            }
                        ]
                    }
                }
            ]
        }
    ],
}

STATUSES_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "value": {
                        "statuses": [{"id": "wamid.out", "status": "delivered"}]
                    }
                }
            ]
        }
    ],
}


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class WhatsAppWebhookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._env = patch.dict(
            os.environ,
            {
                "WHATSAPP_VERIFY_TOKEN": VERIFY_TOKEN,
                "WHATSAPP_APP_SECRET": APP_SECRET,
                "NOMI_MESSAGING_PROVIDER": "mock",
            },
        )
        self._env.start()
        reset_checkin_service()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._env.stop()

    def _seed_open_checkin(self) -> None:
        store.upsert_contact(SeniorContact(SENIOR_ID, WA_ID, ContactRole.SENIOR))
        get_checkin_service().send_checkin(SENIOR_ID)

    def test_get_matching_verify_token_returns_challenge(self) -> None:
        response = self.client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": CHALLENGE,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, CHALLENGE)

    def test_get_wrong_token_returns_403(self) -> None:
        response = self.client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": CHALLENGE,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_post_valid_hmac_text_creates_interaction(self) -> None:
        self._seed_open_checkin()
        body = json.dumps(INBOUND_PAYLOAD).encode("utf-8")
        response = self.client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body, APP_SECRET),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        interactions = store.interactions_for(SENIOR_ID)
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].wellbeing_score, 4.0)
        self.assertEqual(interactions[0].interaction_type, "checkin_response")

    def test_post_invalid_hmac_returns_403_without_interaction(self) -> None:
        self._seed_open_checkin()
        body = json.dumps(INBOUND_PAYLOAD).encode("utf-8")
        response = self.client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body, "other-secret"),
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(store.interactions_for(SENIOR_ID), [])

    def test_post_duplicate_wamid_still_200(self) -> None:
        self._seed_open_checkin()
        body = json.dumps(INBOUND_PAYLOAD).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _sign(body, APP_SECRET),
        }
        first = self.client.post(
            "/webhooks/whatsapp", content=body, headers=headers
        )
        second = self.client.post(
            "/webhooks/whatsapp", content=body, headers=headers
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {"ok": True})
        self.assertEqual(len(store.interactions_for(SENIOR_ID)), 1)

    def test_post_statuses_only_still_200_no_interaction(self) -> None:
        self._seed_open_checkin()
        body = json.dumps(STATUSES_PAYLOAD).encode("utf-8")
        response = self.client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _sign(body, APP_SECRET),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(store.interactions_for(SENIOR_ID), [])


if __name__ == "__main__":
    unittest.main()
