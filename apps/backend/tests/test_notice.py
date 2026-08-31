from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.baseline import (
    BaselineCalculator,
    BaselineConfig,
    SeniorInteraction,
)
from nomi_backend.notice import NoticeDetector


def interaction(
    *,
    senior_id: str,
    occurred_at: datetime,
    latency_minutes: float | None = None,
    missed_checkin: bool = False,
    wellbeing_score: float | None = None,
    interaction_type: str = "checkin_response",
) -> SeniorInteraction:
    sent_at = None
    responded_at = None
    if latency_minutes is not None:
        sent_at = occurred_at - timedelta(minutes=latency_minutes)
        responded_at = occurred_at

    return SeniorInteraction(
        senior_id=senior_id,
        occurred_at=occurred_at,
        interaction_type=interaction_type,
        missed_checkin=missed_checkin,
        checkin_sent_at=sent_at,
        response_received_at=responded_at,
        wellbeing_score=wellbeing_score,
    )


class NoticeDetectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calculator = BaselineCalculator(
            BaselineConfig(
                min_observations_for_stable=5,
                numeric_window_size=5,
                binary_window_size=5,
                frequency_window_days=7,
            )
        )
        self.detector = NoticeDetector()
        self.start = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

    def test_waits_until_baseline_is_established(self) -> None:
        history = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=index),
                latency_minutes=12,
                wellbeing_score=4.0,
            )
            for index in range(3)
        ]
        baseline = self.calculator.calculate("senior-1", history)
        notice = self.detector.assess(baseline, "Mdm Tan")

        self.assertEqual(notice.status, "learning")
        self.assertEqual(notice.findings, [])
        self.assertIn("Still learning", notice.headline)

    def test_keeps_usual_when_latest_values_match_personal_pattern(self) -> None:
        history = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=index),
                latency_minutes=10 + (index % 2),
                wellbeing_score=4.0,
            )
            for index in range(6)
        ]
        baseline = self.calculator.calculate("senior-1", history)
        notice = self.detector.assess(baseline, "Mdm Tan")

        self.assertEqual(notice.status, "usual")
        self.assertEqual(notice.findings, [])

    def test_flags_slower_reply_against_personal_latency(self) -> None:
        latencies = [10, 11, 9, 12, 10, 40]
        history = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=index),
                latency_minutes=latency,
                wellbeing_score=4.0,
            )
            for index, latency in enumerate(latencies)
        ]
        baseline = self.calculator.calculate("senior-1", history)
        notice = self.detector.assess(baseline, "Mdm Tan")

        self.assertIn(notice.status, {"watching", "changed"})
        self.assertTrue(any(finding.signal == "response_latency_minutes" for finding in notice.findings))
        self.assertIn("minutes", notice.findings[0].explanation)

    def test_flags_repeated_missed_checkins_as_changed(self) -> None:
        history = []
        for index in range(6):
            missed = index >= 3
            history.append(
                interaction(
                    senior_id="senior-1",
                    occurred_at=self.start + timedelta(days=index),
                    latency_minutes=None if missed else 12,
                    missed_checkin=missed,
                    interaction_type="checkin_missed" if missed else "checkin_response",
                    wellbeing_score=4.0,
                )
            )

        baseline = self.calculator.calculate("senior-1", history)
        notice = self.detector.assess(baseline, "Mr Rahman")

        self.assertEqual(notice.status, "changed")
        self.assertTrue(any(finding.signal == "missed_checkin_rate" for finding in notice.findings))


if __name__ == "__main__":
    unittest.main()
