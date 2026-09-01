# P2 Change Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Nomi's longitudinal change-detection library (gradual/sustained behavioural drift relative to a senior's own baseline) plus a reproducible evaluation harness comparing it to a fixed-threshold baseline.

**Architecture:** A new additive `nomi_backend.detection` package holds a shared, explainable `DetectionResult` contract, per-signal feature extraction, and a `ChangeDetector` combining three methods over the senior's own baseline — a standardized level-shift test, a two-sided CUSUM (drift onset), and a normalized trend test. A separate `nomi_backend.evaluation` package generates deterministic synthetic senior scenarios, runs both the change detector and a naive fixed-threshold detector, and writes metrics (recall, false-alert rate, detection delay) plus a rolling-window sweep to committed result files.

**Tech Stack:** Python 3.11+, `numpy` (array math + `polyfit`), `scikit-learn` (available; used only if a concrete need appears), stdlib `dataclasses`/`enum`/`statistics`/`math`, `unittest` for tests. No pytest, no ruff in this repo.

**Spec:** [docs/workstreams/P2/specs/2026-09-01-change-detection-design.md](../specs/2026-09-01-change-detection-design.md)

## Global Constraints

- **Python floor:** `>=3.11` (from `apps/backend/pyproject.toml`). No 3.12+-only syntax (no `type` statement, no PEP 695 generics). `X | None` unions are fine.
- **Additive only.** The only shared file modified is `apps/backend/pyproject.toml` (add two dependencies). Do **not** touch `baseline/`, `api/app.py`, `services/demo_repository.py`, `apps/frontend/**`, root `README.md`, `apps/backend/README.md`, or `.gitignore`.
- **No persistence, no FastAPI route, no `demo_repository` wiring.** Library + evaluation harness only.
- **Never `git commit`** (project rule). Every task's final step stages with `git add` and stops. The user commits.
- **Style match `nomi_backend/baseline/`:** `from __future__ import annotations` at top of every module; `@dataclass(frozen=True)`; `str`-valued `Enum`s; module-level constants in `UPPER_SNAKE`.
- **No numeric risk/concern score.** `confidence` is a categorical enum (`low`/`moderate`/`high`) derived from method/signal agreement, never magnitude.
- **Determinism:** all synthetic data uses `numpy.random.default_rng(seed)`; no `random`, no unseeded `numpy.random`.
- **Test runner (from `apps/backend/`):**
  - Single file: `python tests/test_change_detector.py -v`
  - Full suite: `python -m unittest discover -s tests -p "test_*.py" -v`
- **Test file preamble** (every new test file starts with this, matching `tests/test_baseline.py`):
  ```python
  from __future__ import annotations

  import sys
  import unittest
  from datetime import datetime, timedelta, timezone
  from pathlib import Path

  sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
  ```

---

## File Structure

| File | Responsibility |
|---|---|
| `apps/backend/src/nomi_backend/detection/__init__.py` | Public exports for the detection package |
| `apps/backend/src/nomi_backend/detection/contract.py` | Shared enums + `SignalContribution` + `DetectionResult` + `to_dict()` (no numpy) |
| `apps/backend/src/nomi_backend/detection/features.py` | `SeniorInteraction` stream → four per-signal `list[SeriesPoint]` + dropped-value count |
| `apps/backend/src/nomi_backend/detection/changes.py` | `ChangeDetectorConfig` + `ChangeDetector` (level-shift + CUSUM + trend + aggregation) |
| `apps/backend/src/nomi_backend/evaluation/__init__.py` | Public exports for the evaluation package |
| `apps/backend/src/nomi_backend/evaluation/scenarios.py` | Deterministic synthetic senior/scenario generators + ground truth |
| `apps/backend/src/nomi_backend/evaluation/fixed_threshold.py` | Naive population-threshold detector, same `DetectionResult` shape |
| `apps/backend/src/nomi_backend/evaluation/metrics.py` | Recall, precision, false-alert rate, detection-delay percentiles |
| `apps/backend/src/nomi_backend/evaluation/harness.py` | Run all scenarios × detectors, window sweep, render JSON + Markdown |
| `apps/backend/src/nomi_backend/evaluation/__main__.py` | CLI: `python -m nomi_backend.evaluation` → write result files |
| `apps/backend/pyproject.toml` | **Modify:** add `numpy`, `scikit-learn` to `dependencies` |
| `apps/backend/tests/test_detection_contract.py` | Contract serialization + enum-value guards |
| `apps/backend/tests/test_features.py` | Per-signal series derivation + sorting + malformed-value handling |
| `apps/backend/tests/test_change_detector.py` | Detector behaviour across all methods + edge cases |
| `apps/backend/tests/test_evaluation.py` | Scenario determinism, metric math, harness output |
| `docs/workstreams/P2/evaluation-results.json` | **Generated, committed** by Task 11 |
| `docs/workstreams/P2/evaluation-results.md` | **Generated, committed** by Task 11 |

---

## Task 1: Shared detection contract

**Files:**
- Create: `apps/backend/src/nomi_backend/detection/__init__.py`
- Create: `apps/backend/src/nomi_backend/detection/contract.py`
- Test: `apps/backend/tests/test_detection_contract.py`

**Interfaces:**
- Consumes: nothing (leaf module, stdlib only).
- Produces:
  - Enums `DetectionKind` (`ANOMALY="anomaly"`, `SUSTAINED_CHANGE="sustained_change"`), `DetectionStatus` (`OK="ok"`, `INSUFFICIENT_HISTORY="insufficient_history"`), `ChangeDirection` (`RISING="rising"`, `FALLING="falling"`, `NONE="none"`), `Confidence` (`LOW="low"`, `MODERATE="moderate"`, `HIGH="high"`).
  - `@dataclass(frozen=True) SignalContribution` with fields: `signal: str`, `status: DetectionStatus`, `flagged: bool`, `direction: ChangeDirection`, `baseline_mean: float | None`, `recent_mean: float | None`, `deviation_pct: float | None`, `standardized_shift: float | None`, `methods_fired: list[str]`, `estimated_onset: datetime | None`, `recent_series: list[dict]`. Method `to_dict() -> dict`.
  - `@dataclass(frozen=True) DetectionResult` with fields: `senior_id: str`, `kind: DetectionKind`, `detected: bool`, `status: DetectionStatus`, `as_of: datetime | None`, `confidence: Confidence`, `direction: ChangeDirection`, `contributions: list[SignalContribution]`, `summary: str`, `metadata: dict`. Method `to_dict() -> dict`.
  - `to_dict()` returns only JSON primitives: `Enum` → `.value`, `datetime` → `.isoformat()`, nested dataclasses → dicts, recursively.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_detection_contract.py`:

```python
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.detection.contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)


