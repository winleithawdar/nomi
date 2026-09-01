from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class DetectionKind(str, Enum):
    ANOMALY = "anomaly"
    SUSTAINED_CHANGE = "sustained_change"


class DetectionStatus(str, Enum):
    OK = "ok"
    INSUFFICIENT_HISTORY = "insufficient_history"


class ChangeDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    NONE = "none"


class Confidence(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


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
class SignalContribution:
    signal: str
    status: DetectionStatus
    flagged: bool
    direction: ChangeDirection
    baseline_mean: float | None
    recent_mean: float | None
    deviation_pct: float | None
    standardized_shift: float | None
    methods_fired: list[str] = field(default_factory=list)
    estimated_onset: datetime | None = None
    recent_series: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _plain(asdict(self))


@dataclass(frozen=True)
class DetectionResult:
    senior_id: str
    kind: DetectionKind
    detected: bool
    status: DetectionStatus
    as_of: datetime | None
    confidence: Confidence
    direction: ChangeDirection
    contributions: list[SignalContribution] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _plain(asdict(self))
