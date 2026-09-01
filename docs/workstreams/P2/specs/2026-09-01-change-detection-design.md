# P2 — Longitudinal Change Detection + Evaluation — Design

- **Status:** approved for planning
- **Date:** 2026-09-01
- **Owner:** P2
- **Branch:** `feat/P2`
- **Brief:** [p2-change-detection-evaluation.md](../p2-change-detection-evaluation.md)
- **Implementation plan:** [../plans/2026-09-01-change-detection-implementation-plan.md](../plans/2026-09-01-change-detection-implementation-plan.md)

## 1. Purpose

Detect **gradual and sustained** shifts in a senior's behaviour relative to
*their own* established baseline — changes that never appear as a single
extreme anomaly and so are invisible to point-anomaly detection (P1).

P2 delivers two things:

1. A change-detection **library** producing an explainable, structured result.
2. A reproducible **evaluation harness** that quantifies the approach against a
   fixed-threshold baseline on synthetic senior scenarios.

Nomi does not diagnose, predict medical conditions, assign danger labels, or
emit a numeric risk score. P2 output is descriptive: what changed, in which
direction, by how much, since roughly when.

## 2. Scope

### In scope

- `nomi_backend.detection` package: shared result contract, feature extraction,
  the `ChangeDetector`.
- `nomi_backend.evaluation` package: synthetic scenario generators, a
  fixed-threshold comparison detector, metrics, and a runnable harness.
- Unit tests for all of the above, in the repository's `unittest` style.
- Committed evaluation results under `docs/workstreams/P2/`.

### Out of scope

- Point/sudden anomaly detection (P1).
- WhatsApp transport (P3), verification/escalation (P4), frontend (P5),
  deployment/integration wiring (P6).
- Any FastAPI route or `demo_repository` change.
- Database persistence or migrations.

### Blast radius

The **only** shared file modified is `apps/backend/pyproject.toml` — add
`numpy` and `scikit-learn` to `dependencies`. Every other file is new. P2 does
not touch `baseline/`, `api/app.py`, `services/demo_repository.py`, the
frontend, the root `README.md`, or `.gitignore`.

## 3. Foundation reused

The baseline layer (`nomi_backend.baseline`) already provides:

- `SeniorInteraction` — structured observation with derived
  `response_latency_minutes`.
- `BaselineCalculator.calculate(senior_id, interactions) -> SeniorBaseline` —
  per-signal rolling mean / median / stddev / latest deviation, plus
  `learning` / `stable` / `unavailable` status per signal.

P2 treats `SeniorBaseline` as the definition of "personal normal" and asks a
different question of the observation stream: *has the recent stretch drifted
away from that normal, and stayed there?*

## 4. Package layout (all new files)

```
apps/backend/src/nomi_backend/
├── detection/
│   ├── __init__.py        # public exports
│   ├── contract.py        # SHARED: DetectionResult, SignalContribution, enums
│   ├── features.py        # SeniorInteraction stream -> per-signal ordered series
│   └── changes.py         # ChangeDetector + ChangeDetectorConfig (Approach A)
└── evaluation/
    ├── __init__.py
    ├── scenarios.py       # deterministic seeded synthetic senior/scenario generators
    ├── fixed_threshold.py # naive population-threshold detector (comparison)
    ├── metrics.py         # recall, precision / false-alert rate, detection delay
    ├── harness.py         # run all scenarios x {ChangeDetector, FixedThreshold}
    └── __main__.py        # `python -m nomi_backend.evaluation` -> writes results

apps/backend/tests/
├── test_detection_contract.py
├── test_change_detector.py
└── test_evaluation.py

docs/workstreams/P2/
├── specs/
│   └── 2026-09-01-change-detection-design.md   # this document
├── plans/
│   └── 2026-09-01-change-detection-implementation-plan.md
├── evaluation-results.json                     # generated, committed
└── evaluation-results.md                       # generated, committed
```

## 5. Shared detection contract (`detection/contract.py`)

