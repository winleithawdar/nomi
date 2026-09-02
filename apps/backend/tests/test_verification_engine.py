from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime, timedelta
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
from nomi_backend.verification.engine import VerificationEngine
from nomi_backend.verification.models import (
  EscalationDecision,
  VerificationOutcome,
  VerificationRequest,
  VerificationStatus,
)

START = datetime(2026, 8, 30, 9, 0, tzinfo=UTC)


def _contribution(
  *,
  signal: str = "response_latency_minutes",
  flagged: bool = True,
  baseline_mean: float = 25.0,
  recent_mean: float = 55.0,
) -> SignalContribution:
  return SignalContribution(
    signal=signal,
    status=DetectionStatus.OK,
    flagged=flagged,
    direction=ChangeDirection.RISING,
    baseline_mean=baseline_mean,
    recent_mean=recent_mean,
    deviation_pct=0.5,
    standardized_shift=2.0,
    methods_fired=["isolation_forest"],
    recent_series=[{"value": recent_mean}],
  )


def _detection(
  *,
  kind: DetectionKind = DetectionKind.ANOMALY,
  confidence: Confidence = Confidence.MODERATE,
  detected: bool = True,
  status: DetectionStatus = DetectionStatus.OK,
  senior_id: str = "senior-1",
  summary: str = "Response times have been slower than usual.",
) -> DetectionResult:
  return DetectionResult(
    senior_id=senior_id,
    kind=kind,
    detected=detected,
    status=status,
    as_of=START,
    confidence=confidence,
    direction=ChangeDirection.RISING,
    contributions=[_contribution()],
    summary=summary,
  )


def _awaiting_verification(
  detection: DetectionResult,
  *,
  verification_id: str = "verify-1",
  created_at: datetime = START,
) -> VerificationRequest:
  engine = VerificationEngine()
  result = engine.start_verification(detection, now=created_at)
  assert result is not None
  return result.verification


