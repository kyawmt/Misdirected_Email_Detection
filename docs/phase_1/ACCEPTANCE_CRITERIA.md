# Phase 1 — Acceptance criteria

Status: requirements specified; product behavior and metrics are **not implemented and not measured**. Acceptance below is prospective unless explicitly labeled as a Phase 1 document check. This document defines what later evidence must demonstrate; it does not execute tests or begin evaluation.

## Measurement definitions

- **Positive recipient:** An addressed recipient that the sender did not intend, according to the fictional scenario's ground truth. Novelty and anomalous content are evidence, not labels.
- **Positive email:** A draft with at least one unintended recipient. A legitimate email has none. Missing intended recipients alone do not make a positive email in this scope.
- **Intervention:** A warn or simulated-block decision. Count an email once even if several recipients are flagged.
- **False interventions per 1,000 legitimate emails:** 1,000 multiplied by legitimate emails receiving an intervention, divided by all legitimate emails submitted in the evaluation set. Report counts and assessment coverage alongside this rate so abstention cannot hide failures.
- **Email recall:** Misdirected emails receiving an intervention divided by all misdirected emails submitted. Unassessed misdirected emails are not detections. Report recipient correctness separately: intervening on a misdirected email for an unrelated legitimate recipient does not demonstrate correct attribution.
- **Email precision:** Misdirected emails among all intervened emails. If there are no interventions, precision is undefined, not 100%.
- **Recipient precision/recall:** Compute from flagged addresses versus unintended addresses. Also report the fraction of misdirected emails with at least one actual unintended recipient flagged.
- **Assessment coverage:** Successfully assessed valid drafts divided by all valid drafts submitted. Report invalid inputs separately, plus unavailable counts and causes. Normal, supported evaluation cases should achieve full coverage; designed failure cases are a separate reliability exercise.

Compute rates over all submitted cases and show assessed-only breakdowns where useful. Always identify the denominator. A failure that asks a user to retry is not a model warning, but remains a separate user burden that must be visible.

## Product targets and required evidence

| ID | Requirement or provisional target | Evidence required in later phases | Current result |
| --- | --- | --- | --- |
| AC01 — Interruption budget | No more than **1 false intervention per 1,000 legitimate emails** on the product-like simulation. Warnings and blocks share the budget. | Frozen-policy results with numerator, denominator, stated simulated prevalence, confidence interval, coverage, and separate warning/block counts. Balanced challenge-set results cannot substitute. | Not measured. |
| AC02 — Detection utility | Maximize recall subject to AC01; demonstrate useful detections beyond always-allow and compare with simple rules at comparable interruption budgets. | Email and recipient metrics, PR-AUC, correct-attribution examples, missed detections, and baseline comparison on the same evaluation split. Zero warnings with zero recall is not sufficient evidence of utility. | Not measured; no numeric recall floor is claimed. |
| AC03 — Threshold integrity | Choose numeric thresholds using validation evidence; preserve a final test for one evaluation of the chosen policy. | Policy version, threshold-selection rationale, sample sizes, and explicit distinction between ranking and probability calibration. | Threshold values unset. |
| AC04 — Conservative blocking | Blocking remains disabled without evidence for a separate stricter threshold and documented false-block tolerance. | Separate block counts, detection benefit, uncertainty, and a recorded enable/disable decision. Meeting the warning budget alone does not authorize a blocking claim. | Disabled by specification. |
| AC05 — Latency | Local warm scoring **p95 < 300 ms** for valid supported drafts, within the stated input limits. | Hardware/OS, model/data versions, request-size mix, sample count, timing boundary, and failures. Report cold-start time separately. | Not measured. |
| AC06 — Recipient completeness | Every unique address in To/Cc/Bcc gets one result with its roles; email risk is the maximum recipient risk. | Boundary checks for duplicates, ties, multiple mistakes, and threshold equality; error breakdown by recipient count. | Not implemented. |
| AC07 — Legitimate novelty | No rule treats a new recipient, external domain, lookalike identity, or topic change alone as proof of a mistake. | Results for S03 and S05–S07, plus combined-signal reasoning. Count wrong interventions as false positives even when explanations sound plausible. | Not implemented. |
| AC08 — Failure clarity | Invalid inputs and unavailable scoring never become allow or fabricated low-risk scores. | S09/S10 outcomes, visible evidence limitations, complete/non-assessed contract consistency, and no stale decision after a draft edit. | Not implemented. |
| AC09 — Traceable explanations | Flagged recipients have supported reasons; assessed outputs identify model, features, context, and policy versions. | Sample outputs consistent with the input/output specification. Scores are labeled as risk unless calibration has been demonstrated. | Not implemented. |
| AC10 — Scope and evidence honesty | All actions and identities remain fictional; performance statements remain specific to the demo's evaluated setting. | Walkthrough/documents distinguish desired scenario outcomes, measured outcomes, research findings, and unresolved limitations. | Documentation requirement defined; application verification pending. |

