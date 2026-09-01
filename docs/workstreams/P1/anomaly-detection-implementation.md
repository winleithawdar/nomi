# P1 Anomaly Detection Implementation

## Scope

P1 adds sudden, individual-specific behavioural anomaly detection. It reuses
the P2 shared detection contract and feature extraction package, but does not
modify P2 sustained-change logic, persistence, messaging, verification, or the
frontend.

## Detection approach

`AnomalyDetector` treats the newest Nomi interaction as the observation to
score and trains an Isolation Forest only on earlier interactions for that
senior. This prevents the observation from influencing its own baseline or
training data.

The detector uses available causal features for response latency, trailing
missed-check-in rate, trailing interaction frequency, and optional wellbeing.
It requires at least one stable, varying signal and 20 complete historical
feature vectors. This allows a clearly unusual late reply to be noticed even
when the other available signals have not varied yet; categorical confidence
remains low unless multiple signals contribute. Missing optional signals are
excluded instead of being imputed as zero. Interaction-frequency warm-up values
are excluded until its seven-day window is meaningful.

Isolation Forest scores are calibrated against the senior's own training-score
distribution. Because an Isolation Forest can place any value beyond a learned
terminal range in the same leaf, P1 also applies a robust per-senior deviation
guard for extreme departures from a stable signal. This is a quality safeguard,
not a population threshold, and it is surfaced as a named detection method.
The API does not expose the raw score or a generic risk score.
An Isolation Forest score also needs personal evidence: one signal must differ
by at least 2.5 robust standard deviations, or two signals must each differ by
at least 1.5. This prevents an isolated model score from turning ordinary
personal variation into a false alert.
For every active signal, explanations compare the latest value with the
senior's historical mean/median and use counterfactual replacement to identify
signals whose return to usual behaviour reduces anomaly evidence.
Signals with no historical variation are not sent into the forest, but remain
eligible for the personal-deviation guard. This lets P1 explain a first unusual
missed check-in without diluting the multivariate model with a constant column.

## API

`GET /api/v1/seniors/{senior_id}/detections/anomaly` returns the latest
computed `DetectionResult` for the existing demo interaction stream. It is
read-only and does not persist detection events. A production interaction
pipeline can call `AnomalyDetector.detect(senior_id, history_with_observation)`
immediately after storing a new Nomi interaction.

The endpoint returns `404` for an unknown senior. A known senior without
sufficient individual history returns `kind="anomaly"` and
`status="insufficient_history"`, never a detection.

## Files Changed

- `apps/backend/src/nomi_backend/detection/anomalies.py`
- `apps/backend/src/nomi_backend/detection/__init__.py`
- `apps/backend/src/nomi_backend/services/demo_repository.py`
- `apps/backend/src/nomi_backend/api/app.py`
- `apps/backend/tests/test_anomaly_detector.py`

## Schema and Environment Changes

No database schema, migration, persistence, or environment-variable changes.
`scikit-learn` was already declared by P2 in `apps/backend/pyproject.toml`.

## Assumptions and Integration

- Only `source="nomi"` interactions are eligible.
- `confidence` indicates agreement among contributing signals, not medical
  severity or a risk score.
- P4 should consume the structured result and apply senior-first verification;
  P1 never escalates directly.
- P5 can use `contributions`, `summary`, and `recent_series` without relying on
  raw model scores.

## Tests

`apps/backend/tests/test_anomaly_detector.py` covers normal observations,
obvious anomalies, insufficient history, absent wellbeing, malformed optional
data, training-history isolation, duplicate timestamps, and non-Nomi filtering.

## Prototype Evaluation

`nomi_backend.evaluation.anomaly_harness` evaluates the hybrid detector against
Isolation Forest without the personal-deviation guard. It uses deterministic
synthetic personal routines and point anomalies: a late response, a missed
check-in, a wellbeing drop, a combined anomaly, and a late response when
wellbeing is unavailable.

The harness reports recall, precision, false-alert rate, and zero-delay point
detection. It also sweeps the personal-deviation guard threshold. The seeded
four-senior test run achieved 1.000 recall and 0.000 false-alert rate for the
hybrid detector, compared with 0.500 recall for Isolation Forest alone. This is
prototype evidence on synthetic data only, not clinical validation or final
production calibration. The sweep is diagnostic only; it does not automatically
change the configured `3.5` guard threshold.