Frozen dataclasses matching the baseline layer's conventions: `from __future__
import annotations`, `str`-valued `Enum`s, `to_dict()` via `dataclasses.asdict`.

P2 emits `DetectionResult(kind=SUSTAINED_CHANGE, ...)`. P1, when built, emits
`kind=ANOMALY` from the same types. P4 consumes a list of `DetectionResult`.

```python
class DetectionKind(str, Enum):
    ANOMALY = "anomaly"                 # produced by P1
    SUSTAINED_CHANGE = "sustained_change"  # produced by P2

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
```

```python
@dataclass(frozen=True)
class SignalContribution:
    signal: str                       # "response_latency_minutes", ...
    status: DetectionStatus
    flagged: bool
    direction: ChangeDirection
    baseline_mean: float | None
    recent_mean: float | None
    deviation_pct: float | None       # (recent_mean - baseline_mean) / baseline_mean
    standardized_shift: float | None  # z, in baseline-stddev units
    methods_fired: list[str]          # subset of ["level_shift", "cusum", "trend"]
    estimated_onset: datetime | None
    recent_series: list[dict]         # [{"occurred_at": iso, "value": float}] for P5

@dataclass(frozen=True)
class DetectionResult:
    senior_id: str
    kind: DetectionKind
    detected: bool
    status: DetectionStatus
    as_of: datetime | None
    confidence: Confidence            # categorical, never a numeric risk score
    direction: ChangeDirection        # dominant direction across flagged signals
    contributions: list[SignalContribution]
    summary: str                      # plain-language, caregiver-safe
    metadata: dict

    def to_dict(self) -> dict: ...
```

`confidence` is derived from agreement, not magnitude:

- `LOW` — exactly one method fired on exactly one signal.
- `MODERATE` — multiple methods agree on one signal, or two signals each fire.
- `HIGH` — two or more signals flagged and at least one has multi-method agreement.

`summary` is templated per flagged signal, e.g.
*"Response latency has run about 40% above her usual since around Sep 3."*
No summary is produced for `status=insufficient_history`.

## 6. Feature extraction (`detection/features.py`)

Turns a `list[SeniorInteraction]` into an ordered per-signal series aligned with
how the baseline layer derives each signal:

| Signal | Series definition |
|---|---|
| `response_latency_minutes` | `interaction.response_latency_minutes` where both timestamps present |
| `missed_checkin_rate` | trailing mean of the `missed_checkin` 0/1 flag over the last `recent_window_points` outcomes (see [Appendix A](#appendix-a--rolling-window-size-costbenefit-analysis)) |
| `interaction_frequency` | count of interactions in the trailing `frequency_window_days` at each point |
| `wellbeing_score` | `interaction.wellbeing_score` where present |

Each series element carries its source `occurred_at`. Interactions are sorted by
`occurred_at` and filtered to `source == "nomi"` first, matching
`BaselineCalculator`.

> **Known duplication / coordination item:** the per-signal derivation rules are
> re-implemented here because `BaselineCalculator` exposes only aggregates, not
> the raw series. A later refactor should lift the shared derivation into the
> baseline layer and have both consumers call it. Tracked, not done in P2, to
> keep the blast radius minimal.

## 7. Change detector (`detection/changes.py`, Approach A)

### Inputs

```python
ChangeDetector(config: ChangeDetectorConfig | None = None)
    .detect(senior_id: str,
            interactions: list[SeniorInteraction],
            baseline: SeniorBaseline | None = None) -> DetectionResult
