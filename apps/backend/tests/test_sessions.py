from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nomi_backend.api.app import app, reset_checkin_service, store as app_store
from nomi_backend.checkins.models import CheckIn, CheckInStatus, SeniorContact
from nomi_backend.checkins.pipeline import CheckInService
from nomi_backend.checkins.semantics import (
    LABEL_CHANGED_FROM_USUAL,
    LABEL_NEEDS_YOU_NOW,
    STEP_CHANGED,
    STEP_NEEDS_YOU,
)
from nomi_backend.checkins.sessions import (
    FOLLOW_UP_1,
    FOLLOW_UP_2,
    THANK_YOU,
    handle_session_inbound,
    latest_scored_session_payload,
    record_missed_session,
)
from nomi_backend.checkins.store import InMemoryCheckInStore
from nomi_backend.messaging import ContactRole, MessagingSettings, MockMessagingProvider
from nomi_backend.persistence.schema import Base, CheckInMessageRecord, CheckInSessionRecord

SENIOR_ID = "senior-1"
WA_ID = "6581111111"
CAREGIVER_ID = "6582222222"
SENT_AT = datetime(2026, 9, 2, 4, 30, tzinfo=timezone.utc)
RECEIVED_AT = SENT_AT + timedelta(minutes=85)


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


class SessionFollowUpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            future=True,
            autoflush=False,
            autocommit=False,
        )
        self.db_patch = patch(
            "nomi_backend.checkins.sessions.SessionLocal",
            self.Session,
        )
        self.db_patch.start()

        import nomi_backend.checkins.sessions as sessions_mod

        sessions_mod._seen_session_wamids.clear()

        self.store = InMemoryCheckInStore()
        self.store.upsert_contact(SeniorContact(SENIOR_ID, WA_ID, ContactRole.SENIOR))
        self.store.upsert_contact(
            SeniorContact(SENIOR_ID, CAREGIVER_ID, ContactRole.CAREGIVER)
        )
        self._seed_usual_history()
        self.provider = MockMessagingProvider()
        self.service = CheckInService(
            self.store,
            self.provider,
            _settings(),
            clock=lambda: SENT_AT,
        )

    def tearDown(self) -> None:
        self.db_patch.stop()

    def _seed_usual_history(self) -> None:
        for index in range(3):
            sent = SENT_AT - timedelta(days=index + 1)
            self.store.create_checkin(
                CheckIn(
                    id=f"prior-{index}",
                    senior_id=SENIOR_ID,
                    sent_at=sent,
                    outbound_wamid=f"out-prior-{index}",
                    status=CheckInStatus.RESPONDED,
                    response_wamid=f"in-prior-{index}",
                    response_received_at=sent + timedelta(minutes=25),
                    wellbeing_score=4.0,
                    meal="lunch",
                )
            )

    def _reply(self, wamid: str, text: str, received_at: datetime) -> None:
        self.service.handle_inbound_message(
            wa_id=WA_ID,
            wamid=wamid,
            received_at=received_at,
            text=text,
        )
        handle_session_inbound(
            self.service,
            wa_id=WA_ID,
            wamid=wamid,
            text=text,
        )

    def test_three_turns_follow_ups_then_score(self) -> None:
        self.service.send_checkin(SENIOR_ID, meal="lunch")
        self._reply("wamid-1", "3", RECEIVED_AT)
        self.assertEqual(self.provider.bodies[-1], FOLLOW_UP_1)
        self.assertIsNone(self.store.get_open_checkin(SENIOR_ID))

        self._reply("wamid-2", "a bit tired today", RECEIVED_AT + timedelta(minutes=1))
        self.assertEqual(self.provider.bodies[-1], FOLLOW_UP_2)

        self._reply("wamid-3", "ok", RECEIVED_AT + timedelta(minutes=2))
        self.assertEqual(self.provider.bodies[-1], THANK_YOU)
        self.assertEqual(
            self.provider.bodies.count(FOLLOW_UP_1),
            1,
        )
        self.assertEqual(self.provider.bodies.count(FOLLOW_UP_2), 1)

        payload = latest_scored_session_payload(SENIOR_ID)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["label"], LABEL_CHANGED_FROM_USUAL)
        self.assertEqual(payload["suggested_step"], STEP_CHANGED)
        self.assertEqual(payload["rhythm_level"], 1)
        self.assertEqual(payload["self_report_level"], 1)
        self.assertEqual(payload["language_level"], 1)
        self.assertEqual(payload["meal"], "lunch")
        self.assertIn("tired", payload["lexicon_hits"])

        db = self.Session()
        try:
            session_row = db.query(CheckInSessionRecord).one()
            self.assertEqual(session_row.status, "scored")
            self.assertEqual(session_row.senior_turns, 3)
            senior_messages = (
                db.query(CheckInMessageRecord)
                .filter(CheckInMessageRecord.role == "senior")
                .all()
            )
            self.assertEqual(len(senior_messages), 3)
            nomi_bodies = [
                row.body
                for row in db.query(CheckInMessageRecord)
                .filter(CheckInMessageRecord.role == "nomi")
                .order_by(CheckInMessageRecord.created_at.asc())
                .all()
            ]
            self.assertEqual(nomi_bodies, [FOLLOW_UP_1, FOLLOW_UP_2, THANK_YOU])
        finally:
            db.close()

        responded = [
            row
            for row in self.store.list_checkins(SENIOR_ID)
            if row.status is CheckInStatus.RESPONDED
        ]
        self.assertEqual(len(responded), 4)

    def test_help_fell_alerts_caregiver(self) -> None:
        self.service.send_checkin(SENIOR_ID, meal="lunch")
        self._reply("wamid-h1", "4", SENT_AT + timedelta(minutes=5))
        self._reply("wamid-h2", "same", SENT_AT + timedelta(minutes=6))
        self._reply("wamid-h3", "please help I fell", SENT_AT + timedelta(minutes=7))

        payload = latest_scored_session_payload(SENIOR_ID)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["label"], LABEL_NEEDS_YOU_NOW)
        self.assertEqual(payload["suggested_step"], STEP_NEEDS_YOU)
        self.assertEqual(payload["language_level"], 2)
        caregiver_sends = [
            message
            for message in self.provider.sent
            if message.recipient.role is ContactRole.CAREGIVER
        ]
        self.assertEqual(len(caregiver_sends), 1)

    def test_missed_checkin_scores_needs_you_now(self) -> None:
        checkin = self.service.send_checkin(SENIOR_ID, meal="breakfast")
        missed = self.store.get_checkin(checkin.id)
        assert missed is not None
        self.service.mark_missed(checkin.id, as_of=SENT_AT + timedelta(hours=4))
        closed = self.store.get_checkin(checkin.id)
        assert closed is not None
        record_missed_session(self.service, closed)
        payload = latest_scored_session_payload(SENIOR_ID)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["label"], LABEL_NEEDS_YOU_NOW)
        self.assertEqual(payload["rhythm_level"], 2)
        self.assertEqual(payload["meal"], "breakfast")


class SessionApiTest(unittest.TestCase):
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

    def test_latest_session_null_when_none(self) -> None:
        response = self.client.get("/api/v1/seniors/no-sessions-yet/sessions/latest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"session": None})

    def test_existing_send_checkin_still_works(self) -> None:
        app_store.upsert_contact(SeniorContact(SENIOR_ID, WA_ID, ContactRole.SENIOR))
        response = self.client.post(
            "/api/v1/checkins",
            json={"senior_id": SENIOR_ID},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "sent")


if __name__ == "__main__":
    unittest.main()
