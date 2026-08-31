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

# P1 --- Anomaly Detection + Detection API

## Your ownership

Build Nomi's **sudden behavioural anomaly detection layer** on top of
the existing personal baseline.

## Deliverables

-   Inspect the existing baseline implementation and data model.
-   Prepare per-senior behavioural features from available signals:
    -   response latency
    -   missed check-ins
    -   interaction frequency
    -   self-reported wellbeing, where available
-   Implement Isolation Forest or the agreed anomaly-detection approach.
-   Detection must be **individual-specific**, using the senior's own
    history/baseline rather than population-wide medical thresholds.
-   Handle the cold-start / `learning` baseline state safely.
-   Produce an explainable detection result that the rest of Nomi can
    consume, including:
    -   whether the observation is unusual
    -   which behavioural signals contributed
    -   how the current observation differs from the senior's baseline
    -   timestamps / senior identifiers needed downstream
-   Expose the result through a clean service/API contract for P4 and
    the frontend.
-   Persist detection events only if this fits the existing
    architecture; coordinate schema changes first.
-   Add unit tests covering normal observations, obvious anomalies,
    insufficient history, missing optional signals, and malformed data.

## Important

Do not stop at `IsolationForest.predict()`. Your main output must be
useful and understandable to verification, escalation, and frontend
layers.

Do not build: - change-point detection (P2) - WhatsApp integration
(P3) - verification/escalation (P4) - frontend (P5)

## Coordinate with

-   **P2:** shared feature representation and combined detection output.
-   **P4:** exact detection payload needed by verification/escalation.
-   **P5:** explainable fields needed for the dashboard.

## Finish line

Given a senior with an established baseline and a new observation, Nomi
can determine whether it is unusually different from that senior's
normal pattern and return an explainable structured result.
