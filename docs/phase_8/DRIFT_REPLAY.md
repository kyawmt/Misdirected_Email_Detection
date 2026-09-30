# Phase 8 — Drift replay

Served bundle: contract `med-api-v1`, snapshot `med-synth-v4`, features `med-features-v2`, model `med-model-v2`, policy `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled. This document replays one shift, follows the alert to an investigation, and ends with a proposed experiment. The experiment is a written proposal. Nothing in the served model, the policy, or `T_warn` changes. All data is fictional. Monitored requests are `validation_product_like` drafts, plus copies of legitimate first-contact validation drafts in the shifted windows. No frozen test row is read, replayed, scored, or summarized; the one recorded test result is quoted as recorded where it serves as a reference.

## What was replayed

The scenario is a **new partner or collaborator wave**: legitimate first contacts (planned introductions to a new colleague or a new external partner) replace a growing share of ordinary routine mail. It is built from the validation data, so no data was generated and no `med_data` rule changed. The traffic is `validation_product_like` in send-time order, cut into 8 windows of 500 emails. The shifted emails are copies of the 40 legitimate first-contact validation drafts (variants `legitimate_first_contact`, `legitimate_new_domain`) drawn with seed 20260926; each replaces a `routine` draft at a seeded position. Scenario and variant fields build the simulated traffic. They are never sent to the API and never used as monitored inputs.

| Window | Role | Sent (base traffic) | Injected first-contact emails | Share of window |
| --- | --- | --- | --- | --- |
| 1 | reference | 2025-03-31 to 2025-04-17 | 0 | 0% |
| 2 | reference | 2025-04-17 to 2025-05-06 | 0 | 0% |
| 3 | reference | 2025-05-06 to 2025-05-26 | 0 | 0% |
| 4 | reference | 2025-05-26 to 2025-06-13 | 0 | 0% |
| 5 | current | 2025-06-13 to 2025-07-03 | 0 | 0% |
| 6 | current | 2025-07-03 to 2025-07-23 | 20 | 4% |
| 7 | current | 2025-07-23 to 2025-08-11 | 40 | 8% |
| 8 | current | 2025-08-12 to 2025-08-29 | 80 | 16% |

The plan checksum is `a16f64569efd3729…`. The schedule (`SHIFT_SCHEDULE` in `med_monitor.version`) was set so that the last window crosses the alert rules. That makes this a demonstration of the path from alert to investigation, **not a measurement of how sensitive the monitor is**. How it behaves when nothing is shifted is the other half of the evidence: see the first row of the timeline below.

## Timeline

- **No shift.** The unshifted control (window 5) raised no alert. 0 of the 4 reference windows put a feature in the input-drift alert band. The first-window alerts below are what the shift adds.
- **Window 6: `limited_relationship_history_rate`** first alerts. 20 of 500 emails with a recipient that has limited relationship history against 25 of 2000 in the reference period; exact test p = 0.000152 (alpha 0.01).
- **Window 7: `input_drift`** first alerts. 1 feature in the alert band and 4 in the watch band against the train reference (589 recipient rows, 500 emails); 7 features cumulative and structural, not scored.
- **Window 8: `near_cutoff_scores`** first alerts. 8 of 500 emails scoring in the band just below the cutoff against 2 of 2000 in the reference period; exact test p = 7.49e-05 (alpha 0.01).

## Three findings, kept apart

These are separate questions with separate evidence. One alert does not imply the others.

| Finding | Scope | Status | Statement |
| --- | --- | --- | --- |
| **Input drift** (model inputs against train) | window 8 | ALERT | 4 features in the alert band and 7 in the watch band against the train reference (624 recipient rows, 500 emails); 7 features cumulative and structural, not scored. |
| **Input drift** | current windows pooled | watch | 0 features in the alert band and 2 in the watch band against the train reference (2436 recipient rows, 2000 emails); 7 features cumulative and structural, not scored. |
| **Decision-rate change** (share warned) | window 8 | insufficient sample | No statement: 0 of 500 emails warned against 6 of 2000 in the reference period; minimum 2000 on each side. |
| **Decision-rate change** | current windows pooled | no change detected | 2 of 2000 emails warned against 6 of 2000 in the reference period; exact test p = 0.289 (alpha 0.01). |
| **Confirmed performance change** (reviewed labels) | current against reference | insufficient sample | No performance statement: 16 and 2 confirmed misdirected emails, minimum 30 on each side. |

## Investigation

### 1. What alerted

The earliest alert of any kind is in window 6. In window 8, 4 model inputs are in the alert band against train: `co_focus_history_available`, `pair_recency_observed`, `recipient_novel_to_sender`, `content_similarity_observed`. None of them was in the alert band on the pooled reference windows. The input-drift check first alerted in window 7, on 1 feature (`pair_outbound_rate_per_day`); that feature also sits in the watch band on windows with no injected emails, so a one-feature alert on it is low confidence, and the first-contact signature below appears only in window 8.

- Near-cutoff scores: 8 of 500 emails scoring in the band just below the cutoff against 2 of 2000 in the reference period; exact test p = 7.49e-05 (alpha 0.01).
- Limited relationship history: 80 of 500 emails with a recipient that has limited relationship history against 25 of 2000 in the reference period; exact test p = 4.69e-37 (alpha 0.01).

### 2. Which inputs moved, and what they have in common

| Feature | Unit | Train mean | Window mean | Share shift | PSI | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `co_focus_history_available` | recipient_row | 0.9823 | 0.8718 | -0.1105 | 0.234 | ALERT |
| `pair_recency_observed` | recipient_row | 0.9823 | 0.8718 | -0.1105 | 0.234 | ALERT |
| `recipient_novel_to_sender` | recipient_row | 0.0177 | 0.1282 | 0.1105 | 0.234 | ALERT |
| `content_similarity_observed` | recipient_row | 0.9810 | 0.8718 | -0.1092 | 0.224 | ALERT |

These inputs describe the same fact from different sides: the sender has no earlier mail with the recipient (`recipient_novel_to_sender`, `pair_recency_observed`, `co_focus_history_available`), so there is no earlier text to compare with (`content_similarity_observed`). That is the signature of first contacts. Novelty is not a label: the shift says who is being addressed, not whether anyone is mistaken.

### 3. Where in the traffic

| Slice | Window 5 (control), emails | Window 8, emails | Window 8, warned | Window 8, near band | Window 8, limited history |
| --- | --- | --- | --- | --- | --- |
| Has a first-contact recipient | 2 | 80 | 0 | 8 | 80 |
| No first-contact recipient | 498 | 420 | 0 | 0 | 0 |

Replay ground truth, which a real investigation would not have: 80 of the 500 emails in window 8 were injected first contacts.

### 4. What happened to the scores

Emails in the near band in window 8: 8, of which 8 have a first-contact recipient and 0 do not, against 2 of 2,000 in the reference windows. The highest allowed score in window 8 is 0.998527 (margin to `T_warn` 0.00115); the reference windows' highest is 0.997371 (margin 0.00231). There were no warnings in window 8. The 8 near-band emails are 4 distinct drafts, because the replay repeats pool drafts (460 distinct drafts among 500 emails in this window). Nothing about a draft or the model changed: the margin narrows because these drafts are now a larger share of traffic, and because the pool also draws legitimate first contacts from `validation_diagnostic`, which the reference windows do not contain.

### 5. What reviewed labels say (simulated reviewer)

Queued emails from window 8 whose simulated label came back within 14 days. The labels are the dataset's stipulations returned by a simulated reviewer; [the feedback review](FEEDBACK_REVIEW.md) lists the assumptions. They are not real reviews.

| Review stratum | Returned | Confirmed misdirected | Confirmed all intended |
| --- | --- | --- | --- |
| `allowed_score_0.5_to_0.9` | 1 | 0 | 1 |
| `allowed_score_at_least_0.9` | 40 | 0 | 40 |
| `allowed_score_below_0.5` | 4 | 0 | 4 |

### 6. What is and is not established

- **Established:** the model inputs moved toward first contacts (window 8 input drift: ALERT); more emails now score in the band just below the cutoff (near-band check: ALERT). Pooling all four current windows dilutes a shift that ramps up late: the pooled input-drift finding is watch, which is why the per-window finding is the one to read.
- **Pooled decision rate:** no change detected. 2 of 2000 emails warned against 6 of 2000 in the reference period; exact test p = 0.289 (alpha 0.01). That is a statement about too few warnings to see a change, not proof that none occurred.
- **Not established:** any change in detection or in false warnings. Confirmed performance change: insufficient sample. No performance statement: 16 and 2 confirmed misdirected emails, minimum 30 on each side. Warned emails reviewed in windows 5 to 8 within 14 days: 2 of 2 (100%), of which 0 were confirmed all intended. That counts confirmed false interventions among reviewed warnings only; it is not a false-warning rate.
- **What the simulated review adds:** 40 allowed emails from window 8 scoring at least 0.9 were reviewed, and 40 were confirmed all intended. The extra mass near the cutoff is legitimate first-contact mail. That is a finding about this replay's pool, not a guarantee.
- **The risk this points at:** legitimate first contacts already score just below the cutoff. A wave of them pushes more legitimate mail into that margin. Nothing here shows a false warning, and nothing here shows the margin is safe.
- **Not addressed:** mistaken first contacts (S11) are missed by the served policy on every validation and test subset. A first-contact wave does not change that, and the monitor cannot see it without reviewed labels.

## Proposed targeted experiment (not run)

**Question.** Under a first-contact wave, how often does a *legitimate* first contact score at or above `T_warn`, and how much mass sits in the near band?

**Why this and not a model change.** The replay shows the inputs and the margin moving. It cannot say whether the score tail crosses `T_warn`, because the shift is built from only 40 distinct legitimate first-contact drafts. Changing the cutoff, the model, or the features on this evidence would be tuning on the replay.

**Design (shadow mode, log only, no user sees a warning).**

1. Score first-contact traffic for the affected senders with the frozen `med-policy-v2`, in shadow, for a fixed window.
2. Review every shadow warning, every near-band email, and a seeded sample of the rest, using the stratified queue in [the feedback review](FEEDBACK_REVIEW.md#review-workflow).
3. Estimate two quantities among reviewed legitimate first contacts: the share at or above `T_warn` (a false-warning rate) and the share in the near band, each with an exact interval.
4. Size: a zero-count bound at the budget of 1 per 1,000 needs about 2,996 reviewed legitimate first contacts if emails were independent, and more when they come from few senders.

**Decision rule, written before the run.**

- Zero false warnings and a near-band share no higher than the reference: keep `med-policy-v2`, record the tail, and keep watching the near-band check.
- Any confirmed false warning, or a near-band share above the reference: do not move `T_warn`. Open a new policy version through the offline path (new evidence on a new frozen dataset version, separate calibration and selection portions, one test pass) and gate it as in [the runbook](RUNBOOK.md#promotion-gates).

**Side question the same data answers.** The recorded threshold-free separation of mistaken first contacts from legitimate ones (AUC 0.88 on `validation_diagnostic`, 10 against 20 rows) says the score can rank them. The shadow run measures whether that ranking holds at the volume and mix of a real wave. It does not, by itself, justify a lower cutoff.


## Reproduce

```bash
python -m med_monitor build-reference
python -m med_monitor replay
python -m med_monitor feedback
python -m med_monitor bundle-checks
python -m med_monitor report
```

`replay` runs the plan through the API in process (`--api URL` uses a running service). It refuses to start unless the service reports the frozen bundle. Scores and decisions are deterministic; only latency changes between runs.
