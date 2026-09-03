from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from nomi_backend.detection.contract import (
  Confidence,
  DetectionKind,
  DetectionResult,
  DetectionStatus,
)
from nomi_backend.verification.alerts import (
  build_check_in_message,
  build_context,
  build_suggested_action,
  build_verification_outcome_text,
  build_what_changed,
)
from nomi_backend.verification.models import (
  AlertStatus,
  CaregiverAlert,
  EscalationDecision,
  VerificationEngineConfig,
  VerificationOutcome,
  VerificationProcessResult,
  VerificationRequest,
  VerificationStatus,
)


class VerificationEngine:
  """Senior-first verification and deterministic escalation decision layer."""

  def __init__(self, config: VerificationEngineConfig | None = None) -> None:
    self.config = config or VerificationEngineConfig()

  def should_start_verification(self, detection: DetectionResult) -> bool:
    return detection.detected and detection.status == DetectionStatus.OK

  def start_verification(
    self,
    detection: DetectionResult,
    *,
    now: datetime | None = None,
    senior_name: str | None = None,
    active_verification: VerificationRequest | None = None,
    recent_reassuring: VerificationRequest | None = None,
  ) -> VerificationProcessResult | None:
    if not self.should_start_verification(detection):
      return None

    current_time = now or datetime.now(UTC)

    if active_verification is not None:
      return self._escalate_repeated_change(active_verification, detection, current_time)

    if recent_reassuring is not None and self._is_within_repeated_change_window(
      recent_reassuring, current_time
    ):
      return self._escalate_new_repeated_change(detection, current_time, senior_name)

    verification = VerificationRequest(
      id=str(uuid4()),
      senior_id=detection.senior_id,
      detection=detection,
      status=VerificationStatus.AWAITING_RESPONSE,
      outcome=None,
      escalation_decision=EscalationDecision.NONE,
      check_in_message=build_check_in_message(detection, senior_name),
      created_at=current_time,
      message_sent_at=current_time,
    )
    return VerificationProcessResult(verification=verification)

  def record_response(
    self,
    verification: VerificationRequest,
    outcome: VerificationOutcome,
    *,
    response_text: str | None = None,
    now: datetime | None = None,
  ) -> VerificationProcessResult:
    current_time = now or datetime.now(UTC)

    if verification.status != VerificationStatus.AWAITING_RESPONSE:
      return VerificationProcessResult(verification=verification)

    if outcome == VerificationOutcome.REASSURING:
      resolved = replace(
        verification,
        status=VerificationStatus.RESOLVED_REASSURING,
        outcome=VerificationOutcome.REASSURING,
        escalation_decision=EscalationDecision.NONE,
        response_received_at=current_time,
        response_text=response_text,
        resolved_at=current_time,
      )
      return VerificationProcessResult(verification=resolved)

    if outcome == VerificationOutcome.HELP_NEEDED:
      return self._escalate(
        verification,
        VerificationOutcome.HELP_NEEDED,
        current_time,
        response_text=response_text,
      )

    raise ValueError(f"Unsupported direct response outcome: {outcome.value}")

  def handle_no_response(
    self,
    verification: VerificationRequest,
    *,
    now: datetime | None = None,
  ) -> VerificationProcessResult:
    current_time = now or datetime.now(UTC)

    if verification.status != VerificationStatus.AWAITING_RESPONSE:
      return VerificationProcessResult(verification=verification)

    if not self._should_escalate_no_response(verification.detection):
      resolved = replace(
        verification,
        status=VerificationStatus.RESOLVED_NO_ESCALATION,
        outcome=VerificationOutcome.NO_RESPONSE,
        escalation_decision=EscalationDecision.NONE,
        resolved_at=current_time,
      )
      return VerificationProcessResult(verification=resolved)

    return self._escalate(verification, VerificationOutcome.NO_RESPONSE, current_time)

  def is_no_response_due(
    self,
    verification: VerificationRequest,
    *,
    now: datetime | None = None,
  ) -> bool:
    if verification.status != VerificationStatus.AWAITING_RESPONSE:
      return False
    current_time = now or datetime.now(UTC)
    sent_at = verification.message_sent_at or verification.created_at
    timeout = timedelta(hours=self.config.no_response_timeout_hours)
    return current_time >= sent_at + timeout

  def _should_escalate_no_response(self, detection: DetectionResult) -> bool:
    if detection.kind == DetectionKind.SUSTAINED_CHANGE:
      return True
    return detection.confidence in {Confidence.MODERATE, Confidence.HIGH}

  def _is_within_repeated_change_window(
    self,
    verification: VerificationRequest,
    now: datetime,
  ) -> bool:
    if verification.status != VerificationStatus.RESOLVED_REASSURING:
      return False
    resolved_at = verification.resolved_at or verification.created_at
    cooldown = timedelta(days=self.config.repeated_change_cooldown_days)
    return now <= resolved_at + cooldown

  def _escalate_new_repeated_change(
    self,
    detection: DetectionResult,
    now: datetime,
    senior_name: str | None,
  ) -> VerificationProcessResult:
    verification = VerificationRequest(
      id=str(uuid4()),
      senior_id=detection.senior_id,
      detection=detection,
      status=VerificationStatus.ESCALATED,
      outcome=VerificationOutcome.REPEATED_CHANGE,
      escalation_decision=EscalationDecision.CAREGIVER_ALERT,
      check_in_message=build_check_in_message(detection, senior_name),
      created_at=now,
      message_sent_at=now,
      resolved_at=now,
    )
    alert = self._build_alert(
      senior_id=detection.senior_id,
      verification_id=verification.id,
      detection=detection,
      outcome=VerificationOutcome.REPEATED_CHANGE,
      response_text=None,
      created_at=now,
    )
    return VerificationProcessResult(
      verification=verification,
      alert=alert,
      caregiver_message=self._caregiver_delivery_text(alert),
    )

  def _escalate_repeated_change(
    self,
    prior_verification: VerificationRequest,
    detection: DetectionResult,
    now: datetime,
  ) -> VerificationProcessResult:
    updated_prior = replace(
      prior_verification,
      status=VerificationStatus.ESCALATED,
      outcome=VerificationOutcome.REPEATED_CHANGE,
      escalation_decision=EscalationDecision.CAREGIVER_ALERT,
      resolved_at=now,
    )
    alert = self._build_alert(
      senior_id=detection.senior_id,
      verification_id=updated_prior.id,
      detection=detection,
      outcome=VerificationOutcome.REPEATED_CHANGE,
      response_text=None,
      created_at=now,
    )
    return VerificationProcessResult(
      verification=updated_prior,
      alert=alert,
      caregiver_message=self._caregiver_delivery_text(alert),
    )

  def _escalate(
    self,
    verification: VerificationRequest,
    outcome: VerificationOutcome,
    now: datetime,
    *,
    response_text: str | None = None,
  ) -> VerificationProcessResult:
    escalated = replace(
      verification,
      status=VerificationStatus.ESCALATED,
      outcome=outcome,
      escalation_decision=EscalationDecision.CAREGIVER_ALERT,
      response_received_at=now if response_text is not None else verification.response_received_at,
      response_text=response_text,
      resolved_at=now,
    )
    alert = self._build_alert(
      senior_id=verification.senior_id,
      verification_id=verification.id,
      detection=verification.detection,
      outcome=outcome,
      response_text=response_text,
      created_at=now,
    )
    return VerificationProcessResult(
      verification=escalated,
      alert=alert,
      caregiver_message=self._caregiver_delivery_text(alert),
    )

  def _build_alert(
    self,
    *,
    senior_id: str,
    verification_id: str,
    detection: DetectionResult,
    outcome: VerificationOutcome,
    response_text: str | None,
    created_at: datetime,
  ) -> CaregiverAlert:
    return CaregiverAlert(
      id=str(uuid4()),
      senior_id=senior_id,
      verification_request_id=verification_id,
      what_changed=build_what_changed(detection),
      context=build_context(detection),
      verification_outcome=build_verification_outcome_text(outcome, response_text),
      suggested_action=build_suggested_action(outcome, detection),
      detection_summary=detection.summary,
      status=AlertStatus.PENDING,
      created_at=created_at,
    )

  def _caregiver_delivery_text(self, alert: CaregiverAlert) -> str:
    return (
      f"Nomi noticed a change in usual behaviour.\n\n"
      f"What changed: {alert.what_changed}\n\n"
      f"Context: {alert.context}\n\n"
      f"Verification: {alert.verification_outcome}\n\n"
      f"Suggested next step: {alert.suggested_action}"
    )
