from __future__ import annotations

from datetime import UTC, datetime

from nomi_backend.persistence.repository import VerificationRepository
from nomi_backend.verification.engine import VerificationEngine
from nomi_backend.verification.models import CaregiverAlert, VerificationOutcome, VerificationProcessResult
from nomi_backend.verification.serialization import detection_from_dict

__all__ = ["VerificationService"]


class VerificationService:
  def __init__(
    self,
    repository: VerificationRepository,
    engine: VerificationEngine | None = None,
  ) -> None:
    self.repository = repository
    self.engine = engine or VerificationEngine()

  @classmethod
  def from_session(cls, session) -> VerificationService:
    repository = VerificationRepository(session)
    repository.create_tables()
    return cls(repository)

  def start_from_detection_payload(
    self,
    payload: dict,
    *,
    senior_name: str | None = None,
  ) -> VerificationProcessResult | None:
    detection = detection_from_dict(payload)
    active = self.repository.get_active_verification(detection.senior_id)
    recent_reassuring = self.repository.get_latest_reassuring_verification(detection.senior_id)
    result = self.engine.start_verification(
      detection,
      senior_name=senior_name,
      active_verification=active,
      recent_reassuring=recent_reassuring,
    )
    if result is None:
      return None

    saved_verification = self.repository.save_verification(result.verification)
    if result.alert is not None:
      alert = self.repository.save_alert(result.alert, detection.to_dict())
      return VerificationProcessResult(
        verification=saved_verification,
        alert=alert,
        caregiver_message=result.caregiver_message,
      )
    return VerificationProcessResult(verification=saved_verification)

  def record_response(
    self,
    verification_id: str,
    outcome: VerificationOutcome,
    *,
    response_text: str | None = None,
  ) -> VerificationProcessResult | None:
    verification = self.repository.get_verification(verification_id)
    if verification is None:
      return None

    result = self.engine.record_response(
      verification,
      outcome,
      response_text=response_text,
    )
    saved_verification = self.repository.save_verification(result.verification)
    if result.alert is not None:
      alert = self.repository.save_alert(
        result.alert,
        verification.detection.to_dict(),
      )
      return VerificationProcessResult(
        verification=saved_verification,
        alert=alert,
        caregiver_message=result.caregiver_message,
      )
    return VerificationProcessResult(verification=saved_verification)

  def handle_no_response(self, verification_id: str) -> VerificationProcessResult | None:
    verification = self.repository.get_verification(verification_id)
    if verification is None:
      return None

    result = self.engine.handle_no_response(verification)
    saved_verification = self.repository.save_verification(result.verification)
    if result.alert is not None:
      alert = self.repository.save_alert(
        result.alert,
        verification.detection.to_dict(),
      )
      return VerificationProcessResult(
        verification=saved_verification,
        alert=alert,
        caregiver_message=result.caregiver_message,
      )
    return VerificationProcessResult(verification=saved_verification)

  def mark_alert_delivered(
    self,
    alert_id: str,
    *,
    delivered_at: str | None = None,
  ) -> CaregiverAlert | None:
    timestamp = (
      datetime.fromisoformat(delivered_at) if delivered_at else datetime.now(UTC)
    )
    return self.repository.mark_alert_delivered(alert_id, timestamp)

  def format_caregiver_message(self, alert: CaregiverAlert) -> str:
    return (
      f"Nomi noticed a change in usual behaviour.\n\n"
      f"What changed: {alert.what_changed}\n\n"
      f"Context: {alert.context}\n\n"
      f"Verification: {alert.verification_outcome}\n\n"
      f"Suggested next step: {alert.suggested_action}"
    )
