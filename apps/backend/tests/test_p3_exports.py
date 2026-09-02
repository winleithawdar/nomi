from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.checkins import (
    CheckInService,
    ContactNotFound,
    InMemoryCheckInStore,
    send_caregiver_alert,
)
from nomi_backend.messaging import (
    MessagingProvider,
    MessagingSettings,
    build_messaging_provider,
)


class PublicExportTests(unittest.TestCase):
    def test_p3_public_imports_are_available(self) -> None:
        self.assertIsNotNone(CheckInService)
        self.assertIsNotNone(send_caregiver_alert)
        self.assertIsNotNone(ContactNotFound)
        self.assertIsNotNone(InMemoryCheckInStore)
        self.assertIsNotNone(build_messaging_provider)
        self.assertIsNotNone(MessagingSettings)
        self.assertIsNotNone(MessagingProvider)


if __name__ == "__main__":
    unittest.main()
