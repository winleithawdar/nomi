from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.checkins.verification_reply import map_verification_reply
from nomi_backend.verification.models import VerificationOutcome


class VerificationReplyMappingTest(unittest.TestCase):
    def test_exact_one_or_two_is_help_needed(self) -> None:
        self.assertEqual(map_verification_reply("1"), VerificationOutcome.HELP_NEEDED)
        self.assertEqual(map_verification_reply(" 2 "), VerificationOutcome.HELP_NEEDED)

    def test_help_and_not_ok_substrings_are_help_needed(self) -> None:
        self.assertEqual(
            map_verification_reply("I need HELP"),
            VerificationOutcome.HELP_NEEDED,
        )
        self.assertEqual(
            map_verification_reply("I'm not ok"),
            VerificationOutcome.HELP_NEEDED,
        )
        self.assertEqual(
            map_verification_reply("Not okay today"),
            VerificationOutcome.HELP_NEEDED,
        )

    def test_other_replies_are_reassuring(self) -> None:
        self.assertEqual(map_verification_reply("4"), VerificationOutcome.REASSURING)
        self.assertEqual(map_verification_reply("3"), VerificationOutcome.REASSURING)
        self.assertEqual(map_verification_reply("All good"), VerificationOutcome.REASSURING)
        self.assertEqual(map_verification_reply("ok"), VerificationOutcome.REASSURING)


if __name__ == "__main__":
    unittest.main()
