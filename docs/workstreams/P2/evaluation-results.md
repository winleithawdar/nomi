# P2 Change Detection — Evaluation Results

> Prototype evaluation on synthetic data — not clinical validation.

- Seed: `20260901`
- Seniors per scenario: 30
- Selected rolling window: **7**

## Detector comparison

| detector | recall | precision | false_alert_rate | delay_median | delay_p90 |
|---|---|---|---|---|---|
| change_detector | 1.000 | 0.952 | 0.150 | 5.000 | 8.000 |
| fixed_threshold | 0.700 | 1.000 | 0.000 | 8.000 | 14.000 |

## Rolling-window sweep (change detector)

| window | recall | precision | false_alert_rate | delay_median | delay_p90 |
|---|---|---|---|---|---|
| 4 | 1.000 | 0.887 | 0.383 | 4.000 | 6.000 |
| 5 | 1.000 | 0.928 | 0.233 | 4.000 | 6.100 |
| 7 | 1.000 | 0.952 | 0.150 | 5.000 | 8.000 |
| 10 | 1.000 | 0.928 | 0.233 | 5.000 | 8.000 |
| 14 | 1.000 | 0.938 | 0.200 | 5.000 | 9.000 |

## Per-scenario (change detector)

| scenario | n | flagged | labelled change |
|---|---|---|---|
| stable | 30 | 3 | False |
| isolated_late_response | 30 | 6 | False |
| repeated_missed_checkins | 30 | 30 | True |
| sudden_cessation | 30 | 30 | True |
| gradual_latency_increase | 30 | 30 | True |
| gradual_frequency_decline | 30 | 30 | True |
| worsening_wellbeing | 30 | 30 | True |
| recovery_to_normal | 30 | 30 | True |
