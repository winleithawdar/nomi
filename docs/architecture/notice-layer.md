# Notice Layer

The notice layer sits after the personal baseline. It describes whether the latest Nomi observations differ from this senior's own recent pattern.

## Scope

This layer:

- compares latest values with the senior's rolling baseline
- returns explainable findings in plain language
- uses `learning`, `usual`, `watching`, and `changed` as behavioural labels

This layer does not:

- diagnose medical conditions
- assign danger labels
- send WhatsApp verification or caregiver alerts
- use population-wide thresholds

## Status

- `learning`: the baseline is not established yet, so change detection waits
- `usual`: latest observations are in line with this senior's recent pattern
- `watching`: one signal is starting to differ from usual
- `changed`: a stronger or repeated difference from this senior's own baseline

## Signals

- Response latency: a later-than-usual reply against the personal rolling mean
- Missed check-ins: a latest miss, with a stronger label when misses are becoming frequent for this person
- Interaction frequency: fewer recent check-ins than this person's usual cadence
- Wellbeing: a lower self-reported score than this person's recent average, when enough scores exist

## Next layers

Verify (check with the senior first) and Support (caregiver notification with context) remain out of scope until this notice output is stable.
