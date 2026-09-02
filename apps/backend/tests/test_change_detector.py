from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.detection.changes import ChangeDetector, ChangeDetectorConfig
from nomi_backend.detection.contract import (
    ChangeDirection,
    DetectionKind,
    DetectionStatus,
)

START = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _interaction(
    *,
    occurred_at: datetime,
    latency_minutes: float | None = None,
    missed_checkin: bool = False,
    wellbeing_score: float | None = None,
) -> SeniorInteraction:
    sent_at = responded_at = None
    if latency_minutes is not None:
        sent_at = occurred_at - timedelta(minutes=latency_minutes)
        responded_at = occurred_at
    return SeniorInteraction(
        senior_id="senior-1",
        occurred_at=occurred_at,
        interaction_type="checkin_missed" if missed_checkin else "checkin_response",
        missed_checkin=missed_checkin,
        checkin_sent_at=sent_at,
        response_received_at=responded_at,
        wellbeing_score=wellbeing_score,
    )


def _latency_history(values: list[float]) -> list[SeniorInteraction]:
    return [
        _interaction(occurred_at=START + timedelta(days=index), latency_minutes=value)
        for index, value in enumerate(values)
    ]


class ChangeDetectorLevelShiftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_stable_history_is_not_flagged(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 25, 24, 26, 25, 24])

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.kind, DetectionKind.SUSTAINED_CHANGE)
        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertFalse(result.detected)
        self.assertEqual(result.direction, ChangeDirection.NONE)

    def test_sustained_latency_step_is_flagged_rising(self) -> None:
        history = _latency_history(
            [25, 24, 26, 25, 24, 25, 26]  # personal normal ~25
            + [48, 50, 47, 49, 51, 48, 50]  # sustained step up
        )

        result = self.detector.detect("senior-1", history)

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, ChangeDirection.RISING)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        self.assertTrue(latency.flagged)
        self.assertIn("level_shift", latency.methods_fired)
        self.assertGreater(latency.standardized_shift, 0)
        self.assertAlmostEqual(latency.recent_mean, 49.0, delta=1.0)

    def test_short_history_returns_insufficient_history(self) -> None:
        history = _latency_history([25, 26, 24])

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertFalse(result.detected)

    def test_recent_series_is_attached_for_charting(self) -> None:
        history = _latency_history([25] * 7 + [40] * 7)

        result = self.detector.detect("senior-1", history)

        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        self.assertEqual(len(latency.recent_series), 7)
        self.assertEqual(latency.recent_series[-1]["value"], 40.0)
        self.assertIn("occurred_at", latency.recent_series[0])

    def test_missed_checkin_rate_step_is_flagged(self) -> None:
        history = [
            _interaction(occurred_at=START + timedelta(days=i), latency_minutes=20)
            for i in range(7)
        ] + [
            _interaction(occurred_at=START + timedelta(days=7 + i), missed_checkin=True)
            for i in range(7)
        ]

        result = self.detector.detect("senior-1", history)

        rate = next(
            c for c in result.contributions if c.signal == "missed_checkin_rate"
        )
        self.assertTrue(rate.flagged)
        self.assertEqual(rate.direction, ChangeDirection.RISING)


class ChangeDetectorCusumTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_gradual_drift_trips_cusum_and_reports_onset(self) -> None:
        # ~1.6 min/day ramp off a ~25 base, sustained for 10 points.
        values = [25, 24, 26, 25, 24, 25, 26]
        values += [26 + 1.6 * step for step in range(1, 11)]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertTrue(latency.flagged)
        self.assertIn("cusum", latency.methods_fired)
        self.assertIsNotNone(latency.estimated_onset)
        # onset lands in the ramp region, not the flat baseline prefix
        self.assertGreater(latency.estimated_onset, START + timedelta(days=4))

    def test_lone_spike_does_not_trip_cusum(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26, 24, 25, 26, 25] + [95] + [25, 24, 26]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertNotIn("cusum", latency.methods_fired)

    def test_cusum_clears_after_recovery_to_normal(self) -> None:
        values = (
            [25, 24, 26, 25, 24, 25, 26]
            + [46, 48, 47, 49, 48]  # excursion
            + [26, 25, 24, 25, 26, 25, 24, 26]  # recovered, long enough to fill window
        )
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertFalse(latency.flagged)


class ChangeDetectorTrendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_monotonic_ramp_in_recent_window_fires_trend(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26] + [28, 31, 34, 37, 40, 43, 46]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertTrue(latency.flagged)
        self.assertIn("trend", latency.methods_fired)
        self.assertEqual(latency.direction, ChangeDirection.RISING)

    def test_noisy_but_flat_recent_window_does_not_fire_trend(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26] + [25, 27, 24, 26, 25, 24, 26]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertNotIn("trend", latency.methods_fired)

    def test_confidence_is_moderate_when_two_methods_agree_on_one_signal(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26] + [30, 34, 38, 42, 46, 50, 54]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertGreaterEqual(len(latency.methods_fired), 2)
        self.assertEqual(result.confidence.value, "moderate")


from nomi_backend.detection import ChangeDetector as ExportedDetector
from nomi_backend.detection import ChangeDetectorConfig as ExportedConfig


class ChangeDetectorEdgeCaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_learning_baseline_short_series_is_insufficient(self) -> None:
        history = _latency_history([25, 26, 24])
        result = self.detector.detect("senior-1", history)
        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)

    def test_absent_wellbeing_signal_is_skipped_not_errored(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 40, 41, 39, 42, 40, 41, 39])
        result = self.detector.detect("senior-1", history)
        wellbeing = next(
            c for c in result.contributions if c.signal == "wellbeing_score"
        )
        self.assertEqual(wellbeing.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertTrue(result.detected)  # latency still evaluated

    def test_shuffled_input_matches_sorted_input(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 48, 50, 47, 49, 51, 48, 50])
        shuffled = [history[i] for i in (3, 0, 11, 6, 1, 9, 13, 2, 7, 4, 12, 5, 10, 8)]
        self.assertEqual(
            self.detector.detect("senior-1", history).to_dict(),
            self.detector.detect("senior-1", shuffled).to_dict(),
        )

    def test_nan_value_is_dropped_and_recorded(self) -> None:
        # NaN cannot reach the timestamp-derived latency; wellbeing_score is the
        # signal a malformed value actually lands on. Design section 8: filtered,
        # counted in metadata["dropped_values"], never raises.
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 48, 50, 47, 49, 51, 48])
        history.append(
            _interaction(
                occurred_at=START + timedelta(days=13),
                latency_minutes=50,
                wellbeing_score=math.nan,
            )
        )
        result = self.detector.detect("senior-1", history)
        self.assertGreaterEqual(result.metadata["dropped_values"], 1)
        self.assertTrue(result.detected)

    def test_empty_interactions_is_insufficient_history(self) -> None:
        result = self.detector.detect("senior-1", [])
        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertIsNone(result.as_of)
        self.assertFalse(result.detected)

    def test_zero_variance_reference_does_not_raise_or_falsely_flag(self) -> None:
        history = _latency_history([25, 25, 25, 25, 25, 25, 25, 25, 25, 25, 25, 25])
        result = self.detector.detect("senior-1", history)
        self.assertFalse(result.detected)

    def test_only_missed_checkins_evaluates_rate_not_latency(self) -> None:
        history = [
            _interaction(occurred_at=START + timedelta(days=i), latency_minutes=20)
            for i in range(6)
        ] + [
            _interaction(occurred_at=START + timedelta(days=6 + i), missed_checkin=True)
            for i in range(8)
        ]
        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        rate = next(
            c for c in result.contributions if c.signal == "missed_checkin_rate"
        )
        self.assertEqual(latency.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertEqual(rate.status, DetectionStatus.OK)

    def test_package_exports_detector(self) -> None:
        self.assertIs(ExportedDetector, ChangeDetector)
        self.assertIsInstance(ExportedConfig(), ChangeDetectorConfig)


if __name__ == "__main__":
    unittest.main()