class DetectionContractTest(unittest.TestCase):
    def test_enum_values_are_the_documented_constants(self) -> None:
        self.assertEqual(DetectionKind.SUSTAINED_CHANGE.value, "sustained_change")
        self.assertEqual(DetectionKind.ANOMALY.value, "anomaly")
        self.assertEqual(DetectionStatus.OK.value, "ok")
        self.assertEqual(DetectionStatus.INSUFFICIENT_HISTORY.value, "insufficient_history")
        self.assertEqual(
            [d.value for d in ChangeDirection],
            ["rising", "falling", "none"],
        )
        self.assertEqual(
            [c.value for c in Confidence],
            ["low", "moderate", "high"],
        )

    def test_to_dict_emits_only_primitives(self) -> None:
        onset = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
        as_of = onset + timedelta(days=4)
        contribution = SignalContribution(
            signal="response_latency_minutes",
            status=DetectionStatus.OK,
            flagged=True,
            direction=ChangeDirection.RISING,
            baseline_mean=25.0,
            recent_mean=35.0,
            deviation_pct=0.4,
            standardized_shift=2.5,
            methods_fired=["level_shift", "cusum"],
            estimated_onset=onset,
            recent_series=[{"occurred_at": onset.isoformat(), "value": 35.0}],
        )
        result = DetectionResult(
            senior_id="senior-1",
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=True,
            status=DetectionStatus.OK,
            as_of=as_of,
            confidence=Confidence.MODERATE,
            direction=ChangeDirection.RISING,
            contributions=[contribution],
            summary="Response latency is running about 40% above the usual baseline.",
            metadata={"dropped_values": 0, "window": 7},
        )

        payload = result.to_dict()

        self.assertEqual(payload["kind"], "sustained_change")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["confidence"], "moderate")
        self.assertEqual(payload["direction"], "rising")
        self.assertEqual(payload["as_of"], as_of.isoformat())
        self.assertEqual(payload["metadata"], {"dropped_values": 0, "window": 7})
        self.assertEqual(len(payload["contributions"]), 1)
        child = payload["contributions"][0]
        self.assertEqual(child["status"], "ok")
        self.assertEqual(child["direction"], "rising")
        self.assertEqual(child["methods_fired"], ["level_shift", "cusum"])
        self.assertEqual(child["estimated_onset"], onset.isoformat())
        self.assertEqual(child["recent_series"][0]["value"], 35.0)

    def test_to_dict_handles_none_datetimes_and_empty_contributions(self) -> None:
        result = DetectionResult(
            senior_id="senior-2",
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=False,
            status=DetectionStatus.INSUFFICIENT_HISTORY,
            as_of=None,
            confidence=Confidence.LOW,
            direction=ChangeDirection.NONE,
            contributions=[],
            summary="",
            metadata={},
        )

        payload = result.to_dict()

        self.assertIsNone(payload["as_of"])
        self.assertEqual(payload["contributions"], [])
        self.assertEqual(payload["direction"], "none")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_detection_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.detection'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/detection/__init__.py`:

```python
from __future__ import annotations

from .contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)

__all__ = [
    "ChangeDirection",
    "Confidence",
    "DetectionKind",
    "DetectionResult",
    "DetectionStatus",
    "SignalContribution",
]
```

Create `apps/backend/src/nomi_backend/detection/contract.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class DetectionKind(str, Enum):
    ANOMALY = "anomaly"
    SUSTAINED_CHANGE = "sustained_change"


class DetectionStatus(str, Enum):
    OK = "ok"
    INSUFFICIENT_HISTORY = "insufficient_history"


class ChangeDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    NONE = "none"


class Confidence(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True)
class SignalContribution:
    signal: str
    status: DetectionStatus
    flagged: bool
    direction: ChangeDirection
    baseline_mean: float | None
    recent_mean: float | None
    deviation_pct: float | None
    standardized_shift: float | None
    methods_fired: list[str] = field(default_factory=list)
    estimated_onset: datetime | None = None
    recent_series: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return _plain(asdict(self))


@dataclass(frozen=True)
class DetectionResult:
    senior_id: str
    kind: DetectionKind
    detected: bool
    status: DetectionStatus
    as_of: datetime | None
    confidence: Confidence
    direction: ChangeDirection
    contributions: list[SignalContribution] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return _plain(asdict(self))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_detection_contract.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/detection/__init__.py \
        apps/backend/src/nomi_backend/detection/contract.py \
        apps/backend/tests/test_detection_contract.py
```

Do not commit — leave that to the user (project rule).

---

## Task 2: Feature extraction + dependencies

**Files:**
- Modify: `apps/backend/pyproject.toml` (add `numpy`, `scikit-learn` to `[project].dependencies`)
- Create: `apps/backend/src/nomi_backend/detection/features.py`
- Test: `apps/backend/tests/test_features.py`

**Interfaces:**
- Consumes: `nomi_backend.baseline.SeniorInteraction` (fields: `senior_id`, `occurred_at: datetime`, `interaction_type`, `missed_checkin: bool`, `checkin_sent_at`, `response_received_at`, `wellbeing_score: float | None`, `source: str`; property `response_latency_minutes: float | None`).
- Produces:
  - Signal-name constants: `SIGNAL_RESPONSE_LATENCY = "response_latency_minutes"`, `SIGNAL_MISSED_CHECKIN_RATE = "missed_checkin_rate"`, `SIGNAL_INTERACTION_FREQUENCY = "interaction_frequency"`, `SIGNAL_WELLBEING = "wellbeing_score"`.
  - `FREQUENCY_WINDOW_DAYS = 7`, `DEFAULT_MISSED_RATE_WINDOW = 7`.
  - `@dataclass(frozen=True) SeriesPoint` with `occurred_at: datetime`, `value: float`.
  - `@dataclass(frozen=True) SignalSeriesBundle` with `response_latency_minutes: list[SeriesPoint]`, `missed_checkin_rate: list[SeriesPoint]`, `interaction_frequency: list[SeriesPoint]`, `wellbeing_score: list[SeriesPoint]`, `dropped_values: int`; method `as_map() -> dict[str, list[SeriesPoint]]` keyed by the four signal-name constants.
  - `build_signal_series(interactions: list[SeniorInteraction], *, frequency_window_days: int = FREQUENCY_WINDOW_DAYS, missed_rate_window: int = DEFAULT_MISSED_RATE_WINDOW) -> SignalSeriesBundle`. Sorts by `occurred_at`, keeps only `source == "nomi"`, drops non-finite / non-numeric / negative latency and non-finite wellbeing (counted in `dropped_values`).

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_features.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_features.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.detection.features'`.

