from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi import HTTPException

from nomi_backend.api.app import get_latest_anomaly
from nomi_backend.baseline import SeniorInteraction
from nomi_backend.detection import AnomalyDetector
from nomi_backend.detection.contract import (
    ChangeDirection,
    DetectionKind,
    DetectionStatus,
)

START = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _interaction(
    index: int,
    latency: float | None,
    *,
    missed_checkin: bool = False,
    wellbeing_score: float | None = None,
    source: str = "nomi",
) -> SeniorInteraction:
    occurred_at = START + timedelta(days=index)
    sent_at = responded_at = None
    if latency is not None:
        sent_at = occurred_at - timedelta(minutes=latency)
        responded_at = occurred_at
    return SeniorInteraction(
        senior_id="senior-1",
        occurred_at=occurred_at,
        interaction_type="checkin_missed" if missed_checkin else "checkin_response",
        missed_checkin=missed_checkin,
        checkin_sent_at=sent_at,
        response_received_at=responded_at,
        wellbeing_score=wellbeing_score,
        source=source,
    )


def _normal_history(count: int = 32, *, wellbeing: bool = True) -> list[SeniorInteraction]:
    pattern = [24.0, 25.0, 26.0, 24.0, 27.0, 25.0]
    return [
        _interaction(
            index,
            pattern[index % len(pattern)],
            wellbeing_score=4.0 if wellbeing else None,
        )
        for index in range(count)
    ]


class AnomalyDetectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = AnomalyDetector()

    def test_normal_observation_is_not_flagged(self) -> None:
        result = self.detector.detect("senior-1", _normal_history())

        self.assertEqual(result.kind, DetectionKind.ANOMALY)
        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertFalse(result.detected)
        self.assertEqual(result.direction, ChangeDirection.NONE)

    def test_obvious_late_response_is_explainable_anomaly(self) -> None:
        history = _normal_history(31)
        history.append(_interaction(31, 120.0, wellbeing_score=4.0))

        result = self.detector.detect("senior-1", history)
        latency = next(
            item for item in result.contributions if item.signal == "response_latency_minutes"
        )

        self.assertTrue(result.detected)
        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertTrue(latency.flagged)
        self.assertEqual(latency.direction, ChangeDirection.RISING)
        self.assertGreater(latency.recent_mean, latency.baseline_mean)
        self.assertGreater(latency.standardized_shift, 0)
        self.assertIn("personal_deviation_guard", latency.methods_fired)
        self.assertEqual(latency.estimated_onset, history[-1].occurred_at)

    def test_learning_history_is_not_scored(self) -> None:
        result = self.detector.detect("senior-1", _normal_history(10))

        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertFalse(result.detected)
        self.assertEqual(result.metadata["minimum_training_observations"], 20)

    def test_missing_optional_wellbeing_uses_reliable_core_features(self) -> None:
        history = _normal_history(31, wellbeing=False)
        history.append(_interaction(31, 115.0))

        result = self.detector.detect("senior-1", history)
        wellbeing = next(
            item for item in result.contributions if item.signal == "wellbeing_score"
        )

        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertTrue(result.detected)
        self.assertEqual(wellbeing.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertNotIn("wellbeing_score", result.metadata["feature_profile"])

    def test_malformed_optional_value_is_dropped_without_breaking_detection(self) -> None:
        history = _normal_history(31, wellbeing=True)
        history.append(_interaction(31, 120.0, wellbeing_score=math.nan))

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.metadata["dropped_values"], 1)

    def test_latest_observation_is_not_part_of_its_training_history(self) -> None:
        history = _normal_history(31)
        history.append(_interaction(31, 120.0, wellbeing_score=4.0))

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.metadata["training_observations"], 24)

    def test_non_nomi_observations_are_ignored(self) -> None:
        history = _normal_history(32)
        history.append(_interaction(33, 400.0, source="import"))

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.as_of, history[-2].occurred_at)
        self.assertFalse(result.detected)

    def test_duplicate_timestamp_does_not_backfill_missing_latency(self) -> None:
        history = _normal_history(31)
        latest = history[-1]
        history.append(
            SeniorInteraction(
                senior_id="senior-1",
                occurred_at=latest.occurred_at,
                interaction_type="checkin_missed",
                missed_checkin=True,
            )
        )

        result = self.detector.detect("senior-1", history)
        latency = next(
            item for item in result.contributions if item.signal == "response_latency_minutes"
        )

        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertEqual(latency.status, DetectionStatus.INSUFFICIENT_HISTORY)

    def test_first_unusual_missed_checkin_is_detected_by_personal_guard(self) -> None:
        history = _normal_history(31, wellbeing=False)
        history.append(_interaction(31, None, missed_checkin=True))

        result = self.detector.detect("senior-1", history)
        missed = next(
            item for item in result.contributions if item.signal == "missed_checkin_rate"
        )

        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertTrue(result.detected)
        self.assertTrue(missed.flagged)
        self.assertIn("personal_deviation_guard", missed.methods_fired)


class AnomalyApiTest(unittest.TestCase):
    def test_returns_a_structured_latest_anomaly_result(self) -> None:
        payload = get_latest_anomaly("senior-1")

        self.assertEqual(payload["senior_id"], "senior-1")
        self.assertEqual(payload["kind"], "anomaly")
        self.assertIn(payload["status"], {"ok", "insufficient_history"})

    def test_returns_not_found_for_unknown_senior(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            get_latest_anomaly("unknown")

        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
