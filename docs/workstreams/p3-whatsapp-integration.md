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

# P3 --- WhatsApp Integration + Check-In Pipeline

## Your ownership

Connect Nomi to the **official WhatsApp Business Platform / Cloud API**
and own the messaging plumbing.

## Deliverables

-   Inspect existing FastAPI/database code first.
-   Implement Meta webhook verification.
-   Implement inbound WhatsApp message webhook handling.
-   Implement outbound text messaging.
-   Map WhatsApp sender identifiers/phone numbers to Nomi seniors.
-   Store relevant Nomi interactions/check-ins with timestamps and
    message IDs.
-   Make webhook processing idempotent so duplicate Meta events do not
    create duplicate interactions.
-   Connect check-in responses to the existing baseline pipeline so
    response latency and other relevant observations can be generated.
-   Implement the basic check-in messaging path required by the MVP.
-   Keep Meta-specific code behind a messaging/provider/service
    abstraction so core Nomi logic is not coupled to WhatsApp.
-   Use environment variables for all credentials and update
    `.env.example` with placeholders only.
-   Add tests with external Meta calls mocked.
-   Document the exact external Meta setup required for the team.

## MVP target

Prove this real round trip:

**Nomi/FastAPI → actual WhatsApp → senior reply → Meta webhook → FastAPI
→ interaction stored / baseline updated**

P4 will own the verification and escalation decision logic, but provide
the messaging functions P4 needs to send verification messages and
caregiver alerts.

## Important

-   Use the official API only.
-   Do not use WhatsApp Web scraping or unofficial personal-account
    automation.
-   Do not hard-code tokens, phone numbers, app secrets, or IDs.
-   If Meta blocks production-style functionality, preserve a clean mock
    provider/fallback so the whole MVP remains demonstrable.

## Coordinate with

-   **P4:** message types/functions required for verification and
    caregiver alerts.
-   **P6:** deployment/public webhook URL and environment configuration.

## Finish line

The deployed backend can reliably send and receive real WhatsApp
messages and turn senior responses into Nomi interaction data.