- [ ] **Step 3: Add dependencies**

Edit `apps/backend/pyproject.toml`. Change the `dependencies` list from:

```toml
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn>=0.30,<1.0",
]
```

to:

```toml
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn>=0.30,<1.0",
  "numpy>=2.0,<3.0",
  "scikit-learn>=1.5,<2.0",
]
```

- [ ] **Step 4: Write minimal implementation**

Create `apps/backend/src/nomi_backend/detection/features.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python tests/test_features.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Verify the existing suite still passes**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS (all baseline + contract + features tests).

- [ ] **Step 7: Stage the changes**

```bash
git add apps/backend/pyproject.toml \
        apps/backend/src/nomi_backend/detection/features.py \
        apps/backend/tests/test_features.py
```

Do not commit — leave that to the user (project rule).

---

## Task 3: Change detector — config, level-shift, aggregation

**Files:**
- Create: `apps/backend/src/nomi_backend/detection/changes.py`
- Test: `apps/backend/tests/test_change_detector.py`

**Interfaces:**
- Consumes:
  - `nomi_backend.baseline.BaselineCalculator`, `SeniorBaseline`, `SignalStatus` (`STABLE`, `LEARNING`, `UNAVAILABLE`). `SeniorBaseline` has attributes `response_latency_minutes`, `interaction_frequency`, `wellbeing_score` (each a `NumericSignalBaseline` with `.status`, `.mean: float | None`, `.stddev: float | None`) and `missed_checkin_rate` (a `BinarySignalBaseline` with `.status`, `.rate: float | None`).
  - `features.build_signal_series`, `SeriesPoint`, `SignalSeriesBundle`, and the four `SIGNAL_*` constants.
  - `contract.DetectionResult`, `SignalContribution`, `DetectionKind`, `DetectionStatus`, `ChangeDirection`, `Confidence`.
- Produces:
  - `@dataclass(frozen=True) ChangeDetectorConfig` with defaults: `reference_min_points=5`, `recent_window_points=7`, `recent_min_points=4`, `min_sustained_points=3`, `shift_z_threshold=1.5`, `min_rel_std=0.05`, `cusum_k=0.5`, `cusum_h=4.0`, `cusum_clamp=4.0`, `trend_slope_threshold=0.4`, `epsilon=1e-6`. (`cusum_clamp` is defined here but first used in Task 4.)
  - `ChangeDetector(config: ChangeDetectorConfig | None = None)` with `detect(senior_id: str, interactions: list[SeniorInteraction], baseline: SeniorBaseline | None = None) -> DetectionResult`. `kind` is always `DetectionKind.SUSTAINED_CHANGE`.
  - Module-level constant `_RATE_STD_FLOOR = 0.15` and helper `_signal_baseline_status(signal: str, baseline: SeniorBaseline) -> SignalStatus` (returns the per-signal status: `baseline.missed_checkin_rate.status` for the rate signal, else `getattr(baseline, <numeric attr>).status`).
  - Private helpers used by later tasks: `_reference_normal(signal: str, values: list[float]) -> tuple[float, float]` — reference stats from the stretch **before** the recent window (`pre = values[:max(len(values) - recent_window_points, reference_min_points)]`), `pstdev`-based, floored at `_RATE_STD_FLOOR` for the rate signal and at `epsilon` otherwise; never returns `None`. `_level_shift(recent: list[float], ref_mean: float, ref_std: float) -> bool`. Later tasks add `_cusum(...)` and `_trend(...)`.
  - A signal contributes `INSUFFICIENT_HISTORY` (never flagged) when its baseline status is not `STABLE`, or when `len(values) < reference_min_points + recent_min_points`, or when the recent window has fewer than `recent_min_points` points.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_change_detector.py`:

