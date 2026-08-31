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

# P4 --- Verification + Escalation + Caregiver Alert Engine

## Your ownership

Build the decision layer between **detection** and **caregiver action**.

Nomi deliberately separates behavioural detection from escalation: **ML
detects unusual behaviour; senior verification and explicit rules
determine whether caregiver attention is appropriate.**

## Deliverables

-   Consume structured detection results from P1/P2.
-   Implement a clear verification state/workflow.
-   When a meaningful change is detected, trigger a senior-first
    verification request through P3's messaging service.
-   Handle verification outcomes such as:
    -   reassuring response / all good
    -   senior indicates help may be needed
    -   no response
    -   unresolved/repeated behavioural change
-   Implement deterministic, explainable escalation rules.
-   Do not escalate every anomaly automatically.
-   Generate a contextual caregiver alert containing:
    -   what changed relative to the senior's normal
    -   relevant recent context
    -   verification outcome
    -   a simple suggested next action
-   Do not make medical conclusions.
-   Persist verification/escalation/alert history where appropriate.
-   Provide clean API endpoints/data contracts for P5's frontend.
-   Add unit tests for each branch of the workflow.

## Example conceptual flow

Detection → Verify senior → Reassuring response? resolve/continue
learning → Concern remains? create contextual caregiver alert → P3 sends
it.

## Do not build

-   anomaly/change detection itself
-   WhatsApp transport internals
-   frontend

## Coordinate with

-   **P1/P2:** detection payload.
-   **P3:** messaging methods.
-   **P5:** alert/history/status API contract.

## Finish line

A detection event can move through senior-first verification and either
resolve safely or produce an explainable caregiver alert.
