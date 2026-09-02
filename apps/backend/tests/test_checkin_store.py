from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.checkins.models import CheckIn, CheckInStatus, SeniorContact, WhatsAppEvent
from nomi_backend.checkins.store import InMemoryCheckInStore
from nomi_backend.checkins.wellbeing import parse_wellbeing_score
from nomi_backend.messaging.protocol import ContactRole


SENT_AT = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
RECEIVED_AT = SENT_AT + timedelta(minutes=12)


def _contact(
    *,
    senior_id: str = "senior-1",
    wa_id: str = "6581111111",
    role: ContactRole = ContactRole.SENIOR,
) -> SeniorContact:
    return SeniorContact(senior_id=senior_id, wa_id=wa_id, role=role)


def _checkin(
    *,
    checkin_id: str = "checkin-1",
    senior_id: str = "senior-1",
    status: CheckInStatus = CheckInStatus.SENT,
    outbound_wamid: str | None = "wamid.out-1",
    response_wamid: str | None = None,
    response_received_at: datetime | None = None,
    wellbeing_score: float | None = None,
) -> CheckIn:
    return CheckIn(
        id=checkin_id,
        senior_id=senior_id,
        sent_at=SENT_AT,
        outbound_wamid=outbound_wamid,
        status=status,
        response_wamid=response_wamid,
        response_received_at=response_received_at,
        wellbeing_score=wellbeing_score,
    )


class CheckInStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCheckInStore()

    def test_upsert_then_get_contact_by_wa_id(self) -> None:
        contact = _contact()
        stored = self.store.upsert_contact(contact)
        self.assertEqual(stored, contact)
        self.assertEqual(self.store.get_contact_by_wa_id("6581111111"), contact)
        self.assertEqual(
            self.store.get_contact("senior-1", ContactRole.SENIOR),
            contact,
        )

    def test_unknown_wa_id_is_none(self) -> None:
        self.assertIsNone(self.store.get_contact_by_wa_id("6580000000"))

    def test_duplicate_inbound_event_returns_false(self) -> None:
        event = WhatsAppEvent(
            inbound_wamid="wamid.in-1",
            wa_id="6581111111",
            received_at=RECEIVED_AT,
            checkin_id="checkin-1",
            ignored_reason=None,
        )
        self.assertTrue(self.store.record_inbound_event(event))
        self.assertFalse(self.store.record_inbound_event(event))

    def test_interactions_for_empty_until_closed(self) -> None:
        self.store.create_checkin(_checkin())
        self.assertEqual(self.store.interactions_for("senior-1"), [])

    def test_responded_checkin_maps_to_interaction(self) -> None:
        self.store.create_checkin(_checkin())
        responded = _checkin(
            status=CheckInStatus.RESPONDED,
            response_wamid="wamid.in-1",
            response_received_at=RECEIVED_AT,
            wellbeing_score=4.0,
        )
        self.store.save_checkin(responded)

        interactions = self.store.interactions_for("senior-1")
        self.assertEqual(len(interactions), 1)
        interaction = interactions[0]
        self.assertEqual(interaction.interaction_type, "checkin_response")
        self.assertFalse(interaction.missed_checkin)
        self.assertEqual(interaction.source, "nomi")
        self.assertEqual(interaction.checkin_id, "checkin-1")
        self.assertEqual(interaction.checkin_sent_at, SENT_AT)
        self.assertEqual(interaction.response_received_at, RECEIVED_AT)
        self.assertEqual(interaction.occurred_at, RECEIVED_AT)
        self.assertEqual(interaction.wellbeing_score, 4.0)
        self.assertEqual(interaction.senior_id, "senior-1")

    def test_missed_checkin_maps_to_interaction(self) -> None:
        self.store.create_checkin(_checkin())
        missed = _checkin(status=CheckInStatus.MISSED)
        self.store.save_checkin(missed)

        interactions = self.store.interactions_for("senior-1")
        self.assertEqual(len(interactions), 1)
        interaction = interactions[0]
        self.assertEqual(interaction.interaction_type, "checkin_missed")
        self.assertTrue(interaction.missed_checkin)
        self.assertEqual(interaction.source, "nomi")
        self.assertEqual(interaction.checkin_sent_at, SENT_AT)
        self.assertIsNone(interaction.response_received_at)
        self.assertEqual(interaction.occurred_at, SENT_AT)
        self.assertEqual(interaction.checkin_id, "checkin-1")

    def test_get_open_checkin_returns_sent_not_responded(self) -> None:
        open_checkin = self.store.create_checkin(_checkin())
        self.assertEqual(self.store.get_open_checkin("senior-1"), open_checkin)

        self.store.save_checkin(
            _checkin(
                status=CheckInStatus.RESPONDED,
                response_wamid="wamid.in-1",
                response_received_at=RECEIVED_AT,
            )
        )
        self.assertIsNone(self.store.get_open_checkin("senior-1"))


class WellbeingParseTest(unittest.TestCase):
    def test_parse_wellbeing_score(self) -> None:
        self.assertEqual(parse_wellbeing_score(" 3 "), 3.0)
        self.assertIsNone(parse_wellbeing_score("ok"))
        self.assertIsNone(parse_wellbeing_score(None))
        self.assertIsNone(parse_wellbeing_score("4.0"))
        self.assertIsNone(parse_wellbeing_score("10"))
        self.assertIsNone(parse_wellbeing_score("yes 5"))
        self.assertEqual(parse_wellbeing_score("1"), 1.0)
        self.assertEqual(parse_wellbeing_score("5"), 5.0)


if __name__ == "__main__":
    unittest.main()
