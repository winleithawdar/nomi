from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from nomi_backend.detection.contract import DetectionResult


class VerificationStatus(str, Enum):
  AWAITING_RESPONSE = "awaiting_response"
  RESOLVED_REASSURING = "resolved_reassuring"
  RESOLVED_NO_ESCALATION = "resolved_no_escalation"
  ESCALATED = "escalated"


class VerificationOutcome(str, Enum):
  REASSURING = "reassuring"
  HELP_NEEDED = "help_needed"
  NO_RESPONSE = "no_response"
  REPEATED_CHANGE = "repeated_change"


class EscalationDecision(str, Enum):
  NONE = "none"
  CAREGIVER_ALERT = "caregiver_alert"


class AlertStatus(str, Enum):
  PENDING = "pending"
  DELIVERED = "delivered"


def _plain(value: Any) -> Any:
  if isinstance(value, Enum):
    return value.value
  if isinstance(value, datetime):
    return value.isoformat()
  if is_dataclass(value) and not isinstance(value, type):
    return {key: _plain(item) for key, item in asdict(value).items()}
  if isinstance(value, dict):
    return {key: _plain(item) for key, item in value.items()}
  if isinstance(value, (list, tuple)):
    return [_plain(item) for item in value]
  return value


@dataclass(frozen=True)
class VerificationRequest:
  id: str
  senior_id: str
  detection: DetectionResult
  status: VerificationStatus
  outcome: VerificationOutcome | None
  escalation_decision: EscalationDecision
  check_in_message: str
  created_at: datetime
  message_sent_at: datetime | None = None
  response_received_at: datetime | None = None
  response_text: str | None = None
  resolved_at: datetime | None = None

  def to_dict(self) -> dict:
    payload = _plain(asdict(self))
    payload["detection"] = self.detection.to_dict()
    return payload


@dataclass(frozen=True)
class CaregiverAlert:
  id: str
  senior_id: str
  verification_request_id: str
  what_changed: str
  context: str
  verification_outcome: str
  suggested_action: str
  detection_summary: str
  status: AlertStatus
  created_at: datetime
  delivered_at: datetime | None = None

  def to_dict(self) -> dict:
    return _plain(asdict(self))


@dataclass(frozen=True)
class VerificationProcessResult:
  verification: VerificationRequest
  alert: CaregiverAlert | None = None
  caregiver_message: str | None = None

  def to_dict(self) -> dict:
    payload = {
      "verification": self.verification.to_dict(),
      "alert": self.alert.to_dict() if self.alert else None,
      "caregiver_message": self.caregiver_message,
    }
    return payload


@dataclass(frozen=True)
class VerificationEngineConfig:
  no_response_timeout_hours: int = 4
  repeated_change_cooldown_days: int = 7
