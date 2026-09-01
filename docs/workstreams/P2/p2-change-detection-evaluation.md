# Nomi Project Context

Nomi is an AI-powered senior-care support application for seniors ageing
independently at home and their family/informal caregivers.

## Core problem

The gap is not only emergency response. There can be a period before
anyone knows that help may be needed. Subtle changes such as slower
responses, repeated missed check-ins, reduced interaction, or worsening
self-reported wellbeing may become meaningful when they differ from that
senior's own normal behaviour.

## Core principle

**Personal normal, not population normal.**

Nomi does **not** diagnose illness, predict medical conditions, or
determine emergencies.

## Core flow

**LEARN → NOTICE → VERIFY → SUPPORT**

1.  LEARN: build a personal behavioural baseline from Nomi interactions.
2.  NOTICE: detect sudden anomalies and gradual/sustained changes
    relative to that senior's baseline.
3.  VERIFY: check with the senior first instead of immediately alarming
    the caregiver.
4.  SUPPORT: if concern remains, notify the caregiver with useful
    context.

## Existing foundation

-   Personal baseline backend: already implemented.
-   Baseline frontend foundation: already implemented.
-   Frontend: Next.js + TypeScript + Tailwind CSS + shadcn/ui.
-   Backend: FastAPI + Python.
-   Database: Supabase PostgreSQL.
-   Messaging target: official WhatsApp Business Platform / Cloud API.
-   Detection direction: Isolation Forest + change-point detection.

## Team engineering rules

-   Inspect the existing repository before coding.
-   Reuse existing baseline logic, schemas, conventions, and API
    patterns.
-   Do not rewrite working code unnecessarily.
-   Keep modules loosely coupled.
-   Never hard-code credentials or secrets.
-   Coordinate API/schema changes with the team before making breaking
    changes.
-   Add tests for your own work.
-   Keep commits scoped and descriptive.
-   Do not add medical diagnosis, clinical prediction, emergency
    certainty, or a generic numeric risk/concern score.
-   Do not expand into future features such as
    multilingual/voice/community-care integrations unless required for
    the MVP.
-   When finished, document: files changed, API/schema changes,
    environment variables, assumptions, tests, and integration
    instructions.

# P2 --- Longitudinal Change Detection + Evaluation

## Your ownership

Build Nomi's **gradual/sustained behavioural change detection** and
evaluate the overall detection approach.

## Deliverables

### Change detection

-   Inspect the existing baseline and coordinate feature format with P1.
-   Implement an appropriate change-point / longitudinal
    change-detection method.
-   Detect sustained shifts that may not appear as one extreme anomaly.
-   Keep detection individual-specific.
-   Handle insufficient history safely.
-   Produce a structured, explainable output compatible with P1's
    anomaly output.

### Synthetic evaluation

Create reproducible synthetic senior profiles with different normal
routines. Include scenarios such as: - stable normal behaviour -
isolated late response - repeated missed check-ins - sudden cessation of
interaction - gradual increase in response latency - gradual reduction
in interaction frequency - worsening self-reported wellbeing where
supported - recovery back toward normal

### Evaluation

Evaluate the combined detection approach using suitable prototype
metrics: - detection recall - precision / false-alert rate - time or
delay to detection - other clearly justified metrics if useful

Where practical, compare Nomi against a simple fixed-threshold baseline
to demonstrate the value of personalisation.

Clearly label synthetic evaluation as **prototype evaluation, not
clinical validation**.

-   Add tests.
-   Save evaluation scripts/results in a reproducible form the team can
    use in the demo/presentation.

## Do not build

-   WhatsApp
-   verification/escalation
-   frontend

## Coordinate with

-   **P1:** common feature/output contract and combined detection logic.
-   **P6:** reproducible demo scenario and end-to-end test data.
-   **P5:** provide clean data that can be visualised.

## Finish line

Nomi can demonstrate both sudden anomaly detection and sustained
behavioural change using reproducible senior scenarios, with
quantitative prototype evaluation.
