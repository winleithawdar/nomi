from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from nomi_backend.api.app import app, reset_checkin_service, store
from nomi_backend.checkins.models import SeniorContact
from nomi_backend.messaging.protocol import ContactRole, MessagingError

SENIOR_ID = "senior-1"
WA_ID = "6581111111"


class CheckInApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._env = patch.dict(
            os.environ,
            {
                "NOMI_MESSAGING_PROVIDER": "mock",
            },
        )
        self._env.start()
        reset_checkin_service()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self._env.stop()

    def test_post_checkin_for_known_senior_returns_201(self) -> None:
        store.upsert_contact(SeniorContact(SENIOR_ID, WA_ID, ContactRole.SENIOR))
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "sent")
        self.assertEqual(payload["senior_id"], SENIOR_ID)
        self.assertTrue(payload["id"])
        self.assertTrue(payload["outbound_wamid"])
        self.assertIn("sent_at", payload)

    def test_post_checkin_unknown_senior_returns_404(self) -> None:
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": "missing"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Senior not found."})

    def test_post_checkin_messaging_error_returns_503(self) -> None:
        class FailingService:
            def send_checkin(self, senior_id: str, *, body: str | None = None):
                raise MessagingError("send failed")

        with patch(
            "nomi_backend.api.app.get_checkin_service",
            return_value=FailingService(),
        ):
            response = self.client.post(
                "/api/v1/checkins",
                json={"senior_id": SENIOR_ID},
            )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
