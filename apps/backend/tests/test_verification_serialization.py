from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
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
from nomi_backend.verification.serialization import detection_from_dict, detection_to_dict


class DetectionSerializationTest(unittest.TestCase):
    def test_roundtrip_preserves_detection_fields(self) -> None:
        original = DetectionResult(
            senior_id="senior-1",
            kind=DetectionKind.ANOMALY,
            detected=True,
            status=DetectionStatus.OK,
            as_of=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
            confidence=Confidence.HIGH,
            direction=ChangeDirection.FALLING,
            contributions=[
                SignalContribution(
                    signal="wellbeing_score",
                    status=DetectionStatus.OK,
                    flagged=True,
                    direction=ChangeDirection.FALLING,
                    baseline_mean=4.0,
                    recent_mean=2.5,
                    deviation_pct=-0.375,
                    standardized_shift=-1.8,
                    methods_fired=["cusum"],
                    estimated_onset=datetime(2026, 8, 28, 9, 0, tzinfo=UTC),
                    recent_series=[{"occurred_at": "2026-08-28T09:00:00+00:00", "value": 2.5}],
                )
            ],
            summary="Wellbeing score has dipped below the usual range.",
            metadata={"window": 7},
        )

        restored = detection_from_dict(detection_to_dict(original))

        self.assertEqual(restored.senior_id, original.senior_id)
        self.assertEqual(restored.kind, original.kind)
        self.assertEqual(restored.confidence, original.confidence)
        self.assertEqual(restored.summary, original.summary)
        self.assertEqual(len(restored.contributions), 1)
        self.assertEqual(restored.contributions[0].signal, "wellbeing_score")
        self.assertEqual(restored.contributions[0].methods_fired, ["cusum"])


if __name__ == "__main__":
    unittest.main()
