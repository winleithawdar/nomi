from __future__ import annotations

import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.detection.features import (
    SIGNAL_INTERACTION_FREQUENCY,
    SIGNAL_MISSED_CHECKIN_RATE,
    SIGNAL_RESPONSE_LATENCY,
    SIGNAL_WELLBEING,
    build_signal_series,
)

START = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _interaction(
    *,
    occurred_at: datetime,
    latency_minutes: float | None = None,
    missed_checkin: bool = False,
    wellbeing_score: float | None = None,
    source: str = "nomi",
) -> SeniorInteraction:
    sent_at = responded_at = None
    if latency_minutes is not None:
        sent_at = occurred_at - timedelta(minutes=latency_minutes)
        responded_at = occurred_at
    return SeniorInteraction(
        senior_id="senior-1",
        occurred_at=occurred_at,
        interaction_type="checkin_missed" if missed_checkin else "checkin_response",
        missed_checkin=missed_checkin,
        checkin_sent_at=sent_at,
        response_received_at=responded_at,
        wellbeing_score=wellbeing_score,
        source=source,
    )


class BuildSignalSeriesTest(unittest.TestCase):
    def test_latency_series_only_includes_points_with_both_timestamps(self) -> None:
        interactions = [
            _interaction(occurred_at=START, latency_minutes=20),
            _interaction(occurred_at=START + timedelta(days=1), missed_checkin=True),
            _interaction(occurred_at=START + timedelta(days=2), latency_minutes=24),
        ]

        bundle = build_signal_series(interactions)

        latency = bundle.as_map()[SIGNAL_RESPONSE_LATENCY]
        self.assertEqual([point.value for point in latency], [20.0, 24.0])
        self.assertEqual(latency[0].occurred_at, START)

    def test_missed_rate_series_is_trailing_mean_over_window(self) -> None:
        interactions = [
            _interaction(
                occurred_at=START + timedelta(days=index),
                missed_checkin=index in (2, 3),
                latency_minutes=None if index in (2, 3) else 18,
            )
            for index in range(4)
        ]

        bundle = build_signal_series(interactions, missed_rate_window=3)

        rates = [point.value for point in bundle.as_map()[SIGNAL_MISSED_CHECKIN_RATE]]
        # windows: [0], [0,0], [0,0,1], [0,1,1]
        self.assertEqual(rates, [0.0, 0.0, 1 / 3, 2 / 3])

    def test_interaction_frequency_is_trailing_day_count(self) -> None:
        interactions = [
            _interaction(occurred_at=START + timedelta(days=day), latency_minutes=15)
            for day in (0, 1, 2, 9)
        ]

        bundle = build_signal_series(interactions, frequency_window_days=7)

        counts = [point.value for point in bundle.as_map()[SIGNAL_INTERACTION_FREQUENCY]]
        self.assertEqual(counts, [1.0, 2.0, 3.0, 2.0])

    def test_sorts_and_filters_non_nomi_source(self) -> None:
        interactions = [
            _interaction(occurred_at=START + timedelta(days=2), latency_minutes=30),
            _interaction(occurred_at=START, latency_minutes=10),
            _interaction(occurred_at=START + timedelta(days=1), latency_minutes=99, source="import"),
        ]

        bundle = build_signal_series(interactions)

        latency = bundle.as_map()[SIGNAL_RESPONSE_LATENCY]
        self.assertEqual([point.value for point in latency], [10.0, 30.0])

    def test_drops_non_finite_values_and_counts_them(self) -> None:
        interactions = [
            _interaction(occurred_at=START, latency_minutes=12, wellbeing_score=4.0),
            _interaction(
                occurred_at=START + timedelta(days=1),
                latency_minutes=12,
                wellbeing_score=math.nan,
            ),
            _interaction(
                occurred_at=START + timedelta(days=2),
                latency_minutes=-5,
                wellbeing_score=3.0,
            ),
        ]

        bundle = build_signal_series(interactions)

        wellbeing = [point.value for point in bundle.as_map()[SIGNAL_WELLBEING]]
        latency = [point.value for point in bundle.as_map()[SIGNAL_RESPONSE_LATENCY]]
        self.assertEqual(wellbeing, [4.0, 3.0])
        self.assertEqual(latency, [12.0, 12.0])
        self.assertEqual(bundle.dropped_values, 2)

    def test_empty_input_yields_empty_series(self) -> None:
        bundle = build_signal_series([])

        self.assertEqual(bundle.as_map()[SIGNAL_RESPONSE_LATENCY], [])
        self.assertEqual(bundle.dropped_values, 0)


if __name__ == "__main__":
    unittest.main()
