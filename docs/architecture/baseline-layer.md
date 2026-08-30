## Baseline Layer

### Current repository state

The repository started as a minimal [README.md](/Users/winleithawdar/Desktop/nomi/README.md). The baseline layer is the first backend module and now lives under [apps/backend](/Users/winleithawdar/Desktop/nomi/apps/backend).

### Scope

This baseline layer is intentionally limited to:

- storing structured senior interaction observations collected directly by Nomi
- calculating recent, individual-specific baseline statistics
- marking a senior as `learning` until enough recent history exists
- returning explainable outputs that can later feed anomaly detection

This layer does not:

- diagnose medical conditions
- assign danger labels
- use population-wide thresholds
- integrate WhatsApp or caregiver escalation logic

### Implementation plan

1. Create a small Python backend package dedicated to baseline calculations.
2. Model Nomi interaction observations as structured records with timestamps and optional wellbeing.
3. Compute rolling statistics per senior from recent history only.
4. Keep per-signal readiness separate from overall baseline status so optional signals like wellbeing can remain sparse.
5. Add a database migration for raw interaction storage and optional baseline snapshots.
6. Cover cold start, sparse data, and rolling-window behavior with synthetic-data tests.

### Suggested database tables

#### `senior_interactions`

Stores only structured data collected directly through Nomi.

- `id uuid primary key`
- `senior_id uuid not null`
- `checkin_id uuid null`
- `occurred_at timestamptz not null`
- `interaction_type text not null`
- `checkin_sent_at timestamptz null`
- `response_received_at timestamptz null`
- `response_latency_minutes double precision null`
- `missed_checkin boolean not null default false`
- `wellbeing_score double precision null`
- `source text not null default 'nomi'`
- `created_at timestamptz not null default now()`

Notes:

- Keep message bodies and free-text content out of this table for privacy.
- `response_latency_minutes` is derived but useful for querying and testing.
- `source` protects the MVP rule that only Nomi-collected interactions are analyzed.

#### `senior_baseline_snapshots`

Optional persisted snapshot of the most recent baseline.

- `id uuid primary key`
- `senior_id uuid not null`
- `calculated_at timestamptz not null default now()`
- `latest_interaction_at timestamptz not null`
- `status text not null`
- `min_observations_for_stable integer not null`
- `total_interactions integer not null`
- `numeric_window_size integer not null`
- `binary_window_size integer not null`
- `frequency_window_days integer not null`
- `baseline_payload jsonb not null`

Notes:

- `baseline_payload` stores flexible signal stats without overfitting the schema too early.
- Future anomaly or change-point layers can read from snapshots or recalculate on demand.

### Baseline calculation logic

All calculations are per senior and based on recent observations only.

#### Core status

- A senior is `learning` until at least `min_observations_for_stable` interactions exist.
- Incoming observations are always stored, even during learning.
- Optional signals can stay `learning` independently if they have too few values.

#### `response_latency_minutes`

Derived when both `checkin_sent_at` and `response_received_at` exist.

For the most recent `N` latency observations, calculate:

- rolling mean
- rolling median
- rolling standard deviation
- recent observation count
- latest value
- latest deviation from rolling mean

#### `missed_checkin`

For the most recent `N` check-in outcomes, calculate:

- recent missed rate
- recent outcome count
- recent missed count
- latest outcome

#### `interaction_frequency`

For each interaction, derive a feature equal to:

- number of interactions in the trailing `frequency_window_days`

Then, over the most recent derived frequency values, calculate:

- rolling mean
- rolling median
- rolling standard deviation
- recent observation count
- latest value
- latest deviation from rolling mean

This preserves the principle of "personal normal, not population normal" because frequency is based on each senior's own recent cadence.

#### `wellbeing_score`

If present, use the most recent `N` wellbeing values to calculate:

- rolling mean
- rolling median
- rolling standard deviation
- recent observation count
- latest value
- latest deviation from rolling mean

No population-wide interpretation is attached to the score.

### Edge cases

- No history: return `learning` with empty signal stats.
- Very small history: standard deviation should be `0.0` instead of erroring.
- All missed check-ins: latency stats remain unavailable while missed rate still works.
- Sparse wellbeing: overall baseline can stabilize while wellbeing remains `learning`.
- Out-of-order inserts: sort by interaction time before calculating.
- Duplicate timestamps: keep deterministic ordering and still count each interaction.
- Future anomaly support: baseline outputs stay descriptive, not judgmental.
