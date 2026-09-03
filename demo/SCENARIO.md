# Nomi MVP Demo Scenario

**Persona pair (proposal MVP):** one senior ↔ one caregiver consent relationship  
**Primary senior:** Mdm Tan (`senior-1`), Late 70s — independent, WhatsApp-comfortable  
**Primary caregiver:** Sarah Tan (daughter / “Demo Caregiver”) — lives ~20 minutes away  

**Story judges should leave with:**

> Nomi learned what is normal for Mdm Tan, noticed when her pattern changed,
> checked with her first, and only then told Sarah — with clear context, not a diagnosis.

---

## Scenario title

**“Mdm Tan’s quieter week”** — gradual withdrawal that looks like “just a busy week”
until it differs from *her* normal.

---

## Cast and consent

| Role | ID / name | Notes |
|---|---|---|
| Senior | `senior-1` — Mdm Tan | Consented to Nomi behavioural learning |
| Caregiver | `caregiver-demo` — Demo Caregiver (Sarah) | Linked as daughter; active consent |
| Channel | WhatsApp (or mock provider) | Check-ins, verification, caregiver alerts |
| Dashboard | Caregiver UI | Baseline, detections, verification, alerts |

Privacy boundaries (state verbally):

- Only interactions between Mdm Tan and Nomi are analysed
- No cameras, wearables, or continuous home surveillance
- No medical diagnosis, emergency certainty, or generic risk score

---

## Timeline (what happens)

### Act 1 — LEARN (Personal Behaviour Model)

**Days 1–25 of demo history**

Mdm Tan replies to her daily Nomi check-in roughly within **20–30 minutes**.
Wellbeing scores are mostly steady (about 3–4). Missed check-ins are rare.

**What to show on the dashboard**

- Senior list: Mdm Tan’s baseline is **established** (not still learning)
- Senior detail: response latency series looks stable
- Explain: Nomi compares her to **herself**, not to “all seniors”

**Signals in play**

- Response latency
- Missed check-ins
- Interaction frequency
- Self-reported wellbeing
- Baseline deviation

**Proposal feature covered:** Personal Behaviour Model (rolling personal baseline)

---

### Act 2 — NOTICE (Anomaly + Change Detection)

**Demo inflection point (seeded unusual day)**

On a later day, Mdm Tan takes about **3 hours** to reply, and her wellbeing score dips.
Individually, one late reply might be nothing. Together with her usual pattern, Nomi flags it.

**What Nomi does (backend)**

1. Isolation Forest / anomaly path: unusual combination relative to her baseline  
   → `GET /api/v1/seniors/senior-1/detections/anomaly`
2. Change-point / longitudinal path: sustained shift if the slower pattern continues  
   → `GET /api/v1/seniors/senior-1/detections/change`

**What to say**

> “Nomi noticed a meaningful change from Mdm Tan’s own recent normal —
> not that she is sick, and not that this is an emergency.”

**Proposal features covered:** Isolation Forest + change-point detection; individualised detection

---

### Act 3 — VERIFY (Progressive Verification)

Nomi does **not** immediately alarm Sarah.

Instead it sends a gentle senior-first WhatsApp check-in, for example:

> “Hi Mdm Tan, We noticed something a little different in your recent check-in pattern.
> Just checking in — is everything okay on your end? A quick reply would be lovely.”

**Branch A — Reassuring (show once to prove we don’t over-alert)**

- Mdm Tan replies she’s fine / busy with family
- Verification resolves as `resolved_reassuring`
- **No caregiver alert**
- Run: `python scripts/run_demo_scenario.py --outcome reassuring`

**Branch B — Help needed (optional)**

- Mdm Tan indicates she could use a call / visit
- Escalation creates a contextual caregiver alert
- Run: `python scripts/run_demo_scenario.py --outcome help-needed`

**Branch C — No response (primary demo climax)**

