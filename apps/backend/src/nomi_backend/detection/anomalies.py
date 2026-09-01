from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from statistics import fmean, median, pstdev

import numpy
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from nomi_backend.baseline import (
    BaselineCalculator,
    SeniorBaseline,
    SeniorInteraction,
    SignalStatus,
)
from nomi_backend.detection.contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)
from nomi_backend.detection.features import (
    FREQUENCY_WINDOW_DAYS,
    SIGNAL_INTERACTION_FREQUENCY,
    SIGNAL_MISSED_CHECKIN_RATE,
    SIGNAL_RESPONSE_LATENCY,
    SIGNAL_WELLBEING,
    SeriesPoint,
    build_signal_series,
)

_SIGNALS = (
    SIGNAL_RESPONSE_LATENCY,
    SIGNAL_MISSED_CHECKIN_RATE,
    SIGNAL_INTERACTION_FREQUENCY,
    SIGNAL_WELLBEING,
)

_NUMERIC_BASELINE_ATTR = {
    SIGNAL_RESPONSE_LATENCY: "response_latency_minutes",
    SIGNAL_INTERACTION_FREQUENCY: "interaction_frequency",
    SIGNAL_WELLBEING: "wellbeing_score",
}

_SUMMARY_LABEL = {
    SIGNAL_RESPONSE_LATENCY: "Response latency",
    SIGNAL_MISSED_CHECKIN_RATE: "Missed check-ins",
    SIGNAL_INTERACTION_FREQUENCY: "Interaction frequency",
    SIGNAL_WELLBEING: "Self-reported wellbeing",
}


@dataclass(frozen=True)
class AnomalyDetectorConfig:
    """Quality gates and reproducibility settings for point-anomaly scoring."""

    min_training_points: int = 20
    max_training_points: int = 60
    min_feature_count: int = 1
    contamination: float = 0.05
    n_estimators: int = 200
    random_state: int = 41
    explanation_window_points: int = 7
    relative_scale_floor: float = 0.1
    personal_deviation_z_threshold: float = 3.5
    epsilon: float = 1e-6


@dataclass(frozen=True)
class _FeatureRow:
    occurred_at: datetime
    values: dict[str, float]


def _signal_baseline_status(signal: str, baseline: SeniorBaseline) -> SignalStatus:
    if signal == SIGNAL_MISSED_CHECKIN_RATE:
        return baseline.missed_checkin_rate.status
    return getattr(baseline, _NUMERIC_BASELINE_ATTR[signal]).status