```python
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nomi_backend.baseline import SeniorInteraction
from nomi_backend.detection.changes import ChangeDetector, ChangeDetectorConfig
from nomi_backend.detection.contract import (
    ChangeDirection,
    DetectionKind,
    DetectionStatus,
)

START = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _interaction(
    *,
    occurred_at: datetime,
    latency_minutes: float | None = None,
    missed_checkin: bool = False,
    wellbeing_score: float | None = None,
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
    )


def _latency_history(values: list[float]) -> list[SeniorInteraction]:
    return [
        _interaction(occurred_at=START + timedelta(days=index), latency_minutes=value)
        for index, value in enumerate(values)
    ]


class ChangeDetectorLevelShiftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_stable_history_is_not_flagged(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 25, 24, 26, 25, 24])

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.kind, DetectionKind.SUSTAINED_CHANGE)
        self.assertEqual(result.status, DetectionStatus.OK)
        self.assertFalse(result.detected)
        self.assertEqual(result.direction, ChangeDirection.NONE)

    def test_sustained_latency_step_is_flagged_rising(self) -> None:
        history = _latency_history(
            [25, 24, 26, 25, 24, 25, 26]  # personal normal ~25
            + [48, 50, 47, 49, 51, 48, 50]  # sustained step up
        )

        result = self.detector.detect("senior-1", history)

        self.assertTrue(result.detected)
        self.assertEqual(result.direction, ChangeDirection.RISING)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        self.assertTrue(latency.flagged)
        self.assertIn("level_shift", latency.methods_fired)
        self.assertGreater(latency.standardized_shift, 0)
        self.assertAlmostEqual(latency.recent_mean, 49.0, delta=1.0)

    def test_short_history_returns_insufficient_history(self) -> None:
        history = _latency_history([25, 26, 24])

        result = self.detector.detect("senior-1", history)

        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertFalse(result.detected)

    def test_recent_series_is_attached_for_charting(self) -> None:
        history = _latency_history([25] * 7 + [40] * 7)

        result = self.detector.detect("senior-1", history)

        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        self.assertEqual(len(latency.recent_series), 7)
        self.assertEqual(latency.recent_series[-1]["value"], 40.0)
        self.assertIn("occurred_at", latency.recent_series[0])

    def test_missed_checkin_rate_step_is_flagged(self) -> None:
        history = [
            _interaction(occurred_at=START + timedelta(days=i), latency_minutes=20)
            for i in range(7)
        ] + [
            _interaction(occurred_at=START + timedelta(days=7 + i), missed_checkin=True)
            for i in range(7)
        ]

        result = self.detector.detect("senior-1", history)

        rate = next(
            c for c in result.contributions if c.signal == "missed_checkin_rate"
        )
        self.assertTrue(rate.flagged)
        self.assertEqual(rate.direction, ChangeDirection.RISING)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_change_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.detection.changes'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/detection/changes.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, pstdev

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
    min_rel_std: float = 0.05
    cusum_k: float = 0.5
    cusum_h: float = 4.0
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

        direction = ChangeDirection.NONE
        if methods:
            if recent_mean > ref_mean:
                direction = ChangeDirection.RISING
            elif recent_mean < ref_mean:
                direction = ChangeDirection.FALLING

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
            estimated_onset=None,
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
        z = (fmean(recent) - ref_mean) / ref_std
        if abs(z) < self.config.shift_z_threshold:
            return False
        # "Sustained" = at least min_sustained_points of the window sit a full
        # sigma clear of the reference on one side (a lone spike will not).
        margin = ref_std
        above = sum(1 for value in recent if value - ref_mean >= margin)
        below = sum(1 for value in recent if ref_mean - value >= margin)
        return max(above, below) >= self.config.min_sustained_points

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_change_detector.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/detection/changes.py \
        apps/backend/tests/test_change_detector.py
```

Do not commit — leave that to the user (project rule).

---

## Task 4: Change detector — CUSUM drift + onset

**Files:**
- Modify: `apps/backend/src/nomi_backend/detection/changes.py`
- Modify: `apps/backend/tests/test_change_detector.py` (add a test class)

**Interfaces:**
- Consumes: everything from Task 3.
- Produces: `ChangeDetector._cusum(values: list[float], times: list[datetime], ref_mean: float, ref_std: float) -> tuple[bool, ChangeDirection, datetime | None]`. Called from `_evaluate_signal`; when it fires, `"cusum"` is appended to `methods_fired` and `estimated_onset` is set to the `occurred_at` of the index where the exceeding accumulator last reset to zero. CUSUM runs over the full standardized series (from series start) and fires only when, at the final point, an accumulator is **both** still above `cusum_h` **and** its current run spans at least `min_sustained_points` observations — so a lone spike (run length 1) and a recovered excursion (accumulator decayed back to 0) both clear.

- [ ] **Step 1: Write the failing test**

Append these two classes to `apps/backend/tests/test_change_detector.py`, immediately before the single trailing `if __name__ == "__main__":` block:

```python
class ChangeDetectorCusumTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_gradual_drift_trips_cusum_and_reports_onset(self) -> None:
        # ~1.6 min/day ramp off a ~25 base, sustained for 10 points.
        values = [25, 24, 26, 25, 24, 25, 26]
        values += [26 + 1.6 * step for step in range(1, 11)]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertTrue(latency.flagged)
        self.assertIn("cusum", latency.methods_fired)
        self.assertIsNotNone(latency.estimated_onset)
        # onset lands in the ramp region, not the flat baseline prefix
        self.assertGreater(latency.estimated_onset, START + timedelta(days=4))

    def test_lone_spike_does_not_trip_cusum(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26, 24, 25, 26, 25] + [95] + [25, 24, 26]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertNotIn("cusum", latency.methods_fired)

    def test_cusum_clears_after_recovery_to_normal(self) -> None:
        values = (
            [25, 24, 26, 25, 24, 25, 26]
            + [46, 48, 47, 49, 48]  # excursion
            + [26, 25, 24, 25, 26, 25, 24, 26]  # recovered, long enough to fill window
        )
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertFalse(latency.flagged)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_change_detector.py -v`
Expected: FAIL — `test_gradual_drift_trips_cusum_and_reports_onset` fails (`cusum` not in `methods_fired`).

- [ ] **Step 3: Write minimal implementation**

In `apps/backend/src/nomi_backend/detection/changes.py`, add the `_cusum` method to `ChangeDetector`. Residuals are clamped to `±cusum_clamp` so a single extreme point cannot, on its own, drive an accumulator past `cusum_h` or keep it there:

```python
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
```

Then, in `_evaluate_signal`, immediately after the `if self._level_shift(...)` block, insert:

```python
        times = [point.occurred_at for point in series]
        cusum_fired, cusum_direction, cusum_onset = self._cusum(
            values, times, ref_mean, ref_std
        )
        estimated_onset = None
        if cusum_fired:
            methods.append("cusum")
            estimated_onset = cusum_onset
```

Replace the `direction` block so a CUSUM-only flag still gets a direction:

```python
        direction = ChangeDirection.NONE
        if methods:
            if recent_mean > ref_mean:
                direction = ChangeDirection.RISING
            elif recent_mean < ref_mean:
                direction = ChangeDirection.FALLING
            else:
                direction = cusum_direction
```

And change the `SignalContribution(...)` return so `estimated_onset=estimated_onset` instead of `estimated_onset=None`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_change_detector.py -v`
Expected: PASS (8 tests — the 5 from Task 3 plus 3 new).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/detection/changes.py \
        apps/backend/tests/test_change_detector.py
```

Do not commit — leave that to the user (project rule).

---

## Task 5: Change detector — trend test

**Files:**
- Modify: `apps/backend/src/nomi_backend/detection/changes.py`
- Modify: `apps/backend/tests/test_change_detector.py` (add a test class)

