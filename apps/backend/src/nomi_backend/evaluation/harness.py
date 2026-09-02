from __future__ import annotations

import json
from dataclasses import asdict

from nomi_backend.detection.changes import ChangeDetector, ChangeDetectorConfig
from nomi_backend.evaluation.fixed_threshold import FixedThresholdDetector
from nomi_backend.evaluation.metrics import (
    ScenarioOutcome,
    SuiteMetrics,
    evaluate_outcomes,
)
from nomi_backend.evaluation.scenarios import SCENARIO_NAMES, generate_suite

SWEEP_WINDOWS = (4, 5, 7, 10, 14)
DEFAULT_SEED = 20260901
DEFAULT_SENIORS_PER_SCENARIO = 30
FALSE_ALERT_TARGET = 0.15
# A verdict needs a full recent window plus a reference stretch behind it;
# replaying shorter prefixes just multiplies the chances of a noise flag.
_MIN_PREFIX = 14
EVAL_BANNER = "Prototype evaluation on synthetic data — not clinical validation."


def first_flag_index(detector, interactions, *, min_prefix: int = _MIN_PREFIX) -> int | None:
    # Require persistence: a sustained change is still there one observation
    # later, a noise blip is not. Flag at the first prefix whose detection is
    # confirmed by the immediately preceding prefix also detecting.
    previous = False
    for size in range(min_prefix, len(interactions) + 1):
        current = detector.detect("synthetic", interactions[:size]).detected
        if current and previous:
            return size
        previous = current
    return None


def _outcomes_for(detector, suites: dict) -> list[ScenarioOutcome]:
    outcomes: list[ScenarioOutcome] = []
    for name, results in suites.items():
        for result in results:
            index = first_flag_index(detector, result.interactions)
            outcomes.append(
                ScenarioOutcome(
                    scenario=name,
                    ground_truth=result.ground_truth,
                    detected=index is not None,
                    detected_at_index=index,
                )
            )
    return outcomes


def _per_scenario(outcomes: list[ScenarioOutcome]) -> dict:
    summary: dict = {}
    for name in SCENARIO_NAMES:
        rows = [o for o in outcomes if o.scenario == name]
        flagged = sum(1 for o in rows if o.detected)
        summary[name] = {
            "n": len(rows),
            "flagged": flagged,
            "labelled_change": rows[0].ground_truth is not None if rows else False,
        }
    return summary


def run_evaluation(
    seed: int = DEFAULT_SEED,
    seniors_per_scenario: int = DEFAULT_SENIORS_PER_SCENARIO,
    windows: tuple[int, ...] = SWEEP_WINDOWS,
) -> dict:
    suites = {
        name: generate_suite(name, seed=seed, count=seniors_per_scenario)
        for name in SCENARIO_NAMES
    }

    change_detector = ChangeDetector()
    fixed_detector = FixedThresholdDetector()

    cd_outcomes = _outcomes_for(change_detector, suites)
    ft_outcomes = _outcomes_for(fixed_detector, suites)

    sweep = []
    for window in windows:
        detector = ChangeDetector(ChangeDetectorConfig(recent_window_points=window))
        metrics = evaluate_outcomes(_outcomes_for(detector, suites))
        sweep.append({"window": window, **metrics.to_dict()})

    qualifying = [
        row
        for row in sweep
        if row["false_alert_rate"] <= FALSE_ALERT_TARGET
    ]
    if qualifying:
        selected = min(
            qualifying,
            key=lambda row: (
                row["detection_delay_median"]
                if row["detection_delay_median"] is not None
                else float("inf")
            ),
        )["window"]
    else:
        selected = 7

    return {
        "banner": EVAL_BANNER,
        "seed": seed,
        "seniors_per_scenario": seniors_per_scenario,
        "config": asdict(ChangeDetectorConfig()),
        "detectors": {
            "change_detector": evaluate_outcomes(cd_outcomes).to_dict(),
            "fixed_threshold": evaluate_outcomes(ft_outcomes).to_dict(),
        },
        "per_scenario": _per_scenario(cd_outcomes),
        "window_sweep": sweep,
        "selected_window": selected,
    }


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_markdown(report: dict) -> str:
    lines = [
        "# P2 Change Detection — Evaluation Results",
        "",
        f"> {report['banner']}",
        "",
        f"- Seed: `{report['seed']}`",
        f"- Seniors per scenario: {report['seniors_per_scenario']}",
        f"- Selected rolling window: **{report['selected_window']}**",
        "",
        "## Detector comparison",
        "",
        "| detector | recall | precision | false_alert_rate | delay_median | delay_p90 |",
        "|---|---|---|---|---|---|",
    ]
    for key in ("change_detector", "fixed_threshold"):
        m = report["detectors"][key]
        lines.append(
            f"| {key} | {_fmt(m['recall'])} | {_fmt(m['precision'])} | "
            f"{_fmt(m['false_alert_rate'])} | {_fmt(m['detection_delay_median'])} | "
            f"{_fmt(m['detection_delay_p90'])} |"
        )
    lines += [
        "",
        "## Rolling-window sweep (change detector)",
        "",
        "| window | recall | precision | false_alert_rate | delay_median | delay_p90 |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["window_sweep"]:
        lines.append(
            f"| {row['window']} | {_fmt(row['recall'])} | {_fmt(row['precision'])} | "
            f"{_fmt(row['false_alert_rate'])} | {_fmt(row['detection_delay_median'])} | "
            f"{_fmt(row['detection_delay_p90'])} |"
        )
    lines += ["", "## Per-scenario (change detector)", "", "| scenario | n | flagged | labelled change |", "|---|---|---|---|"]
    for name, row in report["per_scenario"].items():
        lines.append(f"| {name} | {row['n']} | {row['flagged']} | {row['labelled_change']} |")
    lines.append("")
    return "\n".join(lines)
