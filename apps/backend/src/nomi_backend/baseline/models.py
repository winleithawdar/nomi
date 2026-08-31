from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class BaselineStatus(str, Enum):
    LEARNING = "learning"
    STABLE = "stable"


class SignalStatus(str, Enum):
    LEARNING = "learning"
    STABLE = "stable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SeniorInteraction:
    senior_id: str
    occurred_at: datetime
    interaction_type: str
    missed_checkin: bool = False
    checkin_sent_at: datetime | None = None
    response_received_at: datetime | None = None
    wellbeing_score: float | None = None
    checkin_id: str | None = None
    source: str = "nomi"

    @property
    def response_latency_minutes(self) -> float | None:
        if self.checkin_sent_at is None or self.response_received_at is None:
            return None
        delta = self.response_received_at - self.checkin_sent_at
        return delta.total_seconds() / 60.0


@dataclass(frozen=True)
class NumericSignalBaseline:
    status: SignalStatus
    observation_count: int
    latest_value: float | None
    mean: float | None
    median: float | None
    stddev: float | None
    latest_deviation_from_mean: float | None


@dataclass(frozen=True)
class BinarySignalBaseline:
    status: SignalStatus
    observation_count: int
    positive_count: int
    rate: float | None
    latest_value: int | None


@dataclass(frozen=True)
class SeniorBaseline:
    senior_id: str
    as_of: datetime | None
    status: BaselineStatus
    min_observations_for_stable: int
    total_interactions: int
    response_latency_minutes: NumericSignalBaseline
    missed_checkin_rate: BinarySignalBaseline
    interaction_frequency: NumericSignalBaseline
    wellbeing_score: NumericSignalBaseline
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