```

If `baseline` is not supplied it is computed via `BaselineCalculator()`.

### Per-signal procedure

For each of the four signals:

1. **Gate.** The signal contributes `status=INSUFFICIENT_HISTORY`,
   `flagged=False` when any of: its baseline status is not `stable`; the series
   has fewer than `reference_min_points + recent_min_points` points; the trailing
   window has fewer than `recent_min_points` points.
2. **Reference normal.** Computed from the stretch *before* the recent window —
   `pre = values[:max(len(values) - recent_window_points, reference_min_points)]`
   — as `ref_mean = mean(pre)`, `ref_std = pstdev(pre)`. This anchors "normal"
   on the senior's history *ahead of* the period under test, so a slow drift is
   not absorbed into its own reference (which the rolling `SeniorBaseline` would
   do). `ref_std` is floored at `min_rel_std * abs(ref_mean)` (a short,
   near-constant window otherwise gives an unrealistically tight sigma), at
   `_RATE_STD_FLOOR = 0.15` for `missed_checkin_rate`, and at `epsilon`.
3. **Recent window.** The trailing `recent_window_points` of the series.
4. **Level shift.** `z = (mean(recent) - ref_mean) / ref_std`. Fires when
   `abs(z) >= shift_z_threshold` and at least `min_sustained_points` of the
   recent window sit a full `ref_std` clear of `ref_mean` on one side (so a lone
   spike, which moves the mean but not `min_sustained_points` individual points,
   does not fire).
5. **CUSUM.** Standardised residuals `r_i = (x_i - ref_mean) / ref_std`, each
   clamped to `±cusum_clamp`. Two-sided tabular CUSUM with slack `cusum_k` and
   decision interval `cusum_h`. Fires when, at the final point, an accumulator is
   above `cusum_h` **and** its current run spans `>= min_sustained_points`
   observations; `estimated_onset` is the `occurred_at` of the index where that
   accumulator last reset to zero. The clamp plus the run-length guard make a
   single extreme point unable to fire CUSUM on its own, and a recovered
   excursion clears (the accumulator decays back below `cusum_h`).
6. **Trend.** Over the recent window (skipped when every value is equal):
   normalised slope from `numpy.polyfit(x, y, 1)` expressed in `ref_std` per
   observation, and the Mann-Kendall sign statistic. Fires when
   `abs(normalised_slope) >= trend_slope_threshold` and Mann-Kendall agrees on
   sign.

`direction` is `RISING` if the fired methods indicate an increase, `FALLING`
for a decrease. `deviation_pct` and `standardized_shift` are always populated
when a reference exists, regardless of firing, so P5 can show magnitude even
for sub-threshold drift.

### Aggregation

- `detected = any(contribution.flagged)`.
- `status = INSUFFICIENT_HISTORY` if the recent window was too short for every
  signal, else `OK`.
- `direction` = the direction of the flagged signal with the largest
  `abs(standardized_shift)`; `NONE` when nothing flagged.
- `confidence` per the rules in section 5.
- `summary` concatenates per-signal templated sentences for flagged signals.

### Configuration (`ChangeDetectorConfig`, frozen dataclass)

| Field | Default | Meaning |
|---|---|---|
| `reference_min_points` | 5 | min values in the pre-window to establish a reference |
| `recent_window_points` | 7 | size of the trailing window — rationale in [Appendix A](#appendix-a--rolling-window-size-costbenefit-analysis) |
| `recent_min_points` | 4 | min trailing values to attempt detection |
| `min_sustained_points` | 3 | recent points a full sigma clear of `ref_mean` for a level shift; also the CUSUM minimum run length |
| `shift_z_threshold` | 1.5 | standardised level-shift trigger |
| `min_rel_std` | 0.05 | `ref_std` floor as a fraction of `abs(ref_mean)` |
| `cusum_k` | 0.5 | CUSUM slack (in std units) |
| `cusum_h` | 4.0 | CUSUM decision interval |
| `cusum_clamp` | 4.0 | per-residual clamp (std units) so one spike cannot fire CUSUM |
| `trend_slope_threshold` | 0.4 | normalised slope trigger (std per observation) |
| `epsilon` | 1e-6 | absolute std floor to avoid divide-by-zero |

Defaults are a starting point; the evaluation harness (section 9) is the
mechanism for tuning them, and the chosen values are recorded in the results
file.

## 8. Error and edge handling

| Case | Behaviour |
|---|---|
| Baseline `learning` / signal `unavailable` | that signal → `INSUFFICIENT_HISTORY`, never flagged; other signals still evaluated |
| Recent window shorter than `recent_min_points` for all signals | whole result `INSUFFICIENT_HISTORY`, `detected=False` |
| Zero-variance reference (`ref_std == 0`) | `epsilon` floor; identical recent data → no fire |
| Optional signal absent (e.g. `wellbeing_score` always `None`) | signal skipped, not an error |
| Out-of-order interactions | sorted by `occurred_at` before anything else |
| `NaN` / non-finite / wrong-type values | filtered out, count recorded in `metadata["dropped_values"]`, never raises |
| Senior with only missed check-ins | latency signal skipped; `missed_checkin_rate` still evaluated |
| Empty interaction list | `INSUFFICIENT_HISTORY`, `as_of=None` |

## 9. Evaluation harness (`nomi_backend.evaluation`)

### Scenarios (`scenarios.py`)

Deterministic given a seed (`numpy.random.default_rng(seed)`). Each generator
returns `(interactions: list[SeniorInteraction], ground_truth)` where
`ground_truth` is `None` (no change) or
`{"signal": str, "onset_index": int, "kind": "sustained_change"}`.

| Scenario | Ground truth |
|---|---|
| `stable` | `None` |
| `isolated_late_response` | `None` (single spike is P1's job, not a sustained change) |
| `repeated_missed_checkins` | `missed_checkin_rate`, rising |
| `sudden_cessation` | `interaction_frequency`, falling |
| `gradual_latency_increase` | `response_latency_minutes`, rising |
| `gradual_frequency_decline` | `interaction_frequency`, falling |
| `worsening_wellbeing` | `wellbeing_score`, falling |
| `recovery_to_normal` | change then return; expected: flagged during the excursion, not after it clears |

Each scenario produces `seniors_per_scenario` synthetic seniors with
per-senior jitter so metrics are not computed on a single trace.

### Fixed-threshold detector (`fixed_threshold.py`)

A deliberately naive population-threshold detector emitting the same
`DetectionResult` shape — e.g. latency `> 45` min, missed rate `> 0.3`,
frequency `< 3` per week, wellbeing `< 3`. This is the comparison point that
demonstrates the value of personalisation.

### Metrics (`metrics.py`)

Computed over a scenario suite for each detector:

- **Detection recall** — fraction of changed scenarios flagged.
- **Precision** and **false-alert rate** — false flags on `stable` (and on
  `isolated_late_response`, which must *not* be read as a sustained change).
- **Detection delay** — observations between true `onset_index` and the first
  flag; reported as median and P90 over the changed scenarios that were caught.

Output carries a fixed banner: **"Prototype evaluation on synthetic data — not
clinical validation."**

### Window sweep

The runner also re-scores every scenario with `ChangeDetector` at
`recent_window_points ∈ {4, 5, 7, 10, 14}` (all other config held at default)
and reports recall, false-alert rate, and median detection delay per value.
The selected window — lowest median detection delay subject to false-alert rate
within target on `stable` and `isolated_late_response` — is recorded, and the
`ChangeDetectorConfig` default is revised if the sweep disagrees with the
Appendix A recommendation of 7.

### Runner (`harness.py` + `__main__.py`)

`python -m nomi_backend.evaluation [--seed N] [--out DIR]` runs every scenario
against both detectors and writes:

- `evaluation-results.json` — full metric payload, the window-sweep table, and
  the `ChangeDetectorConfig` used.
- `evaluation-results.md` — a comparison table (personalised vs fixed
  threshold), the window-sweep table, and the config, ready to drop into the
  demo deck.

Default `--out` is `docs/workstreams/P2/`.

## 10. Testing

`unittest`, mirroring `apps/backend/tests/test_baseline.py` (including the
`sys.path.insert` shim and a local `interaction(...)` factory).

### `test_detection_contract.py`

- `DetectionResult.to_dict()` / `SignalContribution` round-trip; nested
  dataclasses and enums serialise to primitives.
- Enum string values are the documented constants (guards the shared contract).

### `test_change_detector.py`

- Stable synthetic history → `detected=False`, `status=OK`.
- Injected sustained latency step → `detected=True`, latency contribution
  `flagged`, `direction=RISING`, `estimated_onset` within a tolerance of the
  injection point.
- Gradual latency ramp → `trend` in `methods_fired`.
- Gradual frequency decline → frequency contribution `flagged`,
  `direction=FALLING`.
- `learning` baseline / too-short history → `status=INSUFFICIENT_HISTORY`,
  `detected=False`.
- `wellbeing_score` always `None` → wellbeing contribution skipped, other
  signals unaffected.
- Shuffled input → identical result to sorted input.
- `NaN` / string injected into the series → filtered, `metadata["dropped_values"]`
  set, no exception.
- `recovery_to_normal` trace evaluated at the excursion peak → flagged; at the
  end (recovered) → not flagged.

### `test_evaluation.py`

- Every scenario generator is deterministic under a fixed seed (byte-identical
  interaction lists across two calls).
- Metric functions produce the correct numbers on a hand-built set of
  `(DetectionResult, ground_truth)` pairs.
- On the gradual scenarios, `ChangeDetector` recall exceeds the fixed-threshold
  detector's by a set margin (guards the core claim of the workstream).
- The window sweep runs over all five `recent_window_points` values and returns
  one metric row each; `n = 7` is within the documented target band for
  false-alert rate on `stable` and `isolated_late_response`.

## 11. Coordination notes

- **P1** — `detection/contract.py` is proposed as the shared result type. P1 to
  review and adopt (or negotiate changes) so `DetectionResult` covers both
  `ANOMALY` and `SUSTAINED_CHANGE`.
- **P1** — `detection/features.py` re-derives per-signal series; align on a
  single shared feature representation when P1 lands.
- **P4** — consumes `list[DetectionResult]`; `summary`, `direction`,
  `estimated_onset`, and `contributions[*].deviation_pct` are the fields
  intended for caregiver-facing context.
- **P5** — `contributions[*].recent_series` and `baseline_mean` are provided for
  charting; `confidence` is categorical by design.
- **P6** — evaluation scenarios are the seed for a technically consistent demo
  dataset.
- **Team** — `pyproject.toml` gains `numpy` and `scikit-learn`; no other shared
  file changes.

## 12. Open questions

- Exact default thresholds in `ChangeDetectorConfig` — to be settled by the
  evaluation harness output, not guessed now.
- Rolling-window size (`recent_window_points`) — analysed in
  [Appendix A](#appendix-a--rolling-window-size-costbenefit-analysis); the
  recommended default is **7**, and the harness sweeps `{4, 5, 7, 10, 14}` to
  confirm or revise it.
- Whether `scikit-learn` is used at all in P2 (currently only `numpy` is
  required by the design). It is added to dependencies now because it is
  already installed and P1 will need it; P2 will use it only if a concrete need
  appears during implementation.

## Appendix A — Rolling-window size: cost–benefit analysis

### A.1 What "the rolling window" is

`recent_window_points` is the trailing slice of each per-signal series that
feeds three things: the **level-shift** test (mean of the window vs the
reference), the **trend** test (slope over the window), and the magnitude
fields P5 renders (`recent_mean`, `deviation_pct`, `standardized_shift`).

**CUSUM is deliberately not windowed** — it accumulates standardised residuals
from the reference forward and resets on its own. So window size tunes two of
the three detection methods; the drift-onset method is unaffected. That limits
the downside of getting the window slightly wrong.

The same length is also used for the `missed_checkin_rate` series (a trailing
mean over the last `recent_window_points` check-in outcomes).

### A.2 Forces in tension

| Force | Smaller window | Larger window |
|---|---|---|
| **Detection delay** — observations from true onset to first flag | Lower: window fills with post-change points fast | Higher: window stays mixed pre/post change for longer |
| **False-alert rate** — spurious flags on `stable` / one-off spikes | Higher: recent mean is noisy, a single late reply moves it | Lower: transients diluted |
| **Level-shift sensitivity** | Sharper once the window clears the change | Smeared while the window straddles the change |
| **Trend sensitivity** | Weak: short lever arm, slope dominated by noise | Strong: more points, clearer slope |
| **Cold-start coverage** — how soon a senior can be evaluated at all | Broad: needs few points | Narrow: many seniors sit in `insufficient_history` |
| **Recovery clearing lag** — flags persisting after a senior returns to normal | Clears in a few observations | Keeps "remembering" the excursion |
| **Onset localisation** (`estimated_onset`) | Fuzzy from the level-shift path (CUSUM still precise) | Fuzzier still from the level-shift path |

### A.3 Numbers for this context

- **Cadence.** Demo interactions land every ~1–3 days, so `n = 7` covers
  roughly 1–3 weeks of real time — long enough to read as a *sustained* change
  in plain language ("elevated for about a week"), short enough to still be
  actionable. This is a phrasing/utility choice, not a medical threshold.
- **Diminishing statistical power.** The standard error of the recent mean is
  `σ/√n`. Going 4 → 7 cuts it by ~24%; 7 → 10 by a further ~16%; 10 → 14 by
  ~15% more — but by `n = 10–14` the window routinely straddles the change
  point for a level shift, so the extra precision is spent estimating a
  smeared mean. Useful power gains flatten around `n ≈ 7`.
- **Coverage.** First evaluation needs about `reference_min_points` +
  `recent_min_points` observations. At `recent_min_points = 4` that is ~9
  observations; a 10-point window with `recent_min_points = 6` pushes it to
  ~11+. MVP seniors have 3–15 observations, so this difference decides whether
  the demo shows a result at all for the mid-history seniors.
- **Recovery.** The `recovery_to_normal` scenario expects a flag during the
  excursion and none after it clears. A 14-point window keeps ≥ half its mass
  on the excursion for ~7 observations post-recovery — a visible false-positive
  tail. `n = 7` clears in ~4 observations.

### A.4 Options

| Option | Benefit | Cost | Verdict |
|---|---|---|---|
| **Small — `n = 4–5`** | Fastest detection; widest cold-start coverage; snappy recovery | Highest false-alert rate; trend test barely works; noisy magnitude fields for P5 | Rejected — false alarms erode caregiver trust, which the brief weights heavily |
| **Medium — `n = 7`** | Balanced delay vs false-alert rate; trend test has enough points; near-peak statistical power; acceptable coverage; recovery clears in ~4 obs | Slightly slower than a tiny window; still modest power on very subtle drift (CUSUM covers this) | **Recommended** |
| **Large — `n = 10–14`** | Lowest false-alert rate; strongest trend signal | Detection delay grows; worst cold-start coverage; lingering flags after recovery; level-shift mean smeared across the change | Rejected for the MVP — too slow and too many seniors never get evaluated |
| **Time-based — "last N days"** | Adapts to irregular cadence; intuitive to explain | Non-deterministic point count breaks reproducible evaluation; empty/underfilled windows during quiet spells; more code | Rejected now; revisit for production, where cadence varies more than in the demo |

### A.5 Recommendation

- `recent_window_points = 7`, `recent_min_points = 4`, `min_sustained_points = 3`.
- **Count-based, not time-based**, so the evaluation harness is reproducible.
  Keep `recent_window_points` in `ChangeDetectorConfig` so production can retune
  per real cadence.
- The `missed_checkin_rate` series uses the same 7-outcome trailing window (this
  resolves the open detail noted in section 6). A rate over 7 binary outcomes is
  already smoothed; a separate day-based sub-window adds coupling for no
  measurable benefit at MVP cadence.
- Treat `n = 7` as a **calibrated prior, not a final answer**: the harness
  sweeps `recent_window_points ∈ {4, 5, 7, 10, 14}` across every scenario and
  records recall, false-alert rate, and median detection delay per value. The
  winner — lowest median detection delay subject to false-alert rate within
  target on `stable` and `isolated_late_response` — is written into
  `evaluation-results.md`. If the sweep contradicts `n = 7`, the config default
  changes and this appendix is annotated with the measured result.

### A.6 Answer

**`n = 7` is the best choice for this case.** It is the only option that keeps
detection delay useful, holds the false-alert rate down enough to protect
caregiver trust, gives the trend test enough points to function, and still lets
the mid-history demo seniors be evaluated at all. The evaluation harness exists
to prove or correct this before the number is locked.
