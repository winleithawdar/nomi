# Technical Design Notes

Supporting design notes for the Nomi MVP. They record the project's core
capabilities, implementation decisions, and evaluation approach.

| Brief | Scope |
| --- | --- |
| [Anomaly Detection](p1-anomaly-detection.md) | Sudden behavioural anomaly detection on top of the personal baseline; explainable detection service/API. |
| [Longitudinal Change Detection](P2/p2-change-detection-evaluation.md) | Gradual/sustained change detection; synthetic senior scenarios; prototype evaluation of the combined approach. |
| [Messaging And Check-Ins](p3-whatsapp-integration.md) | Provider-based check-ins and webhooks. Telegram Bot API is the live proof-of-concept transport; the WhatsApp Cloud API material is retained as future-provider reference. |
| [Verification And Caregiver Alerts](p4-verification-escalation.md) | Decision layer between detection and caregiver action; senior-first verification; deterministic escalation rules. |
| [Caregiver Dashboard](p5-frontend-product-ux.md) | Baseline, trend, detection, verification, and alert views. |
| [Integration And Quality Assurance](p6-integration-deployment-qa.md) | Wire the capabilities into one deployable MVP with a deterministic demo scenario and end-to-end QA. |
