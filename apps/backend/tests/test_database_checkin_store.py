from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nomi_backend.checkins import CheckInService, DatabaseCheckInStore, SeniorContact
from nomi_backend.messaging import ContactRole, MessagingSettings, MockMessagingProvider
from nomi_backend.persistence.schema import (
    Base,
    NomiCheckInRecord,
    SeniorInteractionRecord,
    WhatsAppEventRecord,
)

SENT_AT = datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)
RECEIVED_AT = SENT_AT + timedelta(minutes=45)


def _settings() -> MessagingSettings:
    return MessagingSettings(
        provider="mock",
        access_token="",
        phone_number_id="",
        verify_token="",
        app_secret="",
        graph_api_version="v21.0",
        default_checkin_body="How are you today?",
    )


class DatabaseCheckInStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        self.store = DatabaseCheckInStore(self.factory)
        self.store.upsert_contact(
            SeniorContact("senior-1", "6581111111", ContactRole.SENIOR)
        )

    def test_contact_and_open_checkin_survive_store_recreation(self) -> None:
        service = CheckInService(
            self.store,
            MockMessagingProvider(),
            _settings(),
            clock=lambda: SENT_AT,
        )
        sent = service.send_checkin("senior-1")

        restarted_store = DatabaseCheckInStore(self.factory)
        self.assertEqual(
            restarted_store.get_contact_by_wa_id("6581111111").senior_id,
            "senior-1",
        )
        self.assertEqual(restarted_store.get_open_checkin("senior-1").id, sent.id)

    def test_inbound_reply_persists_checkin_event_and_interaction_once(self) -> None:
        first_service = CheckInService(
            self.store,
            MockMessagingProvider(),
            _settings(),
            clock=lambda: SENT_AT,
        )
        checkin = first_service.send_checkin("senior-1")

        restarted_store = DatabaseCheckInStore(self.factory)
        restarted_service = CheckInService(
            restarted_store,
            MockMessagingProvider(),
            _settings(),
        )
        interaction = restarted_service.handle_inbound_message(
            wa_id="6581111111",
            wamid="wamid.in-1",
            received_at=RECEIVED_AT,
            text="2",
        )
        duplicate = restarted_service.handle_inbound_message(
            wa_id="6581111111",
            wamid="wamid.in-1",
            received_at=RECEIVED_AT,
            text="2",
        )

        self.assertIsNotNone(interaction)
        self.assertIsNone(duplicate)
        rows = restarted_store.interactions_for("senior-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].checkin_id, checkin.id)
        self.assertEqual(rows[0].response_latency_minutes, 45.0)
        self.assertEqual(rows[0].wellbeing_score, 2.0)

        with self.factory() as session:
            saved_checkin = session.get(NomiCheckInRecord, checkin.id)
            self.assertEqual(saved_checkin.status, "responded")
            self.assertEqual(len(session.scalars(select(WhatsAppEventRecord)).all()), 1)
            self.assertEqual(len(session.scalars(select(SeniorInteractionRecord)).all()), 1)


if __name__ == "__main__":
    unittest.main()
