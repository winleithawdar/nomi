from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from nomi_backend.baseline import SeniorBaseline, SeniorInteraction
from nomi_backend.detection.contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)
from nomi_backend.detection.features import (
    SIGNAL_INTERACTION_FREQUENCY,
    SIGNAL_MISSED_CHECKIN_RATE,
    SIGNAL_RESPONSE_LATENCY,
    SIGNAL_WELLBEING,
    build_signal_series,
)


@dataclass(frozen=True)
class FixedThresholdConfig:
    latency_minutes_max: float = 45.0
    missed_rate_max: float = 0.3
    frequency_min: float = 3.0
    wellbeing_min: float = 3.0
    recent_window_points: int = 7
    recent_min_points: int = 4


_RISING_LIMIT = {SIGNAL_RESPONSE_LATENCY, SIGNAL_MISSED_CHECKIN_RATE}


class FixedThresholdDetector:
    def __init__(self, config: FixedThresholdConfig | None = None) -> None:
        self.config = config or FixedThresholdConfig()

    def detect(
        self,
        senior_id: str,
        interactions: list[SeniorInteraction],
        baseline: SeniorBaseline | None = None,
    ) -> DetectionResult:
        own = [item for item in interactions if item.senior_id == senior_id]
        bundle = build_signal_series(
            own, missed_rate_window=self.config.recent_window_points
        )
        series_map = bundle.as_map()
        as_of = max((item.occurred_at for item in own), default=None)

        limits = {
            SIGNAL_RESPONSE_LATENCY: self.config.latency_minutes_max,
            SIGNAL_MISSED_CHECKIN_RATE: self.config.missed_rate_max,
            SIGNAL_INTERACTION_FREQUENCY: self.config.frequency_min,
            SIGNAL_WELLBEING: self.config.wellbeing_min,
        }

        contributions: list[SignalContribution] = []
        for signal, limit in limits.items():
            points = series_map[signal][-self.config.recent_window_points :]
            if len(points) < self.config.recent_min_points:
                contributions.append(
                    SignalContribution(
                        signal=signal,
                        status=DetectionStatus.INSUFFICIENT_HISTORY,
                        flagged=False,
                        direction=ChangeDirection.NONE,
                        baseline_mean=None,
                        recent_mean=None,
                        deviation_pct=None,
                        standardized_shift=None,
                        methods_fired=[],
                        estimated_onset=None,
                        recent_series=[
                            {"occurred_at": p.occurred_at.isoformat(), "value": p.value}
                            for p in points
                        ],
                    )
                )
                continue
            recent_mean = fmean(point.value for point in points)
            if signal in _RISING_LIMIT:
                flagged = recent_mean > limit
                direction = ChangeDirection.RISING if flagged else ChangeDirection.NONE
            else:
                flagged = recent_mean < limit
                direction = ChangeDirection.FALLING if flagged else ChangeDirection.NONE
            contributions.append(
                SignalContribution(
                    signal=signal,
                    status=DetectionStatus.OK,
                    flagged=flagged,
                    direction=direction,
                    baseline_mean=limit,
                    recent_mean=recent_mean,
                    deviation_pct=None,
                    standardized_shift=None,
                    methods_fired=["fixed_threshold"] if flagged else [],
                    estimated_onset=None,
                    recent_series=[
                        {"occurred_at": p.occurred_at.isoformat(), "value": p.value}
                        for p in points
                    ],
                )
            )

        evaluated = [c for c in contributions if c.status == DetectionStatus.OK]
        flagged = [c for c in contributions if c.flagged]
        if not evaluated:
            status = DetectionStatus.INSUFFICIENT_HISTORY
        else:
            status = DetectionStatus.OK
        return DetectionResult(
            senior_id=senior_id,
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=bool(flagged),
            status=status,
            as_of=as_of,
            confidence=Confidence.MODERATE if flagged else Confidence.LOW,
            direction=flagged[0].direction if flagged else ChangeDirection.NONE,
            contributions=contributions,
            summary="",
            metadata={"detector": "fixed_threshold"},
        )