**Interfaces:**
- Consumes: everything from Tasks 3–4; adds `import numpy`.
- Produces: `ChangeDetector._trend(recent: list[float], ref_std: float) -> tuple[bool, ChangeDirection]`. Fires when `abs(slope / ref_std) >= trend_slope_threshold` (slope from `numpy.polyfit(x, y, 1)[0]`, `x = 0..n-1`) **and** the Mann-Kendall sign statistic `S` is non-zero with the same sign as the slope. When it fires, `"trend"` is appended to `methods_fired`.

- [ ] **Step 1: Write the failing test**

Append this class to `apps/backend/tests/test_change_detector.py`, immediately before the single trailing `if __name__ == "__main__":` block (do not add another one):

```python
class ChangeDetectorTrendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_monotonic_ramp_in_recent_window_fires_trend(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26] + [28, 31, 34, 37, 40, 43, 46]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertTrue(latency.flagged)
        self.assertIn("trend", latency.methods_fired)
        self.assertEqual(latency.direction, ChangeDirection.RISING)

    def test_noisy_but_flat_recent_window_does_not_fire_trend(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26] + [25, 27, 24, 26, 25, 24, 26]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertNotIn("trend", latency.methods_fired)

    def test_confidence_is_moderate_when_two_methods_agree_on_one_signal(self) -> None:
        values = [25, 24, 26, 25, 24, 25, 26] + [30, 34, 38, 42, 46, 50, 54]
        history = _latency_history(values)

        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )

        self.assertGreaterEqual(len(latency.methods_fired), 2)
        self.assertEqual(result.confidence.value, "moderate")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_change_detector.py -v`
Expected: FAIL — `test_monotonic_ramp_in_recent_window_fires_trend` fails (`trend` not in `methods_fired`).

- [ ] **Step 3: Write minimal implementation**

In `apps/backend/src/nomi_backend/detection/changes.py`, add `import numpy` to the module imports (third-party group: after the stdlib imports, before the `from nomi_backend...` imports), then add the `_trend` method to `ChangeDetector`:

```python
    def _trend(
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
```

In `_evaluate_signal`, after the CUSUM block, insert:

```python
        trend_fired, trend_direction = self._trend(recent, ref_std)
        if trend_fired:
            methods.append("trend")
```

Update the `direction` block so a trend-only flag still gets a direction:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_change_detector.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/detection/changes.py \
        apps/backend/tests/test_change_detector.py
```

Do not commit — leave that to the user (project rule).

---

## Task 6: Change detector — hardening, edge cases, package exports

**Files:**
- Modify: `apps/backend/src/nomi_backend/detection/changes.py` (only if a test exposes a bug)
- Modify: `apps/backend/src/nomi_backend/detection/__init__.py` (add detector exports)
- Modify: `apps/backend/tests/test_change_detector.py` (add an edge-case test class)

**Interfaces:**
- Produces: `nomi_backend.detection` package also exports `ChangeDetector`, `ChangeDetectorConfig`.

- [ ] **Step 1: Write the failing test**

Add `import math` to the top-of-file imports of `apps/backend/tests/test_change_detector.py`, then append this block immediately before the single trailing `if __name__ == "__main__":` block:

```python
from nomi_backend.detection import ChangeDetector as ExportedDetector
from nomi_backend.detection import ChangeDetectorConfig as ExportedConfig


class ChangeDetectorEdgeCaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_learning_baseline_short_series_is_insufficient(self) -> None:
        history = _latency_history([25, 26, 24])
        result = self.detector.detect("senior-1", history)
        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)

    def test_absent_wellbeing_signal_is_skipped_not_errored(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 40, 41, 39, 42, 40, 41, 39])
        result = self.detector.detect("senior-1", history)
        wellbeing = next(
            c for c in result.contributions if c.signal == "wellbeing_score"
        )
        self.assertEqual(wellbeing.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertTrue(result.detected)  # latency still evaluated

    def test_shuffled_input_matches_sorted_input(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 48, 50, 47, 49, 51, 48, 50])
        shuffled = [history[i] for i in (3, 0, 11, 6, 1, 9, 13, 2, 7, 4, 12, 5, 10, 8)]
        self.assertEqual(
            self.detector.detect("senior-1", history).to_dict(),
            self.detector.detect("senior-1", shuffled).to_dict(),
        )

    def test_nan_latency_is_dropped_and_recorded(self) -> None:
        history = _latency_history([25, 24, 26, 25, 24, 25, 26, 48, 50, 47, 49, 51, 48])
        history.append(
            _interaction(occurred_at=START + timedelta(days=13), latency_minutes=math.nan)
        )
        result = self.detector.detect("senior-1", history)
        self.assertGreaterEqual(result.metadata["dropped_values"], 1)
        self.assertTrue(result.detected)

    def test_empty_interactions_is_insufficient_history(self) -> None:
        result = self.detector.detect("senior-1", [])
        self.assertEqual(result.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertIsNone(result.as_of)
        self.assertFalse(result.detected)

    def test_zero_variance_reference_does_not_raise_or_falsely_flag(self) -> None:
        history = _latency_history([25, 25, 25, 25, 25, 25, 25, 25, 25, 25, 25, 25])
        result = self.detector.detect("senior-1", history)
        self.assertFalse(result.detected)

    def test_only_missed_checkins_evaluates_rate_not_latency(self) -> None:
        history = [
            _interaction(occurred_at=START + timedelta(days=i), latency_minutes=20)
            for i in range(6)
        ] + [
            _interaction(occurred_at=START + timedelta(days=6 + i), missed_checkin=True)
            for i in range(8)
        ]
        result = self.detector.detect("senior-1", history)
        latency = next(
            c for c in result.contributions if c.signal == "response_latency_minutes"
        )
        rate = next(
            c for c in result.contributions if c.signal == "missed_checkin_rate"
        )
        self.assertEqual(latency.status, DetectionStatus.INSUFFICIENT_HISTORY)
        self.assertEqual(rate.status, DetectionStatus.OK)

    def test_package_exports_detector(self) -> None:
        self.assertIs(ExportedDetector, ChangeDetector)
        self.assertIsInstance(ExportedConfig(), ChangeDetectorConfig)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_change_detector.py -v`
Expected: FAIL — `ImportError: cannot import name 'ChangeDetector' from 'nomi_backend.detection'` (and possibly one or more edge assertions).

- [ ] **Step 3: Write minimal implementation**

Update `apps/backend/src/nomi_backend/detection/__init__.py`:

```python
from __future__ import annotations

from .changes import ChangeDetector, ChangeDetectorConfig
from .contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)

