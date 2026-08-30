from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, median, pstdev

from .models import (
    BaselineStatus,
    BinarySignalBaseline,
    NumericSignalBaseline,
    SeniorBaseline,
    SeniorInteraction,
    SignalStatus,
)


@dataclass(frozen=True)
class BaselineConfig:
    min_observations_for_stable: int = 5
    numeric_window_size: int = 20
    binary_window_size: int = 20
    frequency_window_days: int = 7


class BaselineCalculator:
    def __init__(self, config: BaselineConfig | None = None) -> None:
        self.config = config or BaselineConfig()

    def calculate(
        self,
        senior_id: str,
        interactions: list[SeniorInteraction],
    ) -> SeniorBaseline:
        relevant = sorted(
            [item for item in interactions if item.senior_id == senior_id and item.source == "nomi"],
            key=lambda item: item.occurred_at,
        )

        total_interactions = len(relevant)
        overall_status = (
            BaselineStatus.STABLE
            if total_interactions >= self.config.min_observations_for_stable
            else BaselineStatus.LEARNING
        )

        latency_values = [
            value
            for value in (interaction.response_latency_minutes for interaction in relevant)
            if value is not None
        ]
        missed_values = [1 if interaction.missed_checkin else 0 for interaction in relevant]
        frequency_values = self._interaction_frequency_values(relevant)
        wellbeing_values = [
            interaction.wellbeing_score
            for interaction in relevant
            if interaction.wellbeing_score is not None
        ]

        return SeniorBaseline(
            senior_id=senior_id,
            as_of=relevant[-1].occurred_at if relevant else None,
            status=overall_status,
            min_observations_for_stable=self.config.min_observations_for_stable,
            total_interactions=total_interactions,
            response_latency_minutes=self._numeric_baseline(latency_values),
            missed_checkin_rate=self._binary_baseline(missed_values),
            interaction_frequency=self._numeric_baseline(frequency_values),
            wellbeing_score=self._numeric_baseline(wellbeing_values),
            metadata={
                "numeric_window_size": self.config.numeric_window_size,
                "binary_window_size": self.config.binary_window_size,
                "frequency_window_days": self.config.frequency_window_days,
            },
        )

    def _numeric_baseline(self, values: list[float]) -> NumericSignalBaseline:
        if not values:
            return NumericSignalBaseline(
                status=SignalStatus.UNAVAILABLE,
                observation_count=0,
                latest_value=None,
                mean=None,
                median=None,
                stddev=None,
                latest_deviation_from_mean=None,
            )

        window = values[-self.config.numeric_window_size :]
        current_mean = mean(window)
        latest_value = window[-1]
        status = self._signal_status(len(window))

        return NumericSignalBaseline(
            status=status,
            observation_count=len(window),
            latest_value=latest_value,
            mean=current_mean,
            median=median(window),
            stddev=pstdev(window) if len(window) > 1 else 0.0,
            latest_deviation_from_mean=latest_value - current_mean,
        )

    def _binary_baseline(self, values: list[int]) -> BinarySignalBaseline:
        if not values:
            return BinarySignalBaseline(
                status=SignalStatus.UNAVAILABLE,
                observation_count=0,
                positive_count=0,
                rate=None,
                latest_value=None,
            )

        window = values[-self.config.binary_window_size :]
        positives = sum(window)

        return BinarySignalBaseline(
            status=self._signal_status(len(window)),
            observation_count=len(window),
            positive_count=positives,
            rate=positives / len(window),
            latest_value=window[-1],
        )

    def _interaction_frequency_values(
        self,
        interactions: list[SeniorInteraction],
    ) -> list[float]:
        if not interactions:
            return []

        lookback = timedelta(days=self.config.frequency_window_days)
        window: deque[datetime] = deque()
        frequencies: list[float] = []

        for interaction in interactions:
            while window and interaction.occurred_at - window[0] > lookback:
                window.popleft()
            window.append(interaction.occurred_at)
            frequencies.append(float(len(window)))

        return frequencies

    def _signal_status(self, observation_count: int) -> SignalStatus:
        if observation_count == 0:
            return SignalStatus.UNAVAILABLE
        if observation_count < self.config.min_observations_for_stable:
            return SignalStatus.LEARNING
        return SignalStatus.STABLE
