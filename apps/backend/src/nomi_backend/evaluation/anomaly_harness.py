from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import numpy

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.detection.anomalies import AnomalyDetector, AnomalyDetectorConfig
from nomi_backend.evaluation.metrics import ScenarioOutcome, evaluate_outcomes

ANOMALY_SCENARIO_NAMES = (
    "stable",
    "late_response_spike",
    "missed_checkin_spike",
    "wellbeing_drop",
    "combined_anomaly",
    "late_response_without_wellbeing",
)
DEFAULT_SEED = 20260902
DEFAULT_SENIORS_PER_SCENARIO = 30
GUARD_Z_SWEEP = (2.5, 3.0, 3.5, 4.0, 5.0)
EVAL_BANNER = "Prototype evaluation on synthetic data — not clinical validation."
_START = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
_HISTORY_POINTS = 30


def _interaction(
    index: int,
    latency: float | None,
    *,
    missed_checkin: bool = False,
    wellbeing: float | None = None,
) -> SeniorInteraction:
    occurred_at = _START + timedelta(days=index)
    sent_at = responded_at = None
    if latency is not None:
        sent_at = occurred_at - timedelta(minutes=float(latency))
        responded_at = occurred_at
    return SeniorInteraction(
        senior_id="synthetic",
        occurred_at=occurred_at,
        interaction_type="checkin_missed" if missed_checkin else "checkin_response",
        missed_checkin=missed_checkin,
        checkin_sent_at=sent_at,
        response_received_at=responded_at,
        wellbeing_score=wellbeing,
    )


def _scenario(
    name: str, rng: numpy.random.Generator
) -> tuple[list[SeniorInteraction], dict | None]:
    centre = float(rng.uniform(15.0, 45.0))
    spread = float(rng.uniform(1.5, 4.0))
    wellbeing = float(rng.choice([3.0, 4.0, 5.0]))
    include_wellbeing = name != "late_response_without_wellbeing"
    interactions = [
        _interaction(
            index,
            max(1.0, float(rng.normal(centre, spread))),
            wellbeing=wellbeing if include_wellbeing else None,
        )
        for index in range(_HISTORY_POINTS)
    ]

    if name == "stable":
        interactions.append(
            _interaction(
                _HISTORY_POINTS,
                max(1.0, float(rng.normal(centre, spread))),
                wellbeing=wellbeing if include_wellbeing else None,
            )
        )
        return interactions, None
    if name in {"late_response_spike", "late_response_without_wellbeing"}:
        interactions.append(
            _interaction(
                _HISTORY_POINTS,
                centre + max(30.0, 8.0 * spread),
                wellbeing=wellbeing if include_wellbeing else None,
            )
        )
        return interactions, {
            "signal": "response_latency_minutes",
            "onset_index": _HISTORY_POINTS,
        }
    if name == "missed_checkin_spike":
        interactions.append(
            _interaction(_HISTORY_POINTS, None, missed_checkin=True, wellbeing=wellbeing)
        )
        return interactions, {
            "signal": "missed_checkin_rate",
            "onset_index": _HISTORY_POINTS,
        }
    if name == "wellbeing_drop":
        interactions.append(_interaction(_HISTORY_POINTS, centre, wellbeing=1.0))
        return interactions, {
            "signal": "wellbeing_score",
            "onset_index": _HISTORY_POINTS,
        }
    if name == "combined_anomaly":
        interactions.append(
            _interaction(
                _HISTORY_POINTS,
                centre + max(30.0, 8.0 * spread),
                wellbeing=1.0,
            )
        )
        return interactions, {
            "signal": "response_latency_minutes",
            "onset_index": _HISTORY_POINTS,
        }
    raise ValueError(f"unknown P1 anomaly scenario: {name}")


def _suites(
    seed: int, count: int
) -> dict[str, list[tuple[list[SeniorInteraction], dict | None]]]:
    rng = numpy.random.default_rng(seed)
    return {
        name: [_scenario(name, rng) for _ in range(count)]
        for name in ANOMALY_SCENARIO_NAMES
    }