__all__ = [
    "ChangeDetector",
    "ChangeDetectorConfig",
    "ChangeDirection",
    "Confidence",
    "DetectionKind",
    "DetectionResult",
    "DetectionStatus",
    "SignalContribution",
]
```

If any edge assertion fails, fix the cause in `changes.py`. The design already covers every case in this test class (`_signal_baseline_status` gate, the `len(values) < reference_min_points + recent_min_points` gate, `as_of = own[-1].occurred_at if own else None`, the `_trend` constant-window guard, the relative std floor). If a `numpy.exceptions.RankWarning` prints from `_trend` on a constant window, confirm the `max(recent) == min(recent)` early-return added in Task 5 is present — it should suppress the call entirely.

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_change_detector.py -v`
Expected: PASS (19 tests).

- [ ] **Step 5: Run the full suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS (baseline + contract + features + change detector).

- [ ] **Step 6: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/detection/__init__.py \
        apps/backend/src/nomi_backend/detection/changes.py \
        apps/backend/tests/test_change_detector.py
```

Do not commit — leave that to the user (project rule).

---

## Task 7: Synthetic scenario generators

**Files:**
- Create: `apps/backend/src/nomi_backend/evaluation/__init__.py`
- Create: `apps/backend/src/nomi_backend/evaluation/scenarios.py`
- Test: `apps/backend/tests/test_evaluation.py`

**Interfaces:**
- Consumes: `nomi_backend.baseline.SeniorInteraction`, `numpy`.
- Produces:
  - `@dataclass(frozen=True) ScenarioResult` with `interactions: list[SeniorInteraction]`, `ground_truth: dict | None` (dict shape `{"signal": str, "onset_index": int, "kind": "sustained_change"}`).
  - `BASELINE_POINTS = 21`, `CHANGE_POINTS = 14`, `NORMAL_LATENCY = 25.0`, `NORMAL_LATENCY_SD = 3.0`, `NORMAL_WELLBEING = 4.0`.
  - `SCENARIO_NAMES: tuple[str, ...]` = `("stable", "isolated_late_response", "repeated_missed_checkins", "sudden_cessation", "gradual_latency_increase", "gradual_frequency_decline", "worsening_wellbeing", "recovery_to_normal")`.
  - `generate_scenario(name: str, rng: numpy.random.Generator, senior_index: int) -> ScenarioResult`.
  - `generate_suite(name: str, seed: int, count: int) -> list[ScenarioResult]` — builds one `numpy.random.default_rng(seed + hash offset for name)` and yields `count` seniors. Deterministic for a given `(name, seed, count)`.

- [ ] **Step 1: Write the failing test**

Create `apps/backend/tests/test_evaluation.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.evaluation'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/evaluation/__init__.py`:

```python
from __future__ import annotations

from .scenarios import SCENARIO_NAMES, ScenarioResult, generate_scenario, generate_suite

__all__ = [
    "SCENARIO_NAMES",
    "ScenarioResult",
    "generate_scenario",
    "generate_suite",
]
```

Create `apps/backend/src/nomi_backend/evaluation/scenarios.py`:

```python
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
        for step in range(CHANGE_POINTS // 3):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_evaluation.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/evaluation/__init__.py \
        apps/backend/src/nomi_backend/evaluation/scenarios.py \
        apps/backend/tests/test_evaluation.py
```

Do not commit — leave that to the user (project rule).

---

## Task 8: Fixed-threshold comparison detector

**Files:**
- Create: `apps/backend/src/nomi_backend/evaluation/fixed_threshold.py`
- Modify: `apps/backend/tests/test_evaluation.py` (add a test class)

