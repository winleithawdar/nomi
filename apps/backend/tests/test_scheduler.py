from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from nomi_backend.api.app import app, reset_checkin_service, store
from nomi_backend.checkins.models import SeniorContact
from nomi_backend.checkins.pipeline import CheckInService
from nomi_backend.checkins.scheduler import (
    TIMEZONE_NAME,
    already_sent_this_meal,
    current_meal,
    next_meal,
    run_due,
)
from nomi_backend.checkins.store import InMemoryCheckInStore
from nomi_backend.messaging import ContactRole, MessagingSettings, MockMessagingProvider

SGT = ZoneInfo("Asia/Singapore")
SENIOR_ID = "senior-1"
WA_ID = "6581111111"


def _at(hour: int, minute: int, day: int = 2) -> datetime:
    return datetime(2026, 9, day, hour, minute, tzinfo=SGT)


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


class MealClock:
    def __init__(self, when: datetime) -> None:
        self.when = when

    def __call__(self) -> datetime:
        return self.when


class SchedulerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryCheckInStore()
        self.store.upsert_contact(SeniorContact(SENIOR_ID, WA_ID, ContactRole.SENIOR))
        self.provider = MockMessagingProvider()
        self.clock = MealClock(_at(8, 1))
        self.service = CheckInService(
            self.store,
            self.provider,
            _settings(),
            clock=self.clock,
        )

    def test_current_and_next_meal_around_breakfast(self) -> None:
        self.assertIsNone(current_meal(_at(7, 59)))
        self.assertEqual(current_meal(_at(8, 0)), "breakfast")
        self.assertEqual(current_meal(_at(8, 1)), "breakfast")
        self.assertEqual(current_meal(_at(12, 29)), "breakfast")
        self.assertEqual(current_meal(_at(12, 30)), "lunch")
        self.assertEqual(current_meal(_at(18, 30)), "dinner")

        meal, when = next_meal(_at(7, 59))
        self.assertEqual(meal, "breakfast")
        self.assertEqual(when, _at(8, 0))
        meal, when = next_meal(_at(8, 1))
        self.assertEqual(meal, "lunch")
        self.assertEqual(when, _at(12, 30))

    def test_0759_does_not_send_breakfast(self) -> None:
        self.clock.when = _at(7, 59)
        sent = run_due(self.store, self.service, self.clock.when)
        self.assertEqual(sent, [])
        self.assertEqual(self.provider.bodies, [])
        self.assertIsNone(self.store.get_open_checkin(SENIOR_ID))

    def test_0801_sends_breakfast_once_0810_does_not(self) -> None:
        self.clock.when = _at(8, 1)
        first = run_due(self.store, self.service, self.clock.when)
        self.assertEqual(first, [SENIOR_ID])
        self.assertEqual(len(self.provider.bodies), 1)
        checkin = self.store.get_open_checkin(SENIOR_ID)
        self.assertIsNotNone(checkin)
        assert checkin is not None
        self.assertEqual(checkin.meal, "breakfast")
        self.assertTrue(
            already_sent_this_meal(self.store, SENIOR_ID, "breakfast", self.clock.when)
        )

        self.clock.when = _at(8, 10)
        second = run_due(self.store, self.service, self.clock.when)
        self.assertEqual(second, [])
        self.assertEqual(len(self.provider.bodies), 1)
        self.assertEqual(self.store.get_open_checkin(SENIOR_ID), checkin)

    def test_skips_seniors_without_senior_contact(self) -> None:
        empty = InMemoryCheckInStore()
        empty.upsert_contact(
            SeniorContact(SENIOR_ID, "6582222222", ContactRole.CAREGIVER)
        )
        service = CheckInService(empty, self.provider, _settings(), clock=self.clock)
        self.clock.when = _at(8, 1)
        sent = run_due(empty, service, self.clock.when)
        self.assertEqual(sent, [])

    def test_previous_meal_open_checkin_is_marked_missed_at_lunch(self) -> None:
        self.clock.when = _at(8, 1)
        run_due(self.store, self.service, self.clock.when)
        self.clock.when = _at(12, 31)
        sent = run_due(self.store, self.service, self.clock.when)
        self.assertEqual(sent, [SENIOR_ID])
        self.assertEqual(len(self.provider.bodies), 2)
        open_checkin = self.store.get_open_checkin(SENIOR_ID)
        self.assertIsNotNone(open_checkin)
        assert open_checkin is not None
        self.assertEqual(open_checkin.meal, "lunch")
        missed = [
            row
            for row in self.store.list_checkins(SENIOR_ID)
            if row.meal == "breakfast"
        ]
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0].status.value, "missed")


class SchedulerApiTest(unittest.TestCase):
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

    def test_run_due_returns_sent_list(self) -> None:
        response = self.client.post("/api/v1/checkins/run-due")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("sent", payload)
        self.assertIsInstance(payload["sent"], list)

    def test_schedule_returns_next_meal_in_singapore(self) -> None:
        response = self.client.get(f"/api/v1/seniors/{SENIOR_ID}/schedule")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["next_meal"], {"breakfast", "lunch", "dinner"})
        self.assertEqual(payload["timezone"], TIMEZONE_NAME)
        self.assertTrue(payload["next_at_iso"])


if __name__ == "__main__":
    unittest.main()
