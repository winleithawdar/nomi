from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from nomi_backend.api.app import app, get_checkin_service, reset_checkin_service, store
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
                "NOMI_SCHEDULER_ENABLED": "0",
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

    def test_post_contact_then_checkin_returns_201(self) -> None:
        contact = self.client.post(
            "/api/v1/contacts",
            json={
                "senior_id": SENIOR_ID,
                "wa_id": WA_ID,
                "role": "senior",
            },
        )
        self.assertEqual(contact.status_code, 201)
        self.assertEqual(
            contact.json(),
            {
                "senior_id": SENIOR_ID,
                "wa_id": WA_ID,
                "role": "senior",
                "phone_e164": None,
            },
        )
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(response.status_code, 201)

    def test_post_contact_invalid_role_returns_400(self) -> None:
        response = self.client.post(
            "/api/v1/contacts",
            json={
                "senior_id": SENIOR_ID,
                "wa_id": WA_ID,
                "role": "neighbor",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "role must be senior or caregiver"},
        )

    def test_post_contact_accepts_chat_id_alias(self) -> None:
        contact = self.client.post(
            "/api/v1/contacts",
            json={
                "senior_id": SENIOR_ID,
                "chat_id": WA_ID,
                "role": "senior",
            },
        )
        self.assertEqual(contact.status_code, 201)
        self.assertEqual(contact.json()["wa_id"], WA_ID)
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(response.status_code, 201)

    def test_post_contact_requires_wa_id_or_chat_id(self) -> None:
        response = self.client.post(
            "/api/v1/contacts",
            json={
                "senior_id": SENIOR_ID,
                "role": "senior",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "wa_id or chat_id is required"},
        )

    def test_demo_senior_wa_id_is_seeded_on_reset(self) -> None:
        self._env.stop()
        self._env = patch.dict(
            os.environ,
            {
                "NOMI_MESSAGING_PROVIDER": "mock",
                "NOMI_SCHEDULER_ENABLED": "0",
                "NOMI_DEMO_SENIOR_WA_ID": WA_ID,
            },
        )
        self._env.start()
        reset_checkin_service()
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(response.status_code, 201)

    def test_demo_senior_chat_id_is_seeded_on_reset(self) -> None:
        self._env.stop()
        self._env = patch.dict(
            os.environ,
            {
                "NOMI_MESSAGING_PROVIDER": "mock",
                "NOMI_SCHEDULER_ENABLED": "0",
                "NOMI_DEMO_SENIOR_CHAT_ID": WA_ID,
            },
        )
        self._env.start()
        reset_checkin_service()
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(response.status_code, 201)

    def test_live_checkin_shows_sent_then_responded(self) -> None:
        store.upsert_contact(SeniorContact(SENIOR_ID, WA_ID, ContactRole.SENIOR))
        created = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(created.status_code, 201)
        checkin_id = created.json()["id"]
        sent_at = created.json()["sent_at"]

        live = self.client.get(f"/api/v1/seniors/{SENIOR_ID}/live-checkin")
        self.assertEqual(live.status_code, 200)
        payload = live.json()
        self.assertEqual(payload["senior_id"], SENIOR_ID)
        self.assertTrue(payload["contact_configured"])
        self.assertEqual(
            payload["open_checkin"],
            {"id": checkin_id, "status": "sent", "sent_at": sent_at},
        )
        self.assertEqual(payload["latest"]["id"], checkin_id)
        self.assertEqual(payload["latest"]["status"], "sent")
        self.assertEqual(payload["latest"]["sent_at"], sent_at)
        self.assertIsNone(payload["latest"]["response_received_at"])
        self.assertIsNone(payload["latest"]["wellbeing_score"])
        self.assertNotIn("body", payload)
        self.assertNotIn("body", payload["latest"])
        self.assertNotIn("text", payload)

        received_at = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
        get_checkin_service().handle_inbound_message(
            wa_id=WA_ID,
            wamid="wamid.in-live-1",
            received_at=received_at,
            text="4",
        )

        live = self.client.get(f"/api/v1/seniors/{SENIOR_ID}/live-checkin")
        self.assertEqual(live.status_code, 200)
        payload = live.json()
        self.assertTrue(payload["contact_configured"])
        self.assertIsNone(payload["open_checkin"])
        self.assertEqual(payload["latest"]["id"], checkin_id)
        self.assertEqual(payload["latest"]["status"], "responded")
        self.assertEqual(payload["latest"]["sent_at"], sent_at)
        self.assertEqual(
            payload["latest"]["response_received_at"],
            received_at.isoformat(),
        )
        self.assertEqual(payload["latest"]["wellbeing_score"], 4.0)
        self.assertNotIn("body", payload["latest"])

    def test_live_checkin_without_contact_returns_200(self) -> None:
        response = self.client.get("/api/v1/seniors/unlinked-senior/live-checkin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "senior_id": "unlinked-senior",
                "contact_configured": False,
                "open_checkin": None,
                "latest": None,
            },
        )

    def test_live_checkin_empty_senior_id_returns_400(self) -> None:
        response = self.client.get("/api/v1/seniors/%20/live-checkin")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
