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
from nomi_backend.verification.alerts import (
    build_check_in_message,
    build_context,
    build_suggested_action,
    build_verification_outcome_text,
    build_what_changed,
)
from nomi_backend.verification.models import VerificationOutcome


def _detection() -> DetectionResult:
    return DetectionResult(
        senior_id="senior-1",
        kind=DetectionKind.SUSTAINED_CHANGE,
        detected=True,
        status=DetectionStatus.OK,
        as_of=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
        confidence=Confidence.MODERATE,
        direction=ChangeDirection.RISING,
        contributions=[
            SignalContribution(
                signal="response_latency_minutes",
                status=DetectionStatus.OK,
                flagged=True,
                direction=ChangeDirection.RISING,
                baseline_mean=25.0,
                recent_mean=40.0,
                deviation_pct=0.6,
                standardized_shift=2.0,
                methods_fired=["level_shift"],
                estimated_onset=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
                recent_series=[{"occurred_at": "2026-09-01T09:00:00+00:00", "value": 40.0}],
            )
        ],
        summary="Response latency is running above the usual baseline.",
        metadata={},
    )


class CaregiverAlertBuilderTest(unittest.TestCase):
    def test_what_changed_uses_detection_summary_when_present(self) -> None:
        detection = _detection()
        self.assertEqual(build_what_changed(detection), detection.summary)

    def test_context_mentions_recent_observations(self) -> None:
        context = build_context(_detection())
        self.assertIn("recent observations", context)
        self.assertIn("sustained shift", context)

    def test_verification_outcome_text_avoids_medical_language(self) -> None:
        text = build_verification_outcome_text(
            VerificationOutcome.NO_RESPONSE,
            response_text=None,
        )
        self.assertNotIn("diagnos", text.lower())
        self.assertIn("did not respond", text)

    def test_suggested_action_for_help_needed_is_practical(self) -> None:
        action = build_suggested_action(VerificationOutcome.HELP_NEEDED, _detection())
        self.assertIn("reach out", action.lower())

    def test_check_in_message_is_senior_friendly(self) -> None:
        message = build_check_in_message(_detection(), senior_name="Mdm Tan")
        self.assertIn("Mdm Tan", message)
        self.assertIn("checking in", message.lower())


if __name__ == "__main__":
    unittest.main()
