from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean, median, pstdev

import numpy

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

_RATE_STD_FLOOR = 0.15

_SUMMARY_LABEL = {
    SIGNAL_RESPONSE_LATENCY: "Response latency",
    SIGNAL_MISSED_CHECKIN_RATE: "Missed check-ins",
    SIGNAL_INTERACTION_FREQUENCY: "Interaction frequency",
    SIGNAL_WELLBEING: "Self-reported wellbeing",
}


def _signal_baseline_status(signal: str, baseline: SeniorBaseline) -> SignalStatus:
    if signal == SIGNAL_MISSED_CHECKIN_RATE:
        return baseline.missed_checkin_rate.status
    return getattr(baseline, _NUMERIC_BASELINE_ATTR[signal]).status


@dataclass(frozen=True)
class ChangeDetectorConfig:
    reference_min_points: int = 5
    recent_window_points: int = 7
    recent_min_points: int = 4
    min_sustained_points: int = 3
    shift_z_threshold: float = 1.5
    min_rel_std: float = 0.12
    cusum_k: float = 0.5
    cusum_h: float = 5.0
    cusum_clamp: float = 4.0
    trend_slope_threshold: float = 0.4
    epsilon: float = 1e-6


class ChangeDetector:
    def __init__(self, config: ChangeDetectorConfig | None = None) -> None:
        self.config = config or ChangeDetectorConfig()
        self._baseline_calculator = BaselineCalculator()

    def detect(
        self,
        senior_id: str,
        interactions: list[SeniorInteraction],
        baseline: SeniorBaseline | None = None,
    ) -> DetectionResult:
        own = sorted(
            (item for item in interactions if item.senior_id == senior_id),
            key=lambda item: item.occurred_at,
        )
        if baseline is None:
            baseline = self._baseline_calculator.calculate(senior_id, own)

        bundle = build_signal_series(
            own, missed_rate_window=self.config.recent_window_points
        )
        series_map = bundle.as_map()
        as_of = own[-1].occurred_at if own else None

        contributions = [
            self._evaluate_signal(signal, series_map[signal], baseline)
            for signal in _SIGNALS
        ]

        evaluated = [c for c in contributions if c.status == DetectionStatus.OK]
        if not evaluated:
            return DetectionResult(
                senior_id=senior_id,
                kind=DetectionKind.SUSTAINED_CHANGE,
                detected=False,
                status=DetectionStatus.INSUFFICIENT_HISTORY,
                as_of=as_of,
                confidence=Confidence.LOW,
                direction=ChangeDirection.NONE,
                contributions=contributions,
                summary="",
                metadata={
                    "dropped_values": bundle.dropped_values,
                    "window": self.config.recent_window_points,
                },
            )

        flagged = [c for c in contributions if c.flagged]
        detected = bool(flagged)
        direction = ChangeDirection.NONE
        if flagged:
            lead = max(flagged, key=lambda c: abs(c.standardized_shift or 0.0))
            direction = lead.direction

        return DetectionResult(
            senior_id=senior_id,
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=detected,
            status=DetectionStatus.OK,
            as_of=as_of,
            confidence=self._confidence(flagged),
            direction=direction,
            contributions=contributions,
            summary=self._summary(flagged),
            metadata={
                "dropped_values": bundle.dropped_values,
                "window": self.config.recent_window_points,
            },
        )

    def _evaluate_signal(
        self,
        signal: str,
        series: list[SeriesPoint],
        baseline: SeniorBaseline,
    ) -> SignalContribution:
        config = self.config

        # The interaction_frequency series opens with a deterministic fill-up
        # ramp: the trailing FREQUENCY_WINDOW_DAYS counter climbs from 1 to its
        # plateau as the window fills, regardless of the senior's actual rate.
        # Left in, those points drag the reference mean down and read as a
        # sustained rise on every stable senior. Drop them before splitting.
        if signal == SIGNAL_INTERACTION_FREQUENCY and series:
            origin = series[0].occurred_at
            warmup = sum(
                1
                for point in series
                if point.occurred_at - origin < timedelta(days=FREQUENCY_WINDOW_DAYS)
            )
            series = series[warmup:]

        recent_points = series[-config.recent_window_points :]
        insufficient = SignalContribution(
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
            recent_series=_series_payload(recent_points),
        )

        # Gate 1: the senior's baseline for this signal must be established.
        if _signal_baseline_status(signal, baseline) != SignalStatus.STABLE:
            return insufficient

        values = [point.value for point in series]

        # Gate 2: need room for a distinct "before" and "after" stretch.
        if len(values) < config.reference_min_points + config.recent_min_points:
            return insufficient
        if len(recent_points) < config.recent_min_points:
            return insufficient

        ref_mean, ref_std = self._reference_normal(signal, values)
        recent = [point.value for point in recent_points]
        recent_mean = fmean(recent)
        standardized_shift = (recent_mean - ref_mean) / ref_std
        deviation_pct = (
            (recent_mean - ref_mean) / ref_mean if ref_mean not in (0, 0.0) else None
        )

        methods: list[str] = []
        if self._level_shift(recent, ref_mean, ref_std):
            methods.append("level_shift")

        times = [point.occurred_at for point in series]
        cusum_fired, cusum_direction, cusum_onset = self._cusum(
            values, times, ref_mean, ref_std
        )
        estimated_onset = None
        if cusum_fired:
            methods.append("cusum")
            estimated_onset = cusum_onset

        trend_fired, trend_direction = self._trend(recent, ref_std)
        if trend_fired:
            methods.append("trend")

        direction = ChangeDirection.NONE
        if methods:
            if recent_mean > ref_mean:
                direction = ChangeDirection.RISING
            elif recent_mean < ref_mean:
                direction = ChangeDirection.FALLING
            elif cusum_fired:
                direction = cusum_direction
            elif trend_fired:
                direction = trend_direction

        return SignalContribution(
            signal=signal,
            status=DetectionStatus.OK,
            flagged=bool(methods),
            direction=direction,
            baseline_mean=ref_mean,
            recent_mean=recent_mean,
            deviation_pct=deviation_pct,
            standardized_shift=standardized_shift,
            methods_fired=methods,
            estimated_onset=estimated_onset,
            recent_series=_series_payload(recent_points),
        )

    def _reference_normal(
        self,
        signal: str,
        values: list[float],
    ) -> tuple[float, float]:
        config = self.config
        split = max(
            len(values) - config.recent_window_points, config.reference_min_points
        )
        pre = values[:split]
        ref_mean = fmean(pre)
        ref_std = pstdev(pre) if len(pre) > 1 else 0.0
        # A short, near-constant window gives an unrealistically tight std, which
        # makes ordinary jitter look significant. Floor it relative to the level.
        ref_std = max(ref_std, config.min_rel_std * abs(ref_mean))
        if signal == SIGNAL_MISSED_CHECKIN_RATE:
            ref_std = max(ref_std, _RATE_STD_FLOOR)
        return ref_mean, max(ref_std, config.epsilon)

    def _level_shift(
        self,
        recent: list[float],
        ref_mean: float,
        ref_std: float,
    ) -> bool:
        # Trigger on the median, not the mean: one isolated late reply moves the
        # window mean enough to cross the threshold but leaves the median where
        # the senior's normal is. A genuine step shifts both.
        z = (median(recent) - ref_mean) / ref_std
        if abs(z) < self.config.shift_z_threshold:
            return False
        # "Sustained" = at least min_sustained_points of the window sit a full
        # sigma clear of the reference on one side, after discarding the single
        # most extreme point (so a lone spike plus noise cannot clear the bar).
        centre = fmean(recent)
        outlier = max(range(len(recent)), key=lambda i: abs(recent[i] - centre))
        trimmed = [value for index, value in enumerate(recent) if index != outlier]
        margin = ref_std
        above = sum(1 for value in trimmed if value - ref_mean >= margin)
        below = sum(1 for value in trimmed if ref_mean - value >= margin)
        return max(above, below) >= self.config.min_sustained_points

    def _cusum(
        self,
        values: list[float],
        times: list[datetime],
        ref_mean: float,
        ref_std: float,
    ) -> tuple[bool, ChangeDirection, datetime | None]:
        k = self.config.cusum_k
        h = self.config.cusum_h
        clamp = self.config.cusum_clamp
        need = self.config.min_sustained_points
        high = 0.0
        low = 0.0
        high_start = 0
        low_start = 0
        last = len(values) - 1
        for index, value in enumerate(values):
            residual = (value - ref_mean) / ref_std
            residual = max(-clamp, min(clamp, residual))
            if high <= 0.0:
                high_start = index
            if low <= 0.0:
                low_start = index
            high = max(0.0, high + residual - k)
            low = max(0.0, low - residual - k)
        high_run = last - high_start + 1
        low_run = last - low_start + 1
        if high > h and high >= low and high_run >= need:
            return True, ChangeDirection.RISING, times[high_start]
        if low > h and low_run >= need:
            return True, ChangeDirection.FALLING, times[low_start]
        return False, ChangeDirection.NONE, None

    def _trend(
        self,
        recent: list[float],
        ref_std: float,
    ) -> tuple[bool, ChangeDirection]:
        n = len(recent)
        if n < 3 or max(recent) == min(recent):
            return False, ChangeDirection.NONE
        fired, direction = self._trend_fit(recent, ref_std)
        if not fired:
            return False, ChangeDirection.NONE
        # A single leverage point — one isolated late reply — can dominate a
        # least-squares slope and the sign statistic. Require the trend to
        # survive dropping the point furthest from the window mean: a genuine
        # ramp barely moves, a lone spike collapses to noise.
        centre = fmean(recent)
        outlier = max(range(n), key=lambda i: abs(recent[i] - centre))
        reduced = [value for index, value in enumerate(recent) if index != outlier]
        fired_reduced, direction_reduced = self._trend_fit(reduced, ref_std)
        if not fired_reduced or direction_reduced != direction:
            return False, ChangeDirection.NONE
        return True, direction

    def _trend_fit(
        self,
        recent: list[float],
        ref_std: float,
    ) -> tuple[bool, ChangeDirection]:
        n = len(recent)
        if n < 3 or max(recent) == min(recent):
            return False, ChangeDirection.NONE
        x = numpy.arange(n, dtype=float)
        slope = float(numpy.polyfit(x, numpy.asarray(recent, dtype=float), 1)[0])
        normalized = slope / ref_std
        sign_sum = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                sign_sum += (recent[j] > recent[i]) - (recent[j] < recent[i])
        if abs(normalized) < self.config.trend_slope_threshold:
            return False, ChangeDirection.NONE
        if sign_sum == 0 or (sign_sum > 0) != (slope > 0):
            return False, ChangeDirection.NONE
        return True, (
            ChangeDirection.RISING if slope > 0 else ChangeDirection.FALLING
        )

    def _confidence(self, flagged: list[SignalContribution]) -> Confidence:
        if not flagged:
            return Confidence.LOW
        multi_method = any(len(c.methods_fired) >= 2 for c in flagged)
        if len(flagged) >= 2 and multi_method:
            return Confidence.HIGH
        if len(flagged) >= 2 or multi_method:
            return Confidence.MODERATE
        return Confidence.LOW

    def _summary(self, flagged: list[SignalContribution]) -> str:
        sentences = []
        for contribution in flagged:
            label = _SUMMARY_LABEL[contribution.signal]
            side = "above" if contribution.direction == ChangeDirection.RISING else "below"
            if contribution.deviation_pct is not None:
                magnitude = f"about {abs(contribution.deviation_pct) * 100:.0f}% {side}"
            else:
                magnitude = f"{side}"
            since = ""
            if contribution.estimated_onset is not None:
                since = f", since around {contribution.estimated_onset.date().isoformat()}"
            sentences.append(f"{label} is running {magnitude} the usual baseline{since}.")
        return " ".join(sentences)


def _series_payload(points: list[SeriesPoint]) -> list[dict]:
    return [
        {"occurred_at": point.occurred_at.isoformat(), "value": point.value}
        for point in points
    ]
