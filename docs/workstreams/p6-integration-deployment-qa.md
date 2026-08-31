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

# P6 --- Integration + Deployment + End-to-End QA

## Your ownership

Make the six workstreams operate as **one reliable MVP**.

Do not build a large isolated feature unless needed to unblock
integration.

## Deliverables

### Integration

-   Understand the existing baseline architecture.
-   Track API contracts and database/schema changes across P1-P5.
-   Resolve integration mismatches early.
-   Connect: WhatsApp → interactions → baseline → detection →
    verification → escalation → caregiver alert → frontend.
-   Keep environment configuration consistent.

### Deployment

-   Ensure FastAPI is publicly available over HTTPS for Meta webhooks.
-   Ensure the Next.js frontend is deployed and points to the correct
    backend.
-   Configure required environment variables securely.
-   Resolve CORS/network/deployment issues.
-   Ensure migrations and seed data work in the deployed environment.

### Demo data

Prepare a deterministic demo senior/caregiver scenario that shows: 1.
established normal behaviour 2. meaningful behavioural change 3.
detection 4. senior verification 5. unresolved concern 6. caregiver
alert 7. dashboard explanation

Coordinate with P2 so synthetic/demo data is technically consistent with
the detection pipeline.

### QA

Test at minimum: - normal response - late but non-escalated response -
isolated anomaly - repeated/sustained change - missed response -
reassuring verification - unresolved verification → escalation -
duplicate webhook - API failure/loading/error states - deployed
end-to-end flow

Maintain a concise bug/blocker list and route issues to the relevant
owner.

### Demo resilience

Prepare a fallback if a live dependency fails: - deterministic seeded
scenario - backup screenshots/video if needed - mock messaging provider
if WhatsApp becomes unavailable

## Coordinate with

Everyone. You are the integration point, not the owner of everybody
else's implementation.

## Finish line

The deployed Nomi MVP can complete the full end-to-end scenario reliably
and repeatedly, with a backup path ready for the live presentation.
