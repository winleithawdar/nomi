from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario: str
    ground_truth: dict | None
    detected: bool
    detected_at_index: int | None


@dataclass(frozen=True)
class SuiteMetrics:
    recall: float
    precision: float
    false_alert_rate: float
    detection_delay_median: float | None
    detection_delay_p90: float | None
    n_changed: int
    n_stable: int

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_outcomes(outcomes: list[ScenarioOutcome]) -> SuiteMetrics:
    changed = [o for o in outcomes if o.ground_truth is not None]
    stable = [o for o in outcomes if o.ground_truth is None]

    true_positive = [o for o in changed if o.detected]
    false_positive = [o for o in stable if o.detected]

    recall = len(true_positive) / len(changed) if changed else 0.0
    false_alert_rate = len(false_positive) / len(stable) if stable else 0.0
    positives = len(true_positive) + len(false_positive)
    precision = len(true_positive) / positives if positives else 0.0

    delays = [
        o.detected_at_index - o.ground_truth["onset_index"]
        for o in true_positive
        if o.detected_at_index is not None
    ]
    if delays:
        median = float(numpy.percentile(delays, 50, method="linear"))
        p90 = float(numpy.percentile(delays, 90, method="linear"))
    else:
        median = None
        p90 = None

    return SuiteMetrics(
        recall=recall,
        precision=precision,
        false_alert_rate=false_alert_rate,
        detection_delay_median=median,
        detection_delay_p90=p90,
        n_changed=len(changed),
        n_stable=len(stable),
    )
