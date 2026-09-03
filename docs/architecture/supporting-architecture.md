# Supporting Context & Architectural Additions (Nomi Baseline)

This document outlines the strategic, functional, and architectural context from the TechSeries proposal that must be added to the baseline documentation to guide the complete engineering implementation.

## 1. Core System Pipeline
The baseline layer is only the first step in a four-part operational pipeline. Documentation must reflect how the baseline feeds the subsequent stages:
* **LEARN:** Build a personal baseline from Nomi interactions such as response timing, latency, missed check-ins, interaction frequency, and self-reported wellbeing.
* **NOTICE:** Identify sudden anomalies and gradual shifts relative to the senior's own recent pattern.
* **VERIFY:** Check with the senior first to understand whether assistance is needed before alarming the caregiver.
* **SUPPORT:** If concern remains, notify the caregiver with relevant context so they can decide the next action.

## 2. Intelligence & Detection Mechanisms
The documentation must expand on how the baseline snapshots will be utilized by the "Notice" layer.
* **Isolation Forest:** Used to detect unusual combinations of signals, such as a late response occurring together with reduced interaction and missed check-ins.
* **Change-Point Detection:** Used to identify sustained, gradual shifts over time that may be too subtle to appear as a single sudden anomaly.
* **Individualised Detection:** Behaviour is strictly compared against the senior's own baseline rather than a population-wide definition of "normal".
* **Scope Boundary:** Nomi detects behavioural change, not illness.

## 3. Technology Stack & Infrastructure
The baseline documentation should explicitly state the approved technology stack for the MVP to ensure alignment across teams:
* **Messaging:** Telegram Bot API for the live proof of concept, with a
  provider abstraction that retains WhatsApp Cloud API support for future use.
* **Backend:** FastAPI + Python for feature extraction, detection, and escalation logic.
* **Database:** Supabase PostgreSQL for consent, interactions, derived features, and alert history.
* **Dashboard:** Next.js + TypeScript for a mobile-responsive caregiver dashboard.
* **Deployment:** Vercel + cloud backend to host dashboard and API services.

## 4. Progressive Verification & Escalation Rules
The system deliberately separates behavioural detection from caregiver escalation. The baseline docs must note this workflow constraint:
* An unusual pattern detected by the ML models does not immediately become a caregiver alert.
* The system first sends a gentle check-in to the senior through the configured messaging provider.
* Caregiver escalation only occurs if there is continued non-response, repeated anomalies, or concerning self-reported wellbeing.
* Alerts arrive through the configured messaging provider, with behavioural context and a simple next action.

## 5. Privacy Guardrails
To ensure the system adheres to the defined trust principles, the following constraints must be documented as architectural non-negotiables:
* **Explicit Opt-In:** Behavioural learning begins only after the senior provides consent.
* **Minimal Intrusion:** Nomi operates entirely without cameras, wearables, or continuous in-home surveillance.
* **Data Scope:** The system only analyses interactions directly between the senior and Nomi, ignoring unrelated conversations.

## 6. Target Personas
Development should be anchored to the defined primary and secondary users:
* **Primary Persona (Mdm Tan, 72):** An independent senior who uses a familiar messaging app, wants to age in place without being a burden, and is hesitant to constantly ask for help.
* **Secondary Persona (Sarah Tan, 36):** A caregiver daughter who lives 20 minutes away, wants peace of mind without constant manual checking, and needs clear context when an alert is raised.
