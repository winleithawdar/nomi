from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from nomi_backend.baseline import SeniorInteraction

SIGNAL_RESPONSE_LATENCY = "response_latency_minutes"
SIGNAL_MISSED_CHECKIN_RATE = "missed_checkin_rate"
SIGNAL_INTERACTION_FREQUENCY = "interaction_frequency"
SIGNAL_WELLBEING = "wellbeing_score"

FREQUENCY_WINDOW_DAYS = 7
DEFAULT_MISSED_RATE_WINDOW = 7


@dataclass(frozen=True)
class SeriesPoint:
    occurred_at: datetime
    value: float


@dataclass(frozen=True)
class SignalSeriesBundle:
    response_latency_minutes: list[SeriesPoint]
    missed_checkin_rate: list[SeriesPoint]
    interaction_frequency: list[SeriesPoint]
    wellbeing_score: list[SeriesPoint]
    dropped_values: int

    def as_map(self) -> dict[str, list[SeriesPoint]]:
        return {
            SIGNAL_RESPONSE_LATENCY: self.response_latency_minutes,
            SIGNAL_MISSED_CHECKIN_RATE: self.missed_checkin_rate,
            SIGNAL_INTERACTION_FREQUENCY: self.interaction_frequency,
            SIGNAL_WELLBEING: self.wellbeing_score,
        }


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def build_signal_series(
    interactions: list[SeniorInteraction],
    *,
    frequency_window_days: int = FREQUENCY_WINDOW_DAYS,
    missed_rate_window: int = DEFAULT_MISSED_RATE_WINDOW,
) -> SignalSeriesBundle:
    ordered = sorted(
        (item for item in interactions if item.source == "nomi"),
        key=lambda item: item.occurred_at,
    )

    latency: list[SeriesPoint] = []
    missed_rate: list[SeriesPoint] = []
    frequency: list[SeriesPoint] = []
    wellbeing: list[SeriesPoint] = []
    dropped = 0

    missed_flags: deque[int] = deque(maxlen=missed_rate_window)
    freq_window: deque[datetime] = deque()
    lookback = timedelta(days=frequency_window_days)

    for item in ordered:
        try:
            raw_latency = item.response_latency_minutes
        except (TypeError, ValueError):
            raw_latency = None
        if raw_latency is not None:
            value = _finite_number(raw_latency)
            if value is None or value < 0:
                dropped += 1
            else:
                latency.append(SeriesPoint(item.occurred_at, value))

        missed_flags.append(1 if item.missed_checkin else 0)
        missed_rate.append(
            SeriesPoint(item.occurred_at, sum(missed_flags) / len(missed_flags))
        )

        while freq_window and item.occurred_at - freq_window[0] > lookback:
            freq_window.popleft()
        freq_window.append(item.occurred_at)
        frequency.append(SeriesPoint(item.occurred_at, float(len(freq_window))))

        if item.wellbeing_score is not None:
            value = _finite_number(item.wellbeing_score)
            if value is None:
                dropped += 1
            else:
                wellbeing.append(SeriesPoint(item.occurred_at, value))

    return SignalSeriesBundle(
        response_latency_minutes=latency,
        missed_checkin_rate=missed_rate,
        interaction_frequency=frequency,
        wellbeing_score=wellbeing,
        dropped_values=dropped,
    )