class VerificationEngineTest(unittest.TestCase):
  def setUp(self) -> None:
    self.engine = VerificationEngine()

  def test_should_not_start_when_detection_not_actionable(self) -> None:
    self.assertFalse(self.engine.should_start_verification(_detection(detected=False)))
    self.assertFalse(
      self.engine.should_start_verification(
        _detection(status=DetectionStatus.INSUFFICIENT_HISTORY)
      )
    )

  def test_start_verification_creates_senior_check_in(self) -> None:
    detection = _detection()
    result = self.engine.start_verification(detection, now=START, senior_name="Mdm Tan")

    self.assertIsNotNone(result)
    assert result is not None
    verification = result.verification
    self.assertEqual(verification.status, VerificationStatus.AWAITING_RESPONSE)
    self.assertEqual(verification.escalation_decision, EscalationDecision.NONE)
    self.assertIn("Mdm Tan", verification.check_in_message)
    self.assertIn("checking in", verification.check_in_message.lower())
    self.assertIsNone(result.alert)

  def test_reassuring_response_resolves_without_escalation(self) -> None:
    detection = _detection()
    verification = _awaiting_verification(detection)
    result = self.engine.record_response(
      verification,
      VerificationOutcome.REASSURING,
      response_text="I'm fine, just busy today",
      now=START + timedelta(hours=1),
    )

    self.assertEqual(result.verification.status, VerificationStatus.RESOLVED_REASSURING)
    self.assertEqual(result.verification.outcome, VerificationOutcome.REASSURING)
    self.assertEqual(result.verification.escalation_decision, EscalationDecision.NONE)
    self.assertIsNone(result.alert)

  def test_help_needed_response_escalates_with_contextual_alert(self) -> None:
    detection = _detection()
    verification = _awaiting_verification(detection)
    result = self.engine.record_response(
      verification,
      VerificationOutcome.HELP_NEEDED,
      response_text="I could use some help",
      now=START + timedelta(hours=1),
    )

    self.assertEqual(result.verification.status, VerificationStatus.ESCALATED)
    self.assertEqual(result.verification.outcome, VerificationOutcome.HELP_NEEDED)
    self.assertEqual(result.verification.escalation_decision, EscalationDecision.CAREGIVER_ALERT)
    self.assertIsNotNone(result.alert)
    assert result.alert is not None
    self.assertIn("help", result.alert.verification_outcome.lower())
    self.assertIn("reach out", result.alert.suggested_action.lower())
    self.assertIn(detection.summary, result.alert.what_changed)
    self.assertIsNotNone(result.caregiver_message)

  def test_no_response_on_low_confidence_anomaly_does_not_escalate(self) -> None:
    detection = _detection(confidence=Confidence.LOW)
    verification = _awaiting_verification(detection)
    result = self.engine.handle_no_response(verification, now=START + timedelta(hours=5))

    self.assertEqual(result.verification.status, VerificationStatus.RESOLVED_NO_ESCALATION)
    self.assertEqual(result.verification.outcome, VerificationOutcome.NO_RESPONSE)
    self.assertEqual(result.verification.escalation_decision, EscalationDecision.NONE)
    self.assertIsNone(result.alert)

  def test_no_response_on_high_confidence_anomaly_escalates(self) -> None:
    detection = _detection(confidence=Confidence.HIGH)
    verification = _awaiting_verification(detection)
    result = self.engine.handle_no_response(verification, now=START + timedelta(hours=5))

    self.assertEqual(result.verification.status, VerificationStatus.ESCALATED)
    self.assertEqual(result.verification.outcome, VerificationOutcome.NO_RESPONSE)
    self.assertIsNotNone(result.alert)
    assert result.alert is not None
    self.assertIn("did not respond", result.alert.verification_outcome.lower())
    self.assertIn("phone call", result.alert.suggested_action.lower())

  def test_no_response_on_sustained_change_always_escalates(self) -> None:
    detection = _detection(kind=DetectionKind.SUSTAINED_CHANGE, confidence=Confidence.LOW)
    verification = _awaiting_verification(detection)
    result = self.engine.handle_no_response(verification, now=START + timedelta(hours=5))

    self.assertEqual(result.verification.status, VerificationStatus.ESCALATED)
    self.assertEqual(result.verification.outcome, VerificationOutcome.NO_RESPONSE)
    self.assertIsNotNone(result.alert)

  def test_repeated_change_after_reassuring_escalates(self) -> None:
    first_detection = _detection(summary="First slower response pattern.")
    first_verification = _awaiting_verification(first_detection, created_at=START)
    reassuring = self.engine.record_response(
      first_verification,
      VerificationOutcome.REASSURING,
      now=START + timedelta(hours=1),
    ).verification

    second_detection = _detection(summary="Another slower response pattern.")
    result = self.engine.start_verification(
      second_detection,
      now=START + timedelta(days=2),
      recent_reassuring=reassuring,
    )

    self.assertIsNotNone(result)
    assert result is not None
    self.assertEqual(result.verification.status, VerificationStatus.ESCALATED)
    self.assertEqual(result.verification.outcome, VerificationOutcome.REPEATED_CHANGE)
    self.assertIsNotNone(result.alert)
    assert result.alert is not None
    self.assertIn("further behavioural change", result.alert.verification_outcome.lower())

  def test_active_verification_with_new_detection_escalates(self) -> None:
    detection = _detection()
    active = _awaiting_verification(detection)
    follow_up = _detection(summary="Pattern continues.")
    result = self.engine.start_verification(
      follow_up,
      now=START + timedelta(hours=2),
      active_verification=active,
    )

    self.assertIsNotNone(result)
    assert result is not None
    self.assertEqual(result.verification.outcome, VerificationOutcome.REPEATED_CHANGE)
    self.assertIsNotNone(result.alert)

  def test_is_no_response_due_respects_timeout(self) -> None:
    detection = _detection()
    verification = _awaiting_verification(detection, created_at=START)

    self.assertFalse(self.engine.is_no_response_due(verification, now=START + timedelta(hours=3)))
    self.assertTrue(self.engine.is_no_response_due(verification, now=START + timedelta(hours=4)))

  def test_alert_copy_avoids_medical_language(self) -> None:
    detection = _detection()
    verification = _awaiting_verification(detection)
    result = self.engine.record_response(
      verification,
      VerificationOutcome.HELP_NEEDED,
      now=START + timedelta(hours=1),
    )

    assert result.alert is not None
    combined = " ".join(
      [
        result.alert.what_changed,
        result.alert.context,
        result.alert.verification_outcome,
        result.alert.suggested_action,
      ]
    ).lower()
    for forbidden in ("diagnosis", "illness", "emergency", "disease", "stroke"):
      self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
  unittest.main()