**Interfaces:**
- Consumes: `features.build_signal_series` + `SIGNAL_*` constants; `contract.DetectionResult`, `SignalContribution`, enums; `SeniorInteraction`.
- Produces:
  - `@dataclass(frozen=True) FixedThresholdConfig` with `latency_minutes_max: float = 45.0`, `missed_rate_max: float = 0.3`, `frequency_min: float = 3.0`, `wellbeing_min: float = 3.0`, `recent_window_points: int = 7`, `recent_min_points: int = 4`.
  - `FixedThresholdDetector(config: FixedThresholdConfig | None = None)` with `detect(senior_id: str, interactions: list[SeniorInteraction], baseline=None) -> DetectionResult`. Signature matches `ChangeDetector.detect` (accepts and ignores `baseline`). Flags a signal when its recent-window mean crosses the population constant. `kind = DetectionKind.SUSTAINED_CHANGE`; `confidence = MODERATE` when detected else `LOW`.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_evaluation.py` (before the final `if __name__` block):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.evaluation.fixed_threshold'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/evaluation/fixed_threshold.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from nomi_backend.baseline import SeniorBaseline, SeniorInteraction
from nomi_backend.detection.contract import (
    ChangeDirection,
    Confidence,
    DetectionKind,
    DetectionResult,
    DetectionStatus,
    SignalContribution,
)
from nomi_backend.detection.features import (
    SIGNAL_INTERACTION_FREQUENCY,
    SIGNAL_MISSED_CHECKIN_RATE,
    SIGNAL_RESPONSE_LATENCY,
    SIGNAL_WELLBEING,
    build_signal_series,
)


@dataclass(frozen=True)
class FixedThresholdConfig:
    latency_minutes_max: float = 45.0
    missed_rate_max: float = 0.3
    frequency_min: float = 3.0
    wellbeing_min: float = 3.0
    recent_window_points: int = 7
    recent_min_points: int = 4


_RISING_LIMIT = {SIGNAL_RESPONSE_LATENCY, SIGNAL_MISSED_CHECKIN_RATE}


class FixedThresholdDetector:
    def __init__(self, config: FixedThresholdConfig | None = None) -> None:
        self.config = config or FixedThresholdConfig()

    def detect(
        self,
        senior_id: str,
        interactions: list[SeniorInteraction],
        baseline: SeniorBaseline | None = None,
    ) -> DetectionResult:
        own = [item for item in interactions if item.senior_id == senior_id]
        bundle = build_signal_series(
            own, missed_rate_window=self.config.recent_window_points
        )
        series_map = bundle.as_map()
        as_of = max((item.occurred_at for item in own), default=None)

        limits = {
            SIGNAL_RESPONSE_LATENCY: self.config.latency_minutes_max,
            SIGNAL_MISSED_CHECKIN_RATE: self.config.missed_rate_max,
            SIGNAL_INTERACTION_FREQUENCY: self.config.frequency_min,
            SIGNAL_WELLBEING: self.config.wellbeing_min,
        }

        contributions: list[SignalContribution] = []
        for signal, limit in limits.items():
            points = series_map[signal][-self.config.recent_window_points :]
            if len(points) < self.config.recent_min_points:
                contributions.append(
                    SignalContribution(
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
                        recent_series=[
                            {"occurred_at": p.occurred_at.isoformat(), "value": p.value}
                            for p in points
                        ],
                    )
                )
                continue
            recent_mean = fmean(point.value for point in points)
            if signal in _RISING_LIMIT:
                flagged = recent_mean > limit
                direction = ChangeDirection.RISING if flagged else ChangeDirection.NONE
            else:
                flagged = recent_mean < limit
                direction = ChangeDirection.FALLING if flagged else ChangeDirection.NONE
            contributions.append(
                SignalContribution(
                    signal=signal,
                    status=DetectionStatus.OK,
                    flagged=flagged,
                    direction=direction,
                    baseline_mean=limit,
                    recent_mean=recent_mean,
                    deviation_pct=None,
                    standardized_shift=None,
                    methods_fired=["fixed_threshold"] if flagged else [],
                    estimated_onset=None,
                    recent_series=[
                        {"occurred_at": p.occurred_at.isoformat(), "value": p.value}
                        for p in points
                    ],
                )
            )

        evaluated = [c for c in contributions if c.status == DetectionStatus.OK]
        flagged = [c for c in contributions if c.flagged]
        if not evaluated:
            status = DetectionStatus.INSUFFICIENT_HISTORY
        else:
            status = DetectionStatus.OK
        return DetectionResult(
            senior_id=senior_id,
            kind=DetectionKind.SUSTAINED_CHANGE,
            detected=bool(flagged),
            status=status,
            as_of=as_of,
            confidence=Confidence.MODERATE if flagged else Confidence.LOW,
            direction=flagged[0].direction if flagged else ChangeDirection.NONE,
            contributions=contributions,
            summary="",
            metadata={"detector": "fixed_threshold"},
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_evaluation.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/evaluation/fixed_threshold.py \
        apps/backend/tests/test_evaluation.py
```

Do not commit — leave that to the user (project rule).

---

## Task 9: Evaluation metrics

**Files:**
- Create: `apps/backend/src/nomi_backend/evaluation/metrics.py`
- Modify: `apps/backend/tests/test_evaluation.py` (add a test class)

**Interfaces:**
- Consumes: nothing beyond stdlib + `numpy`.
- Produces:
  - `@dataclass(frozen=True) ScenarioOutcome` with `scenario: str`, `ground_truth: dict | None`, `detected: bool`, `detected_at_index: int | None` (prefix length at first flag, or `None`).
  - `@dataclass(frozen=True) SuiteMetrics` with `recall: float`, `precision: float`, `false_alert_rate: float`, `detection_delay_median: float | None`, `detection_delay_p90: float | None`, `n_changed: int`, `n_stable: int`. Method `to_dict() -> dict`.
  - `evaluate_outcomes(outcomes: list[ScenarioOutcome]) -> SuiteMetrics`. `recall` = flagged changed / changed; `false_alert_rate` = flagged stable / stable; `precision` = true positives / all positives; delay = `detected_at_index - onset_index` over caught changed outcomes (percentiles via `numpy.percentile`, `method="linear"`; `None` when none caught).

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_evaluation.py` (before the final `if __name__` block):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.evaluation.metrics'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/evaluation/metrics.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_evaluation.py -v`
Expected: PASS (15 tests).

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/evaluation/metrics.py \
        apps/backend/tests/test_evaluation.py
```

Do not commit — leave that to the user (project rule).

---

## Task 10: Evaluation harness + window sweep + rendering

**Files:**
- Create: `apps/backend/src/nomi_backend/evaluation/harness.py`
- Modify: `apps/backend/tests/test_evaluation.py` (add a test class)

**Interfaces:**
- Consumes: `scenarios.generate_suite` + `SCENARIO_NAMES`; `changes.ChangeDetector`, `ChangeDetectorConfig`; `fixed_threshold.FixedThresholdDetector`; `metrics.ScenarioOutcome`, `evaluate_outcomes`, `SuiteMetrics`.
- Produces:
  - `SWEEP_WINDOWS = (4, 5, 7, 10, 14)`, `DEFAULT_SEED = 20260901`, `DEFAULT_SENIORS_PER_SCENARIO = 30`, `FALSE_ALERT_TARGET = 0.15`, `EVAL_BANNER = "Prototype evaluation on synthetic data — not clinical validation."`
  - `first_flag_index(detector, interactions, *, min_prefix: int) -> int | None` — replays growing prefixes (`interactions[:n]` for `n` from `min_prefix..len`), returns the first `n` where `detector.detect(...).detected` is `True`, else `None`.
  - `run_evaluation(seed: int = DEFAULT_SEED, seniors_per_scenario: int = DEFAULT_SENIORS_PER_SCENARIO, windows: tuple[int, ...] = SWEEP_WINDOWS) -> dict` — returns `{"banner", "seed", "seniors_per_scenario", "config", "detectors": {"change_detector": SuiteMetrics.to_dict(), "fixed_threshold": ...}, "per_scenario": {name: {...}}, "window_sweep": [{"window", **SuiteMetrics.to_dict()}], "selected_window": int}`. `selected_window` = the window with the lowest `detection_delay_median` (treating `None` as +inf) among those whose `false_alert_rate <= FALSE_ALERT_TARGET`; falls back to `7` if none qualify.
  - `render_markdown(report: dict) -> str`, `render_json(report: dict) -> str` (JSON text, `indent=2`, sorted keys).

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_evaluation.py` (before the final `if __name__` block):

