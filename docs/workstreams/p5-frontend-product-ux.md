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

# P5 --- Frontend + Product / Demo UX

## Your ownership

Own the complete **judge-facing caregiver experience**. The frontend
must make Nomi's core idea understandable within seconds.

## Deliverables

Build/polish the existing frontend rather than starting over.

### Caregiver overview

-   senior overview/list
-   baseline learning/established state
-   recent check-in/activity information
-   meaningful current statuses without medical/risk claims

### Senior detail

Clearly visualise: - personal baseline - typical response behaviour -
recent observations/check-ins - behavioural trend over time - detected
change relative to the senior's own normal - what Nomi noticed and why

### Verification / alerts

-   verification status where relevant
-   contextual caregiver alerts
-   alert/history view
-   clear explanation of what changed and suggested next action

### Demo UX

The demo must make this story visually obvious:

**Normal pattern → meaningful deviation → Nomi notices → verifies →
caregiver becomes aware**

Use: - Next.js - TypeScript - Tailwind - shadcn/ui - existing project
design conventions

Keep the interface calm, trustworthy, polished, responsive, and easy to
scan.

Avoid: - medical dashboards - generic health/risk scores - raw ML
numbers without explanation - dense analytics - excessive decorative UI

### Integration

-   Use typed API clients/interfaces.
-   Integrate P1/P2 detection outputs and P4 alert/history APIs.
-   Include loading, empty, error, and learning states.
-   Do not invent backend fields if a contract exists.
-   Add basic frontend tests where practical.

## Coordinate with

-   **P1/P2:** explainable detection fields.
-   **P4:** verification/alert APIs.
-   **P6:** seeded demo scenario and deployed endpoints.

## Finish line

A judge can look at the dashboard and immediately understand what is
normal for the senior, what changed, what Nomi did, and whether the
caregiver needs to act.