## Assumptions about measurement and acceptance

**A10 — Latency workload:** For a reproducible local benchmark, assume one request in flight, at least 1,000 measured valid requests after 20 unmeasured warm-up requests. Time from backend receipt through validation, context lookup, feature computation, prediction, policy application, and response preparation. UI rendering and network transit are excluded. Include small and maximum-supported inputs and report their latency separately. These are proposed measurement conditions, not executed load tests or production capacity claims.

**A11 — Uncertainty:** Use a 95% confidence interval for the false-intervention rate. A point estimate meeting AC01 is provisional; a stronger claim that the budget is supported requires its upper confidence bound to meet the budget under justified sampling assumptions. Related variants or threads must not be treated as independent evidence. Choose the suitable interval method during evaluation. Zero observed false positives on a small sample is insufficient evidence of a reliably tiny rate.

**A12 — Unknown prevalence and costs:** Neither real-world misdirection prevalence nor business costs are provided. The future data report must label its chosen prevalence as a simulation assumption and show sensitivity. Do not infer a precision target or fixed recall percentage from paper results. Numeric block tolerance is also deferred; its absence keeps blocking off.

**A13 — Failure of a target:** Record each later target as met, not met, or insufficient evidence, with measured values. If the warning budget is unmet, investigate or explicitly revise the provisional target with rationale; do not silently substitute a looser budget. If evidence is inadequate, retain the limitation and blocking-disabled status. A reproducible educational demo may still be presented with unmet targets disclosed, but must not be described as having met them.

## Research consistency

The research reference IDs below link to the full citations in the [Research Basis](../../PROJECT_PLAN.md#research-basis).

- R1's injected-recipient ranking task supports a separate diagnostic ranking metric; it does not replace AC01/AC02 on a mix of legitimate and misdirected emails.
- R2 motivates first-contact analysis and explicit false-positive reporting; its recipient-level experimental rates do not establish this product's email-level budget.
- R3's email anomaly findings motivate combined evidence, not a claim that every anomaly is accidental misdirection.
- R4 motivates pre-send review and corrections; a user correction alone does not prove a model prediction was correct.

The budget, latency workload, coverage rule, maximum aggregation, confidence requirement, and conservative blocking policy are our project decisions. They are not attributed to the papers as validated results.

## Phase 1 completion check

| Required deliverable | Document review status |
| --- | --- |
| Concise product brief with persona, problem, scope, assumptions, and job alignment | Defined in [PRODUCT_BRIEF.md](PRODUCT_BRIEF.md). |
| Scenario list covering the five required situations and legitimate counterexamples | Defined in [SCENARIOS.md](SCENARIOS.md); no dataset generated. |
| Input/output specification including scores, recipients, reasons, decisions, and versions | Defined in [INPUT_OUTPUT_SPECIFICATION.md](INPUT_OUTPUT_SPECIFICATION.md); no API implemented. |
| Measurable requirements with separate target and result states | Defined here; all runtime and efficacy results remain unmeasured. |
| Research consistency and assumption traceability | R1–R4 connections and assumptions A1–A13 documented across these four files. |

Phase 1 is complete as a requirements deliverable. This is not a product performance sign-off. Dataset construction, feature engineering, model training, numeric threshold selection, backend/UI work, monitoring, testing execution, and deployment have not started in this phase.
