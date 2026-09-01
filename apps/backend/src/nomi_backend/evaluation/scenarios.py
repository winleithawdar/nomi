from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy

from nomi_backend.baseline import SeniorInteraction

BASELINE_POINTS = 21
CHANGE_POINTS = 14
NORMAL_LATENCY = 25.0
NORMAL_LATENCY_SD = 3.0
NORMAL_WELLBEING = 4.0
_START = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
_DAY = timedelta(days=1)

SCENARIO_NAMES = (
    "stable",
    "isolated_late_response",
    "repeated_missed_checkins",
    "sudden_cessation",
    "gradual_latency_increase",
    "gradual_frequency_decline",
    "worsening_wellbeing",
    "recovery_to_normal",
)


@dataclass(frozen=True)
class ScenarioResult:
    interactions: list[SeniorInteraction]
    ground_truth: dict | None


def _checkin(
    occurred_at: datetime,
    latency: float | None,
    *,
    missed: bool = False,
    wellbeing: float | None = None,
) -> SeniorInteraction:
    sent_at = responded_at = None
    if latency is not None and not missed:
        sent_at = occurred_at - timedelta(minutes=float(latency))
        responded_at = occurred_at
    return SeniorInteraction(
        senior_id="synthetic",
        occurred_at=occurred_at,
        interaction_type="checkin_missed" if missed else "checkin_response",
        missed_checkin=missed,
        checkin_sent_at=sent_at,
        response_received_at=responded_at,
        wellbeing_score=wellbeing,
    )


def _normal_latency(rng: numpy.random.Generator) -> float:
    return float(max(1.0, rng.normal(NORMAL_LATENCY, NORMAL_LATENCY_SD)))


def _daily(day_index: int) -> datetime:
    return _START + day_index * _DAY


def generate_scenario(
    name: str,
    rng: numpy.random.Generator,
    senior_index: int,
) -> ScenarioResult:
    total = BASELINE_POINTS + CHANGE_POINTS
    onset = BASELINE_POINTS
    interactions: list[SeniorInteraction] = []
    ground_truth: dict | None = None

    if name == "stable":
        for day in range(total):
            interactions.append(_checkin(_daily(day), _normal_latency(rng), wellbeing=NORMAL_WELLBEING))

    elif name == "isolated_late_response":
        for day in range(total):
            latency = _normal_latency(rng)
            if day == onset + 3:
                latency = NORMAL_LATENCY + 60.0
            interactions.append(_checkin(_daily(day), latency, wellbeing=NORMAL_WELLBEING))

    elif name == "repeated_missed_checkins":
        for day in range(total):
            if day >= onset and (day - onset) % 2 == 0:
                interactions.append(_checkin(_daily(day), None, missed=True))
            else:
                interactions.append(_checkin(_daily(day), _normal_latency(rng), wellbeing=NORMAL_WELLBEING))
        ground_truth = {"signal": "missed_checkin_rate", "onset_index": onset, "kind": "sustained_change"}

    elif name == "sudden_cessation":
        for day in range(onset):
            interactions.append(_checkin(_daily(day), _normal_latency(rng), wellbeing=NORMAL_WELLBEING))
        # Cadence collapses from daily to every third day for the rest of the
        # window — a sustained drop in interaction frequency with enough
        # post-onset points to confirm.
        for step in range(CHANGE_POINTS // 2):
            interactions.append(_checkin(_daily(onset + step * 3), _normal_latency(rng), wellbeing=NORMAL_WELLBEING))
        ground_truth = {"signal": "interaction_frequency", "onset_index": onset, "kind": "sustained_change"}

    elif name == "gradual_latency_increase":
        for day in range(total):
            latency = _normal_latency(rng)
            if day >= onset:
                latency += 2.2 * (day - onset + 1)
            interactions.append(_checkin(_daily(day), latency, wellbeing=NORMAL_WELLBEING))
        ground_truth = {"signal": "response_latency_minutes", "onset_index": onset, "kind": "sustained_change"}

    elif name == "gradual_frequency_decline":
        day = 0
        gap = 1
        emitted = 0
        while day < total * 2 and emitted < total:
            interactions.append(_checkin(_daily(day), _normal_latency(rng), wellbeing=NORMAL_WELLBEING))
            emitted += 1
            if emitted > onset:
                gap = min(4, 1 + (emitted - onset) // 3)
            day += gap
        ground_truth = {"signal": "interaction_frequency", "onset_index": onset, "kind": "sustained_change"}

    elif name == "worsening_wellbeing":
        for day in range(total):
            wellbeing = NORMAL_WELLBEING
            if day >= onset:
                wellbeing = max(1.0, NORMAL_WELLBEING - 0.35 * (day - onset + 1))
            interactions.append(_checkin(_daily(day), _normal_latency(rng), wellbeing=wellbeing))
        ground_truth = {"signal": "wellbeing_score", "onset_index": onset, "kind": "sustained_change"}

    elif name == "recovery_to_normal":
        excursion_end = onset + 7
        for day in range(total):
            latency = _normal_latency(rng)
            if onset <= day < excursion_end:
                latency += 22.0
            interactions.append(_checkin(_daily(day), latency, wellbeing=NORMAL_WELLBEING))
        ground_truth = {"signal": "response_latency_minutes", "onset_index": onset, "kind": "sustained_change"}

    else:
        raise ValueError(f"unknown scenario: {name}")

    return ScenarioResult(interactions=interactions, ground_truth=ground_truth)


def _seed_for(name: str, seed: int) -> int:
    return (seed * 1_000_003 + zlib.crc32(name.encode("utf-8"))) & 0xFFFFFFFF


def generate_suite(name: str, seed: int, count: int) -> list[ScenarioResult]:
    rng = numpy.random.default_rng(_seed_for(name, seed))
    return [generate_scenario(name, rng, index) for index in range(count)]
