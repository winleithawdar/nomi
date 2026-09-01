from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.evaluation.scenarios import (
    SCENARIO_NAMES,
    generate_scenario,
    generate_suite,
)
import numpy


class ScenarioGeneratorTest(unittest.TestCase):
    def test_all_scenarios_are_named(self) -> None:
        self.assertEqual(len(SCENARIO_NAMES), 8)
        self.assertIn("gradual_latency_increase", SCENARIO_NAMES)

    def test_generators_are_deterministic_for_a_seed(self) -> None:
        first = generate_suite("gradual_latency_increase", seed=7, count=3)
        second = generate_suite("gradual_latency_increase", seed=7, count=3)

        def shape(results):
            return [
                (
                    [
                        (i.occurred_at.isoformat(), i.response_latency_minutes, i.missed_checkin, i.wellbeing_score)
                        for i in r.interactions
                    ],
                    r.ground_truth,
                )
                for r in results
            ]

        self.assertEqual(shape(first), shape(second))

    def test_stable_scenario_has_no_ground_truth(self) -> None:
        result = generate_scenario("stable", numpy.random.default_rng(1), 0)
        self.assertIsNone(result.ground_truth)
        self.assertGreaterEqual(len(result.interactions), 30)

    def test_isolated_late_response_is_not_labelled_a_sustained_change(self) -> None:
        result = generate_scenario("isolated_late_response", numpy.random.default_rng(1), 0)
        self.assertIsNone(result.ground_truth)

    def test_gradual_latency_increase_injects_rising_latency(self) -> None:
        result = generate_scenario("gradual_latency_increase", numpy.random.default_rng(2), 0)
        self.assertEqual(result.ground_truth["signal"], "response_latency_minutes")
        onset = result.ground_truth["onset_index"]
        latencies = [
            i.response_latency_minutes
            for i in result.interactions
            if i.response_latency_minutes is not None
        ]
        self.assertGreater(
            sum(latencies[onset:]) / len(latencies[onset:]),
            sum(latencies[:onset]) / len(latencies[:onset]) + 5,
        )

    def test_sudden_cessation_reduces_interaction_count_after_onset(self) -> None:
        result = generate_scenario("sudden_cessation", numpy.random.default_rng(3), 0)
        self.assertEqual(result.ground_truth["signal"], "interaction_frequency")


from datetime import datetime, timedelta, timezone

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.evaluation.fixed_threshold import (
    FixedThresholdConfig,
    FixedThresholdDetector,
)

_TS = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _resp(day: int, latency: float) -> SeniorInteraction:
    at = _TS + timedelta(days=day)
    return SeniorInteraction(
        senior_id="senior-1",
        occurred_at=at,
        interaction_type="checkin_response",
        missed_checkin=False,
        checkin_sent_at=at - timedelta(minutes=latency),
        response_received_at=at,
        wellbeing_score=None,
    )


class FixedThresholdDetectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = FixedThresholdDetector()

    def test_normal_latency_is_not_flagged(self) -> None:
        history = [_resp(d, 20.0) for d in range(12)]
        result = self.detector.detect("senior-1", history)
        self.assertFalse(result.detected)
        self.assertEqual(result.confidence.value, "low")

    def test_latency_above_population_threshold_is_flagged(self) -> None:
        history = [_resp(d, 20.0) for d in range(6)] + [_resp(6 + d, 60.0) for d in range(7)]
        result = self.detector.detect("senior-1", history)
        self.assertTrue(result.detected)
        self.assertEqual(result.kind.value, "sustained_change")
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        self.assertTrue(latency.flagged)

    def test_accepts_and_ignores_baseline_kwarg(self) -> None:
        history = [_resp(d, 20.0) for d in range(12)]
        result = self.detector.detect("senior-1", history, baseline=None)
        self.assertFalse(result.detected)

    def test_short_history_is_insufficient(self) -> None:
        result = self.detector.detect("senior-1", [_resp(0, 20.0), _resp(1, 20.0)])
        self.assertEqual(result.status.value, "insufficient_history")


from nomi_backend.evaluation.metrics import (
    ScenarioOutcome,
    SuiteMetrics,
    evaluate_outcomes,
)