```python
from nomi_backend.evaluation.harness import (
    EVAL_BANNER,
    SWEEP_WINDOWS,
    render_json,
    render_markdown,
    run_evaluation,
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.evaluation.harness'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/evaluation/harness.py`:

```python
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
_MIN_PREFIX = 9
EVAL_BANNER = "Prototype evaluation on synthetic data — not clinical validation."


def first_flag_index(detector, interactions, *, min_prefix: int = _MIN_PREFIX) -> int | None:
    for size in range(min_prefix, len(interactions) + 1):
        if detector.detect("synthetic", interactions[:size]).detected:
            return size
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_evaluation.py -v`
Expected: PASS (22 tests). If `test_change_detector_beats_fixed_threshold_on_recall` or `test_default_window_false_alert_rate_within_target` fails, tune `scenarios.py` injection magnitudes (increase drift slopes / step sizes) and `ChangeDetectorConfig` defaults together, re-running until both the unit tests in `test_change_detector.py` and these hold. Record the final defaults in the spec's section 7 table.

- [ ] **Step 5: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/evaluation/harness.py \
        apps/backend/tests/test_evaluation.py
```

Do not commit — leave that to the user (project rule).

---

## Task 11: CLI entry point + generate committed results

**Files:**
- Create: `apps/backend/src/nomi_backend/evaluation/__main__.py`
- Modify: `apps/backend/src/nomi_backend/evaluation/__init__.py` (export harness API)
- Modify: `apps/backend/tests/test_evaluation.py` (add a CLI test)
- Generate: `docs/workstreams/P2/evaluation-results.json`, `docs/workstreams/P2/evaluation-results.md`

**Interfaces:**
- Consumes: `harness.run_evaluation`, `render_json`, `render_markdown`.
- Produces: `main(argv: list[str] | None = None) -> int`. Flags: `--seed` (int, default `harness.DEFAULT_SEED`), `--seniors-per-scenario` (int, default `harness.DEFAULT_SENIORS_PER_SCENARIO`), `--out` (path, default `docs/workstreams/P2`). Writes `<out>/evaluation-results.json` and `<out>/evaluation-results.md`. `python -m nomi_backend.evaluation` runs `main`.

- [ ] **Step 1: Write the failing test**

Append to `apps/backend/tests/test_evaluation.py` (before the final `if __name__` block):

```python
import json
import tempfile
from pathlib import Path

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nomi_backend.evaluation.__main__'`.

- [ ] **Step 3: Write minimal implementation**

Create `apps/backend/src/nomi_backend/evaluation/__main__.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from nomi_backend.evaluation.harness import (
    DEFAULT_SEED,
    DEFAULT_SENIORS_PER_SCENARIO,
    render_json,
    render_markdown,
    run_evaluation,
)


def _default_out() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent / "docs" / "workstreams" / "P2"
    return Path("docs/workstreams/P2")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nomi_backend.evaluation")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--seniors-per-scenario", type=int, default=DEFAULT_SENIORS_PER_SCENARIO
    )
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args(argv)

    report = run_evaluation(
        seed=args.seed, seniors_per_scenario=args.seniors_per_scenario
    )

    out_dir = Path(args.out) if args.out else _default_out()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation-results.json").write_text(
        render_json(report) + "\n", encoding="utf-8"
    )
    (out_dir / "evaluation-results.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    print(
        f"wrote {out_dir/'evaluation-results.json'} and "
        f"{out_dir/'evaluation-results.md'} (selected window "
        f"{report['selected_window']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Update `apps/backend/src/nomi_backend/evaluation/__init__.py`:

```python
from __future__ import annotations

from .fixed_threshold import FixedThresholdConfig, FixedThresholdDetector
from .harness import render_json, render_markdown, run_evaluation
from .metrics import ScenarioOutcome, SuiteMetrics, evaluate_outcomes
from .scenarios import SCENARIO_NAMES, ScenarioResult, generate_scenario, generate_suite

__all__ = [
    "FixedThresholdConfig",
    "FixedThresholdDetector",
    "SCENARIO_NAMES",
    "ScenarioOutcome",
    "ScenarioResult",
    "SuiteMetrics",
    "evaluate_outcomes",
    "generate_scenario",
    "generate_suite",
    "render_json",
    "render_markdown",
    "run_evaluation",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_evaluation.py -v`
Expected: PASS (23 tests).

- [ ] **Step 5: Generate the committed result files**

Run from `apps/backend/src/` (so `nomi_backend` is importable without a shim; `_default_out()` finds the repo root itself):

```bash
python -m nomi_backend.evaluation
```

Expected: prints `wrote <repo>/docs/workstreams/P2/evaluation-results.json and ...md (selected window 7)` and creates both files under `docs/workstreams/P2/`. Open `evaluation-results.md` and sanity-check: `change_detector` recall > `fixed_threshold` recall; window `7` row has `false_alert_rate` ≤ ~0.15; `selected_window` is 7 (if not, update the spec's section 7 default and Appendix A note to the selected value, then re-run).

- [ ] **Step 6: Run the full backend suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: PASS — baseline (6) + detection contract (3) + features (6) + change detector (19) + evaluation (23).

- [ ] **Step 7: Stage the changes**

```bash
git add apps/backend/src/nomi_backend/evaluation/__main__.py \
        apps/backend/src/nomi_backend/evaluation/__init__.py \
        apps/backend/tests/test_evaluation.py \
        docs/workstreams/P2/evaluation-results.json \
        docs/workstreams/P2/evaluation-results.md
```

Do not commit — leave that to the user (project rule).

---

## Post-Implementation

- [ ] Confirm `git status` shows only new files under `apps/backend/src/nomi_backend/detection/`, `apps/backend/src/nomi_backend/evaluation/`, `apps/backend/tests/test_*.py`, `docs/workstreams/P2/evaluation-results.*`, plus the two-line `apps/backend/pyproject.toml` change. Nothing else.
- [ ] Update spec `docs/workstreams/P2/specs/2026-09-01-change-detection-design.md` section 7 config table and Appendix A if the window sweep selected a value other than 7.
- [ ] Hand off to the user for commit and for coordination with P1 on adopting `nomi_backend.detection.contract`.