def _outcomes(detector: AnomalyDetector, suites: dict) -> list[ScenarioOutcome]:
    outcomes: list[ScenarioOutcome] = []
    for name, scenarios in suites.items():
        for interactions, ground_truth in scenarios:
            result = detector.detect("synthetic", interactions)
            outcomes.append(
                ScenarioOutcome(
                    scenario=name,
                    ground_truth=ground_truth,
                    detected=result.detected,
                    detected_at_index=len(interactions) - 1 if result.detected else None,
                )
            )
    return outcomes


def _per_scenario(outcomes: list[ScenarioOutcome]) -> dict:
    return {
        name: {
            "n": len(rows := [item for item in outcomes if item.scenario == name]),
            "flagged": sum(item.detected for item in rows),
            "labelled_anomaly": rows[0].ground_truth is not None if rows else False,
        }
        for name in ANOMALY_SCENARIO_NAMES
    }


def run_anomaly_evaluation(
    seed: int = DEFAULT_SEED,
    seniors_per_scenario: int = DEFAULT_SENIORS_PER_SCENARIO,
    guard_z_values: tuple[float, ...] = GUARD_Z_SWEEP,
) -> dict:
    suites = _suites(seed, seniors_per_scenario)
    hybrid = AnomalyDetector()
    forest_only = AnomalyDetector(
        AnomalyDetectorConfig(
            personal_deviation_z_threshold=float("inf"),
            require_forest_personal_evidence=False,
        )
    )
    hybrid_outcomes = _outcomes(hybrid, suites)
    forest_outcomes = _outcomes(forest_only, suites)

    sweep = []
    for guard_z in guard_z_values:
        detector = AnomalyDetector(
            AnomalyDetectorConfig(personal_deviation_z_threshold=guard_z)
        )
        metrics = evaluate_outcomes(_outcomes(detector, suites))
        sweep.append({"guard_z_threshold": guard_z, **metrics.to_dict()})

    return {
        "banner": EVAL_BANNER,
        "seed": seed,
        "seniors_per_scenario": seniors_per_scenario,
        "config": asdict(AnomalyDetectorConfig()),
        "detectors": {
            "hybrid_personal_detector": evaluate_outcomes(hybrid_outcomes).to_dict(),
            "isolation_forest_only": evaluate_outcomes(forest_outcomes).to_dict(),
        },
        "per_scenario": _per_scenario(hybrid_outcomes),
        "guard_threshold_sweep": sweep,
        "configured_guard_z_threshold": (
            AnomalyDetectorConfig().personal_deviation_z_threshold
        ),
    }


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def render_markdown(report: dict) -> str:
    lines = [
        "# P1 Anomaly Detection — Evaluation Results",
        "",
        f"> {report['banner']}",
        "",
        f"- Seed: `{report['seed']}`",
        f"- Seniors per scenario: {report['seniors_per_scenario']}",
        f"- Configured guard threshold: **{report['configured_guard_z_threshold']}**",
        "",
        "## Detector comparison",
        "",
        "| detector | recall | precision | false_alert_rate | delay_median | delay_p90 |",
        "|---|---|---|---|---|---|",
    ]
    for name, metrics in report["detectors"].items():
        lines.append(
            f"| {name} | {_fmt(metrics['recall'])} | {_fmt(metrics['precision'])} | "
            f"{_fmt(metrics['false_alert_rate'])} | {_fmt(metrics['detection_delay_median'])} | "
            f"{_fmt(metrics['detection_delay_p90'])} |"
        )
    lines += [
        "",
        "## Personal-deviation guard sweep",
        "",
        "| guard z threshold | recall | precision | false_alert_rate |",
        "|---|---|---|---|",
    ]
    for row in report["guard_threshold_sweep"]:
        lines.append(
            f"| {row['guard_z_threshold']} | {_fmt(row['recall'])} | {_fmt(row['precision'])} | "
            f"{_fmt(row['false_alert_rate'])} |"
        )
    lines += [
        "",
        "## Per-scenario (hybrid detector)",
        "",
        "| scenario | n | flagged | labelled anomaly |",
        "|---|---|---|---|",
    ]
    for name, row in report["per_scenario"].items():
        lines.append(f"| {name} | {row['n']} | {row['flagged']} | {row['labelled_anomaly']} |")
    lines.append("")
    return "\n".join(lines)


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)