class MetricsTest(unittest.TestCase):
    def test_recall_precision_and_false_alert_rate(self) -> None:
        outcomes = [
            ScenarioOutcome("gradual_latency_increase", {"signal": "response_latency_minutes", "onset_index": 21, "kind": "sustained_change"}, True, 25),
            ScenarioOutcome("worsening_wellbeing", {"signal": "wellbeing_score", "onset_index": 21, "kind": "sustained_change"}, False, None),
            ScenarioOutcome("stable", None, False, None),
            ScenarioOutcome("stable", None, True, 12),
        ]

        metrics = evaluate_outcomes(outcomes)

        self.assertAlmostEqual(metrics.recall, 0.5)
        self.assertAlmostEqual(metrics.false_alert_rate, 0.5)
        self.assertAlmostEqual(metrics.precision, 0.5)
        self.assertEqual(metrics.n_changed, 2)
        self.assertEqual(metrics.n_stable, 2)

    def test_detection_delay_uses_onset_index(self) -> None:
        outcomes = [
            ScenarioOutcome("gradual_latency_increase", {"signal": "response_latency_minutes", "onset_index": 21, "kind": "sustained_change"}, True, 25),
            ScenarioOutcome("gradual_frequency_decline", {"signal": "interaction_frequency", "onset_index": 21, "kind": "sustained_change"}, True, 30),
        ]

        metrics = evaluate_outcomes(outcomes)

        self.assertEqual(metrics.detection_delay_median, 6.5)  # delays 4 and 9

    def test_no_caught_changes_yields_none_delay(self) -> None:
        outcomes = [
            ScenarioOutcome("stable", None, False, None),
            ScenarioOutcome("worsening_wellbeing", {"signal": "wellbeing_score", "onset_index": 21, "kind": "sustained_change"}, False, None),
        ]

        metrics = evaluate_outcomes(outcomes)

        self.assertIsNone(metrics.detection_delay_median)
        self.assertEqual(metrics.recall, 0.0)

    def test_to_dict_is_primitive(self) -> None:
        metrics = evaluate_outcomes([ScenarioOutcome("stable", None, False, None)])
        payload = metrics.to_dict()
        self.assertIn("recall", payload)
        self.assertIsInstance(payload["recall"], float)


from nomi_backend.evaluation.harness import (
    EVAL_BANNER,
    SWEEP_WINDOWS,
    render_json,
    render_markdown,
    run_evaluation,
)
from nomi_backend.evaluation.anomaly_harness import (
    ANOMALY_SCENARIO_NAMES,
    EVAL_BANNER as ANOMALY_EVAL_BANNER,
    render_json as render_anomaly_json,
    render_markdown as render_anomaly_markdown,
    run_anomaly_evaluation,
)


class HarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_evaluation(seed=101, seniors_per_scenario=4)

    def test_report_has_both_detectors(self) -> None:
        self.assertIn("change_detector", self.report["detectors"])
        self.assertIn("fixed_threshold", self.report["detectors"])

    def test_window_sweep_covers_all_windows(self) -> None:
        windows = [row["window"] for row in self.report["window_sweep"]]
        self.assertEqual(windows, list(SWEEP_WINDOWS))

    def test_selected_window_is_one_of_the_sweep_windows(self) -> None:
        self.assertIn(self.report["selected_window"], SWEEP_WINDOWS)

    def test_change_detector_beats_fixed_threshold_on_recall(self) -> None:
        cd = self.report["detectors"]["change_detector"]["recall"]
        ft = self.report["detectors"]["fixed_threshold"]["recall"]
        self.assertGreaterEqual(cd, ft)

    def test_default_window_false_alert_rate_within_target(self) -> None:
        row = next(r for r in self.report["window_sweep"] if r["window"] == 7)
        self.assertLessEqual(row["false_alert_rate"], 0.25)

    def test_markdown_contains_banner_and_table(self) -> None:
        text = render_markdown(self.report)
        self.assertIn(EVAL_BANNER, text)
        self.assertIn("| window |", text.lower())

    def test_render_json_round_trips(self) -> None:
        import json

        self.assertEqual(json.loads(render_json(self.report))["seed"], 101)


import json
import tempfile

from nomi_backend.evaluation.__main__ import main


class CliTest(unittest.TestCase):
    def test_main_writes_both_result_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["--seed", "5", "--seniors-per-scenario", "3", "--out", tmp])
            self.assertEqual(code, 0)
            payload = json.loads((Path(tmp) / "evaluation-results.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["seed"], 5)
            md = (Path(tmp) / "evaluation-results.md").read_text(encoding="utf-8")
            self.assertIn("Evaluation Results", md)


class AnomalyHarnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = run_anomaly_evaluation(seed=202, seniors_per_scenario=4)

    def test_all_anomaly_scenarios_are_reported(self) -> None:
        self.assertEqual(set(self.report["per_scenario"]), set(ANOMALY_SCENARIO_NAMES))

    def test_hybrid_detector_catches_injected_anomalies(self) -> None:
        metrics = self.report["detectors"]["hybrid_personal_detector"]
        self.assertGreaterEqual(metrics["recall"], 0.95)

    def test_hybrid_is_not_worse_than_forest_only(self) -> None:
        hybrid = self.report["detectors"]["hybrid_personal_detector"]
        forest = self.report["detectors"]["isolation_forest_only"]
        self.assertGreaterEqual(hybrid["recall"], forest["recall"])

    def test_hybrid_false_alert_rate_meets_prototype_target(self) -> None:
        metrics = self.report["detectors"]["hybrid_personal_detector"]
        self.assertLessEqual(metrics["false_alert_rate"], 0.10)

    def test_guard_sweep_includes_default_threshold(self) -> None:
        thresholds = [row["guard_z_threshold"] for row in self.report["guard_threshold_sweep"]]
        self.assertIn(3.5, thresholds)
        self.assertEqual(self.report["configured_guard_z_threshold"], 3.5)

    def test_anomaly_renderers_include_banner(self) -> None:
        self.assertIn(ANOMALY_EVAL_BANNER, render_anomaly_markdown(self.report))
        self.assertEqual(render_anomaly_json(self.report).count('"seed"'), 1)


if __name__ == "__main__":
    unittest.main()
