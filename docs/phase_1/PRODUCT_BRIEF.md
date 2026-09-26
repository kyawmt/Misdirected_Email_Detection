# Phase 1 — Product brief

Status: requirements defined; no implementation or measured results. Date: 2026-09-26.

## Problem and user

An employee may accidentally address an outbound email to someone they did not intend. The demo helps a fictional sender review potentially mistaken recipients before a simulated send, while minimizing interruptions to legitimate communication. A reviewer of the demo is the primary audience; the sender is the product persona. Reducing false alerts keeps the demonstration focused on interruptions a sender would actually notice.

## Experience and decisions

Select or compose a fictional draft, assess its recipients against earlier communication, and display a recipient-specific explanation. A correction creates a new assessment. The unit of prediction is a draft–recipient pair; an email is misdirected if at least one addressed recipient is unintended. Missing intended recipients without an unintended addressee are outside scope.

The initial email risk is the maximum recipient risk. Valid assessments yield **allow**, **warn**, or, only after separate justification, **simulated block**. Allow means no intervention at the selected operating point, not guaranteed correctness. Failures yield **unable to assess**, never a safe decision. No message is actually sent or blocked.

## Scope and assumptions

| ID | Phase 1 decision or assumption |
| --- | --- |
| A1 | One fictional organization, `demo.example`, with English plain-text drafts and fictional contacts on reserved `.example` domains. No real mailbox or attachment access. |
| A2 | Low-volume local demonstration; 1–20 unique recipients across To/Cc/Bcc. Product-level request limits are specified separately. These are convenience limits, not research findings. |
| A3 | Historical context comes from a selected fictional snapshot containing only events strictly before the draft. Intent labels and scenario answers are unavailable to scoring. |
| A4 | Risk uses a 0–1 scale, higher meaning more suspicious. It is not a probability without calibration evidence; maximum aggregation is our design choice. |
| A5 | Numeric thresholds and real-world prevalence are unknown. Simulated blocking defaults to disabled. Unfamiliarity, external status, or topic change alone does not establish unintendedness. |
| A6 | Synthetic outcomes demonstrate engineering behavior, not enterprise effectiveness. Cold starts remain valid inputs with explicit limitations. |

## Success and evidence

Target at most **one false intervention per 1,000 legitimate emails**; count both warnings and simulated blocks. Maximize recall within this budget and compare against always-allow and simple rules. Target warm local scoring **p95 below 300 ms** on documented hardware. These are provisional requirements; all metrics are currently **not measured**. Evidence rules and failure handling are in the acceptance criteria.

## Research and role alignment

Adopt message–recipient assessment from R1 and pre-send feedback from R4. R2 motivates legitimate first-contact scenarios; R3 supports behavioral context. Maximum aggregation, abstention behavior, limits, and operating budgets are project decisions, not paper guarantees. References and evidence limitations are in the [research basis](../../README.md#research-basis-and-techniques).

This scope covers applied ML, combining signals, efficacy tradeoffs, real-time reliability, and written communication. Modeling, the scoring API, the review UI, monitoring, and deployment remain later work.

## Phase 1 deliverables

- [Scenario list](SCENARIOS.md)
- [Input/output specification](INPUT_OUTPUT_SPECIFICATION.md)
- [Acceptance criteria and measurement definitions](ACCEPTANCE_CRITERIA.md)

