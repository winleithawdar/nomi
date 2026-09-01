from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.detection.contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)


class DetectionContractTest(unittest.TestCase):
    def test_enum_values_are_the_documented_constants(self) -> None:
        self.assertEqual(DetectionKind.SUSTAINED_CHANGE.value, "sustained_change")
        self.assertEqual(DetectionKind.ANOMALY.value, "anomaly")
        self.assertEqual(DetectionStatus.OK.value, "ok")
        self.assertEqual(DetectionStatus.INSUFFICIENT_HISTORY.value, "insufficient_history")
        self.assertEqual(
            [d.value for d in ChangeDirection],
            ["rising", "falling", "none"],
        )
        self.assertEqual(
            [c.value for c in Confidence],
            ["low", "moderate", "high"],
        )

    def test_to_dict_emits_only_primitives(self) -> None:
        onset = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
        as_of = onset + timedelta(days=4)
        contribution = SignalContribution(
            signal="response_latency_minutes",
            status=DetectionStatus.OK,
            flagged=True,
            direction=ChangeDirection.RISING,
            baseline_mean=25.0,
            recent_mean=35.0,
            deviation_pct=0.4,
            standardized_shift=2.5,
            methods_fired=["level_shift", "cusum"],
            estimated_onset=onset,
            recent_series=[{"occurred_at": onset.isoformat(), "value": 35.0}],
        )
        result = DetectionResult(
            senior_id="senior-1",
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=True,
            status=DetectionStatus.OK,
            as_of=as_of,
            confidence=Confidence.MODERATE,
            direction=ChangeDirection.RISING,
            contributions=[contribution],
            summary="Response latency is running about 40% above the usual baseline.",
            metadata={"dropped_values": 0, "window": 7},
        )

        payload = result.to_dict()

        self.assertEqual(payload["kind"], "sustained_change")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["confidence"], "moderate")
        self.assertEqual(payload["direction"], "rising")
        self.assertEqual(payload["as_of"], as_of.isoformat())
        self.assertEqual(payload["metadata"], {"dropped_values": 0, "window": 7})
        self.assertEqual(len(payload["contributions"]), 1)
        child = payload["contributions"][0]
        self.assertEqual(child["status"], "ok")
        self.assertEqual(child["direction"], "rising")
        self.assertEqual(child["methods_fired"], ["level_shift", "cusum"])
        self.assertEqual(child["estimated_onset"], onset.isoformat())
        self.assertEqual(child["recent_series"][0]["value"], 35.0)

    def test_to_dict_handles_none_datetimes_and_empty_contributions(self) -> None:
        result = DetectionResult(
            senior_id="senior-2",
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=False,
            status=DetectionStatus.INSUFFICIENT_HISTORY,
            as_of=None,
            confidence=Confidence.LOW,
            direction=ChangeDirection.NONE,
            contributions=[],
            summary="",
            metadata={},
        )

        payload = result.to_dict()

        self.assertIsNone(payload["as_of"])
        self.assertEqual(payload["contributions"], [])
        self.assertEqual(payload["direction"], "none")


if __name__ == "__main__":
    unittest.main()
