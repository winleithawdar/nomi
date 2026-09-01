from __future__ import annotations

from datetime import datetime

from nomi_backend.detection.contract import (
  ChangeDirection,
  Confidence,
  DetectionKind,
  DetectionResult,
  DetectionStatus,
  SignalContribution,
)


def detection_to_dict(detection: DetectionResult) -> dict:
  return detection.to_dict()


def detection_from_dict(payload: dict) -> DetectionResult:
  contributions = [
    SignalContribution(
      signal=item["signal"],
      status=DetectionStatus(item["status"]),
      flagged=item["flagged"],
      direction=ChangeDirection(item["direction"]),
      baseline_mean=item.get("baseline_mean"),
      recent_mean=item.get("recent_mean"),
      deviation_pct=item.get("deviation_pct"),
      standardized_shift=item.get("standardized_shift"),
      methods_fired=list(item.get("methods_fired", [])),
      estimated_onset=_parse_datetime(item.get("estimated_onset")),
      recent_series=list(item.get("recent_series", [])),
    )
    for item in payload.get("contributions", [])
  ]
  return DetectionResult(
    senior_id=payload["senior_id"],
    kind=DetectionKind(payload["kind"]),
    detected=payload["detected"],
    status=DetectionStatus(payload["status"]),
    as_of=_parse_datetime(payload.get("as_of")),
    confidence=Confidence(payload["confidence"]),
    direction=ChangeDirection(payload["direction"]),
    contributions=contributions,
    summary=payload.get("summary", ""),
    metadata=dict(payload.get("metadata", {})),
  )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
  if value is None:
    return None
  if isinstance(value, datetime):
    return value
  return datetime.fromisoformat(value)