class AnomalyDetector:
    """Detect a sudden unusual observation against one senior's own history."""

    def __init__(self, config: AnomalyDetectorConfig | None = None) -> None:
        self.config = config or AnomalyDetectorConfig()
        self._baseline_calculator = BaselineCalculator()

    def detect(
        self,
        senior_id: str,
        interactions: list[SeniorInteraction],
        baseline: SeniorBaseline | None = None,
    ) -> DetectionResult:
        """Score the latest Nomi observation using only earlier observations as training."""
        own = sorted(
            (
                item
                for item in interactions
                if item.senior_id == senior_id and item.source == "nomi"
            ),
            key=lambda item: item.occurred_at,
        )
        as_of = own[-1].occurred_at if own else None
        if len(own) < 2:
            return self._insufficient_result(senior_id, as_of, [], dropped_values=0)

        history = own[:-1]
        if baseline is None:
            # The observation being scored must never influence its own baseline.
            baseline = self._baseline_calculator.calculate(senior_id, history)

        rows, dropped_values = self._causal_feature_rows(own)
        observation = rows[-1]
        active_signals, training_rows = self._select_feature_profile(
            rows[:-1], observation, baseline
        )
        contributions = self._empty_contributions(rows, active_signals)

        if len(active_signals) < self.config.min_feature_count or len(training_rows) < self.config.min_training_points:
            return self._insufficient_result(
                senior_id,
                as_of,
                contributions,
                dropped_values=dropped_values,
                feature_profile=active_signals,
                training_observations=len(training_rows),
            )

        training_rows = training_rows[-self.config.max_training_points :]
        raw_training = numpy.asarray(
            [[row.values[signal] for signal in active_signals] for row in training_rows],
            dtype=float,
        )
        transformed_training = self._transform_matrix(raw_training, active_signals)
        scaler = RobustScaler()
        scaled_training = scaler.fit_transform(transformed_training)
        model = IsolationForest(
            contamination=self.config.contamination,
            n_estimators=self.config.n_estimators,
            random_state=self.config.random_state,
            max_samples=1.0,
        )
        model.fit(scaled_training)

        raw_observation = numpy.asarray(
            [[observation.values[signal] for signal in active_signals]], dtype=float
        )
        scaled_observation = scaler.transform(
            self._transform_matrix(raw_observation, active_signals)
        )
        training_scores = -model.score_samples(scaled_training)
        observation_score = float(-model.score_samples(scaled_observation)[0])
        # Calibrate against this senior's own recent normal observations. The score
        # stays internal so the API never presents a generic risk score.
        threshold = float(numpy.quantile(training_scores, 1.0 - self.config.contamination))
        model_detected = observation_score > threshold
        guarded_signals = self._personal_deviation_signals(
            observation, training_rows, active_signals
        )
        # A forest cannot distinguish values beyond the largest training point
        # once they land in the same terminal leaf. A robust, per-senior guard
        # preserves sensitivity to an extreme one-signal departure without using
        # a population threshold or exposing a risk score.
        detected = model_detected or bool(guarded_signals)

        contributions = self._explain(
            model=model,
            observation_score=observation_score,
            scaled_observation=scaled_observation,
            scaled_training=scaled_training,
            active_signals=active_signals,
            training_rows=training_rows,
            all_rows=rows,
            detected=detected,
            model_detected=model_detected,
            guarded_signals=guarded_signals,
        )
        flagged = [item for item in contributions if item.flagged]
        direction = self._dominant_direction(flagged)

        return DetectionResult(
            senior_id=senior_id,
            kind=DetectionKind.ANOMALY,
            detected=detected,
            status=DetectionStatus.OK,
            as_of=as_of,
            confidence=self._confidence(flagged),
            direction=direction,
            contributions=contributions,
            summary=self._summary(flagged, detected),
            metadata={
                "dropped_values": dropped_values,
                "feature_profile": active_signals,
                "training_observations": len(training_rows),
                "threshold_source": "personal_training_quantile",
                "detection_methods": [
                    method
                    for method, used in (
                        ("isolation_forest", model_detected),
                        ("personal_deviation_guard", bool(guarded_signals)),
                    )
                    if used
                ],
            },
        )

    def _causal_feature_rows(
        self, interactions: list[SeniorInteraction]
    ) -> tuple[list[_FeatureRow], int]:
        rows: list[_FeatureRow] = []
        for index, interaction in enumerate(interactions):
            # Building each row from its prefix keeps derived rolling features causal.
            series = build_signal_series(interactions[: index + 1]).as_map()
            values = {}
            for signal in (SIGNAL_MISSED_CHECKIN_RATE, SIGNAL_INTERACTION_FREQUENCY):
                if series[signal]:
                    values[signal] = series[signal][-1].value
            latency = self._finite_latency(interaction)
            if latency is not None and series[SIGNAL_RESPONSE_LATENCY]:
                values[SIGNAL_RESPONSE_LATENCY] = series[SIGNAL_RESPONSE_LATENCY][-1].value
            wellbeing = self._finite_number(interaction.wellbeing_score)
            if wellbeing is not None and series[SIGNAL_WELLBEING]:
                values[SIGNAL_WELLBEING] = series[SIGNAL_WELLBEING][-1].value
            if interaction.occurred_at - interactions[0].occurred_at < timedelta(
                days=FREQUENCY_WINDOW_DAYS
            ):
                values.pop(SIGNAL_INTERACTION_FREQUENCY, None)
            rows.append(_FeatureRow(occurred_at=interaction.occurred_at, values=values))
        return rows, build_signal_series(interactions).dropped_values

    def _finite_latency(self, interaction: SeniorInteraction) -> float | None:
        try:
            latency = interaction.response_latency_minutes
        except (TypeError, ValueError):
            return None
        if latency is None or not math.isfinite(latency) or latency < 0:
            return None
        return latency

    def _finite_number(self, value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) else None

    def _select_feature_profile(
        self,
        history: list[_FeatureRow],
        observation: _FeatureRow,
        baseline: SeniorBaseline,
    ) -> tuple[list[str], list[_FeatureRow]]:
        candidates = [
            signal
            for signal in _SIGNALS
            if signal in observation.values
            and _signal_baseline_status(signal, baseline) == SignalStatus.STABLE
            and sum(signal in row.values for row in history) >= self.config.min_training_points
        ]

        while len(candidates) >= self.config.min_feature_count:
            complete = [
                row for row in history if all(signal in row.values for signal in candidates)
            ]
            if len(complete) >= self.config.min_training_points:
                varying = [
                    signal
                    for signal in candidates
                    if max(row.values[signal] for row in complete)
                    - min(row.values[signal] for row in complete)
                    > self.config.epsilon
                ]
                if len(varying) >= self.config.min_feature_count:
                    complete = [
                        row
                        for row in history
                        if all(signal in row.values for signal in varying)
                    ]
                    return varying, complete
                return [], []
            # Optional sparse signals are removed before reliable core signals.
            least_available = min(
                candidates,
                key=lambda signal: sum(signal in row.values for row in history),
            )
            candidates.remove(least_available)
        return candidates, []

    def _empty_contributions(
        self, rows: list[_FeatureRow], active_signals: list[str]
    ) -> list[SignalContribution]:
        return [
            self._contribution(
                signal=signal,
                rows=rows,
                active=signal in active_signals,
                flagged=False,
            )
            for signal in _SIGNALS
        ]

    def _explain(
        self,
        *,
        model: IsolationForest,
        observation_score: float,
        scaled_observation: numpy.ndarray,
        scaled_training: numpy.ndarray,
        active_signals: list[str],
        training_rows: list[_FeatureRow],
        all_rows: list[_FeatureRow],
        detected: bool,
        model_detected: bool,
        guarded_signals: set[str],
    ) -> list[SignalContribution]:
        increases: dict[str, float] = {}
        for index, signal in enumerate(active_signals):
            replacement = scaled_observation.copy()
            # The median transformed training value represents this senior's usual value.
            replacement[0, index] = float(numpy.median(scaled_training[:, index]))
            replaced_score = float(-model.score_samples(replacement)[0])
            increases[signal] = observation_score - replaced_score

        positive = [signal for signal, value in increases.items() if value > self.config.epsilon]
        if detected and not positive and increases:
            positive = [max(increases, key=increases.__getitem__)]
        positive = list(dict.fromkeys([*positive, *guarded_signals]))

        return [
            self._contribution(
                signal=signal,
                rows=all_rows,
                active=signal in active_signals,
                flagged=detected and signal in positive,
                methods=[
                    method
                    for method, used in (
                        ("isolation_forest", model_detected and signal in positive),
                        ("personal_deviation_guard", signal in guarded_signals),
                    )
                    if used
                ],
            )
            for signal in _SIGNALS
        ]

    def _contribution(
        self,
        *,
        signal: str,
        rows: list[_FeatureRow],
        active: bool,
        flagged: bool,
        methods: list[str] | None = None,
    ) -> SignalContribution:
        values = [row.values[signal] for row in rows[:-1] if signal in row.values]
        current = rows[-1].values.get(signal) if rows else None
        series = [
            SeriesPoint(row.occurred_at, row.values[signal])
            for row in rows
            if signal in row.values
        ][-self.config.explanation_window_points :]
        if not active or current is None or not values:
            return SignalContribution(
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
                recent_series=self._series_payload(series),
            )

        normal_mean = fmean(values)
        normal_median = median(values)
        deviation_pct = (
            (current - normal_mean) / normal_mean if normal_mean not in (0.0, 0) else None
        )
        mad = median([abs(value - normal_median) for value in values])
        robust_scale = max(
            1.4826 * mad,
            pstdev(values) if len(values) > 1 else 0.0,
            self.config.relative_scale_floor * abs(normal_median),
            self.config.epsilon,
        )
        direction = ChangeDirection.NONE
        if current > normal_median:
            direction = ChangeDirection.RISING
        elif current < normal_median:
            direction = ChangeDirection.FALLING
        return SignalContribution(
            signal=signal,
            status=DetectionStatus.OK,
            flagged=flagged,
            direction=direction,
            baseline_mean=normal_mean,
            recent_mean=current,
            deviation_pct=deviation_pct,
            standardized_shift=(current - normal_median) / robust_scale,
            methods_fired=methods or [],
            estimated_onset=rows[-1].occurred_at if flagged else None,
            recent_series=self._series_payload(series),
        )

    def _insufficient_result(
        self,
        senior_id: str,
        as_of: datetime | None,
        contributions: list[SignalContribution],
        *,
        dropped_values: int,
        feature_profile: list[str] | None = None,
        training_observations: int = 0,
    ) -> DetectionResult:
        return DetectionResult(
            senior_id=senior_id,
            kind=DetectionKind.ANOMALY,
            detected=False,
            status=DetectionStatus.INSUFFICIENT_HISTORY,
            as_of=as_of,
            confidence=Confidence.LOW,
            direction=ChangeDirection.NONE,
            contributions=contributions,
            summary="",
            metadata={
                "dropped_values": dropped_values,
                "feature_profile": feature_profile or [],
                "training_observations": training_observations,
                "minimum_training_observations": self.config.min_training_points,
            },
        )

    def _transform_matrix(self, values: numpy.ndarray, signals: list[str]) -> numpy.ndarray:
        transformed = values.copy()
        for index, signal in enumerate(signals):
            if signal == SIGNAL_RESPONSE_LATENCY:
                transformed[:, index] = numpy.log1p(transformed[:, index])
        return transformed

    def _personal_deviation_signals(
        self,
        observation: _FeatureRow,
        training_rows: list[_FeatureRow],
        active_signals: list[str],
    ) -> set[str]:
        guarded: set[str] = set()
        for signal in active_signals:
            values = [row.values[signal] for row in training_rows]
            centre = median(values)
            mad = median([abs(value - centre) for value in values])
            scale = max(
                1.4826 * mad,
                pstdev(values) if len(values) > 1 else 0.0,
                self.config.relative_scale_floor * abs(centre),
                self.config.epsilon,
            )
            if abs(observation.values[signal] - centre) / scale >= self.config.personal_deviation_z_threshold:
                guarded.add(signal)
        return guarded

    def _dominant_direction(self, flagged: list[SignalContribution]) -> ChangeDirection:
        if not flagged:
            return ChangeDirection.NONE
        return max(flagged, key=lambda item: abs(item.standardized_shift or 0.0)).direction

    def _confidence(self, flagged: list[SignalContribution]) -> Confidence:
        if len(flagged) >= 3:
            return Confidence.HIGH
        if len(flagged) == 2:
            return Confidence.MODERATE
        return Confidence.LOW

    def _summary(self, flagged: list[SignalContribution], detected: bool) -> str:
        if not detected:
            return "No unusual observation was detected relative to this senior's usual pattern."
        labels = ", ".join(_SUMMARY_LABEL[item.signal].lower() for item in flagged)
        return f"Nomi noticed an unusual observation relative to this senior's usual pattern: {labels}."

    def _series_payload(self, series: list[SeriesPoint]) -> list[dict]:
        return [
            {"occurred_at": point.occurred_at.isoformat(), "value": point.value}
            for point in series
        ]
