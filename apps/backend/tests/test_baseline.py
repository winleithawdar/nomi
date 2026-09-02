from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.baseline import (
    BaselineCalculator,
    BaselineConfig,
    BaselineStatus,
    SeniorInteraction,
    SignalStatus,
)


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

class BaselineCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calculator = BaselineCalculator(
            BaselineConfig(
                min_observations_for_stable=5,
                numeric_window_size=5,
                binary_window_size=5,
                frequency_window_days=7,
            )
        )
        self.start = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

    def test_marks_baseline_learning_for_cold_start(self) -> None:
        interactions = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=index),
                latency_minutes=15 + index,
                wellbeing_score=4.0,
            )
            for index in range(3)
        ]

        baseline = self.calculator.calculate("senior-1", interactions)

        self.assertEqual(baseline.status, BaselineStatus.LEARNING)
        self.assertEqual(baseline.total_interactions, 3)
        self.assertEqual(baseline.response_latency_minutes.status, SignalStatus.LEARNING)
        self.assertEqual(baseline.missed_checkin_rate.rate, 0.0)
        self.assertEqual(baseline.interaction_frequency.latest_value, 3.0)

    def test_stabilizes_with_recent_personal_history(self) -> None:
        latencies = [10, 11, 9, 12, 10, 11]
        wellbeing = [4, 4, 3, 4, 5, 4]
        interactions = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=index),
                latency_minutes=latency,
                wellbeing_score=wellbeing[index],
            )
            for index, latency in enumerate(latencies)
        ]

        baseline = self.calculator.calculate("senior-1", interactions)

        self.assertEqual(baseline.status, BaselineStatus.STABLE)
        self.assertEqual(baseline.response_latency_minutes.status, SignalStatus.STABLE)
        self.assertEqual(baseline.response_latency_minutes.observation_count, 5)
        self.assertAlmostEqual(baseline.response_latency_minutes.mean, 10.6)
        self.assertEqual(baseline.response_latency_minutes.latest_value, 11)
        self.assertAlmostEqual(baseline.missed_checkin_rate.rate, 0.0)
        self.assertEqual(baseline.interaction_frequency.latest_value, 6.0)

    def test_keeps_wellbeing_learning_when_sparse(self) -> None:
        interactions = []
        for index in range(6):
            interactions.append(
                interaction(
                    senior_id="senior-1",
                    occurred_at=self.start + timedelta(days=index),
                    latency_minutes=12,
                    wellbeing_score=4.0 if index < 2 else None,
                )
            )

        baseline = self.calculator.calculate("senior-1", interactions)

        self.assertEqual(baseline.status, BaselineStatus.STABLE)
        self.assertEqual(baseline.wellbeing_score.status, SignalStatus.LEARNING)
        self.assertEqual(baseline.wellbeing_score.observation_count, 2)
        self.assertEqual(baseline.response_latency_minutes.status, SignalStatus.STABLE)

    def test_handles_missed_checkins_without_latency_values(self) -> None:
        interactions = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=index),
                missed_checkin=index % 2 == 0,
                latency_minutes=None if index % 2 == 0 else 18,
                interaction_type="checkin_missed" if index % 2 == 0 else "checkin_response",
            )
            for index in range(5)
        ]

        baseline = self.calculator.calculate("senior-1", interactions)

        self.assertEqual(baseline.missed_checkin_rate.status, SignalStatus.STABLE)
        self.assertEqual(baseline.missed_checkin_rate.positive_count, 3)
        self.assertAlmostEqual(baseline.missed_checkin_rate.rate, 0.6)
        self.assertEqual(baseline.response_latency_minutes.status, SignalStatus.LEARNING)
        self.assertEqual(baseline.response_latency_minutes.observation_count, 2)

    def test_sorts_out_of_order_interactions_before_calculating(self) -> None:
        interactions = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=2),
                latency_minutes=14,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start,
                latency_minutes=10,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=1),
                latency_minutes=12,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=3),
                latency_minutes=16,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=4),
                latency_minutes=18,
            ),
        ]

        baseline = self.calculator.calculate("senior-1", interactions)

        self.assertEqual(baseline.status, BaselineStatus.STABLE)
        self.assertEqual(baseline.as_of, self.start + timedelta(days=4))
        self.assertEqual(baseline.response_latency_minutes.latest_value, 18)

    def test_example_baseline_evolves_over_time(self) -> None:
        history = [
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=0),
                latency_minutes=10,
                wellbeing_score=4,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=1),
                latency_minutes=11,
                wellbeing_score=4,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=2),
                latency_minutes=9,
                wellbeing_score=4,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=3),
                latency_minutes=10,
                wellbeing_score=4,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=4),
                latency_minutes=12,
                wellbeing_score=3,
            ),
            interaction(
                senior_id="senior-1",
                occurred_at=self.start + timedelta(days=5),
                latency_minutes=24,
                wellbeing_score=3,
            ),
        ]

        checkpoints = [
            self.calculator.calculate("senior-1", history[:count])
            for count in (2, 5, 6)
        ]

        self.assertEqual(checkpoints[0].status, BaselineStatus.LEARNING)
        self.assertAlmostEqual(checkpoints[0].response_latency_minutes.mean, 10.5)

        self.assertEqual(checkpoints[1].status, BaselineStatus.STABLE)
        self.assertAlmostEqual(checkpoints[1].response_latency_minutes.mean, 10.4)
        self.assertAlmostEqual(checkpoints[1].wellbeing_score.mean, 3.8)

        self.assertEqual(checkpoints[2].status, BaselineStatus.STABLE)
        self.assertAlmostEqual(checkpoints[2].response_latency_minutes.mean, 13.2)
        self.assertAlmostEqual(checkpoints[2].response_latency_minutes.latest_deviation_from_mean, 10.8)


if __name__ == "__main__":
    unittest.main()