- Mdm Tan does not reply within the verification window
- Deterministic rules escalate (not “every anomaly auto-alerts”)
- Run: `python scripts/run_demo_scenario.py --outcome no-response`

**Proposal feature covered:** Progressive Verification (senior check-in → reassess → escalate only if concern remains)

---

### Act 4 — SUPPORT (Contextual Caregiver Alert)

Sarah receives a WhatsApp-style alert (live provider or mock) **and** sees it on the dashboard.

Alert content includes:

| Field | Example intent |
|---|---|
| **What changed** | Response times slower than her usual baseline |
| **Context** | Recent observations vs personal pattern; sudden and/or sustained flag |
| **Verification outcome** | No response / help needed / repeated change |
| **Suggested action** | e.g. “Consider a phone call or visit when convenient.” |

**What to say**

> “Sarah gets context she can act on — not a medical claim, not a mystery risk number.”

**Proposal features covered:** Contextual Caregiver Alerts + optional dashboard explanation

---

## End-to-end pipeline (technical)

```text
WhatsApp check-in / reply
  → Feature extraction + SeniorInteraction
  → Personal baseline (LEARN)
  → Anomaly + change detection (NOTICE)
  → Senior-first verification (VERIFY)
  → Rule-based escalation
  → Contextual caregiver alert + dashboard (SUPPORT)
```

| Workstream | Responsibility in this scenario |
|---|---|
| Baseline (Winnie) | Personal normal |
| P1 | Sudden anomaly |
| P2 | Sustained / gradual change |
| P3 | WhatsApp send/receive / webhook |
| P4 | Verification + escalation + alert copy |
| P5 | Caregiver dashboard |
| P6 | Wiring, seed data, deployment |

---

## How to run this scenario live

### Option 1 — Fastest (recommended for presentation)

1. Start backend + frontend (see [`README.md`](./README.md)).
2. Open dashboard → **Mdm Tan**.
3. In a terminal:

```bash
python scripts/run_demo_scenario.py --outcome no-response
```

4. Refresh dashboard → show verification result + caregiver alert.
5. Optionally re-run with `--outcome reassuring` to show false-alarm reduction.

### Option 2 — Full messaging pipeline (if WhatsApp / DB configured)

```bash
python scripts/run_persistent_pipeline_demo.py
```

Covers contacts, persisted check-in, signed webhook reply, detection, verification, alert.

### Option 3 — Manual API walkthrough

1. `GET /api/v1/seniors/senior-1` — baseline established  
2. `GET /api/v1/seniors/senior-1/detections/anomaly` — change noticed  
3. `POST /api/v1/verifications` with that detection payload — verify first  
4. `POST .../no-response` or `.../response` — escalate or resolve  
5. `GET /api/v1/alerts` — caregiver support context  

---

## Talking points (pitch Q&A)

**“Isn’t this just an emergency button?”**  
No. Nomi is an early-awareness layer for behavioural change over hours–days. It does not claim to detect falls or replace emergency services.

**“Why not alert the family immediately?”**  
Progressive verification reduces unnecessary alerts. A reassuring reply can resolve the concern with the senior.

**“Why WhatsApp?”**  
Low friction for seniors already messaging; no new app, no wearable, no camera.

**“What if she’s just slow today?”**  
Personal baselines adapt; escalation uses explicit rules (confidence, sustained change, no response, repeated change) — not every blip.

---

## Success criteria for the demo

Judges should be able to answer yes to all of these:

- [ ] I understand Mdm Tan’s **personal normal**
- [ ] I see that Nomi **noticed a change** relative to that normal
- [ ] I see that Nomi **verified with the senior first**
- [ ] I see a **contextual caregiver alert** (or a clean resolve without alert)
- [ ] I understand Nomi does **not** diagnose or declare emergencies

---

## Scope reminder

This MVP demonstrates **one complete senior → Nomi → caregiver flow**.

It does **not** include (proposal future work): multilingual / voice UX, multi-caregiver networks, community-care integrations, or clinical prediction.
