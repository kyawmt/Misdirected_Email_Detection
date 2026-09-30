# Phase 8 — Reviewed feedback

Served bundle: contract `med-api-v1`, snapshot `med-synth-v4`, features `med-features-v2`, model `med-model-v2`, policy `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled. **A click is not a label.** Feedback reaches a label only through a reviewer, and it never retrains, recalibrates, or moves the cutoff. All data is fictional. Monitored requests are `validation_product_like` drafts, plus copies of legitimate first-contact validation drafts in the shifted windows. No frozen test row is read, replayed, scored, or summarized; the one recorded test result is quoted as recorded where it serves as a reference.

## Sources, and how much reviewed evidence exists today

| Source | Content | Reviewed | Usable as a label for the monitored traffic |
| --- | --- | --- | --- |
| API feedback file (`POST /feedback`) | 2 lines, 2 assessments, 1 contact; labels unintended 2; 2026-09-26T17:11:40Z to 2026-09-27T00:43:51Z | 0 (clicks) | No. No line names a draft, and the log and feedback line carry no assessment time. |
| Dataset `reviewer_feedback.csv` | 3 rows about non-frozen drafts: train/pending_review 2, train/rejected 1 | 0 accepted | No. 0 rows concern a validation draft. |

**Reviewed labels on the monitored traffic: 0.** Label delay for the click feedback is not computable: neither the log line nor the feedback line carries an assessment time. Everything below that reports coverage, delay, or efficacy uses a **simulated reviewer**, not real reviews.

## The rule

Only a reviewer record with status accepted and an asserted bit changes a recipient label; clicks, pending, and rejected records change nothing. In this run 0 labels were changed by feedback. The SHA-256 of `policy.json` and `model.joblib` was recorded before and after the feedback stage and did not change.

## Why feedback on warned emails alone is biased

People are shown a warning only when the policy warns. If only those emails are reviewed:

- **Precision is estimable.** Every reviewed email was warned, so the share confirmed misdirected is a precision-side figure.
- **Recall is not.** A mistake the policy allowed is never shown to anyone, so it never reaches a reviewer, and the denominator silently drops every miss. On the reference windows, 6 of 6 reviewed warned emails were misdirected, so recall computed from warned emails alone is 1.00. With a sample of allowed emails added, the estimate is 0.363 (interval 0.021 to 0.369) at 14 days.
- **What senders do with a warning changes what can be reviewed.** A sender who removes a flagged recipient sends a corrected email, and the mistake that was caught never appears in sent mail. Warnings a sender ignores are the ones that stay in the record. Reviewing only mail sent after a warning is another biased sample.
- **Clicks are not verified.** A click says what one person thought at one moment. It needs a review before it is a label.

The fix is a sampled review of *allowed* emails with known inclusion probabilities, so misses can be observed and weighted back to the population.

## Review workflow

1. A click or a warning creates no label. It can put an email in a review queue.
2. The queue is built from the decision and the score band: all warned emails, and a seeded sample of allowed emails with a higher inclusion probability where the score is higher.
3. A reviewer answers whether each recipient was intended. Only an accepted review can change a recipient's effective label.
4. Efficacy is computed from returned answers, with each stratum weighted by its population, and always shown with its counts.

Strata are fixed in `med_monitor.version` before any answer is read. The score bands are generic round numbers. The recorded validation misses all score above 0.9 (see the [error analysis](../phase_5/ERROR_ANALYSIS.md)), so the top band holds them here; a real system cannot assume that. The lowest band is sampled at a low rate so that mistakes the score does not see can still be observed.

| Stratum | Rule | Inclusion probability | Emails, reference | Emails, current | Queued (all windows) |
| --- | --- | --- | --- | --- | --- |
| `warned` | every warned email | 1 | 6 | 2 | 8 |
| `allowed_score_at_least_0.9` | allowed, email risk score from 0.9 to below 1 | 1 | 40 | 93 | 133 |
| `allowed_score_0.5_to_0.9` | allowed, email risk score from 0.5 to below 0.9 | 0.1 | 33 | 36 | 6 |
| `allowed_score_below_0.5` | allowed, email risk score from 0 to below 0.5 | 0.01 | 1,921 | 1,869 | 45 |

## Simulated reviewer

- Label source: simulated reviewer: the stipulated label of each queued validation draft, returned after a seeded delay.
- Every queued email is answered; delays are gamma-distributed; the reviewer is always right. These are assumptions.
- Delay: gamma(shape=2.0, scale=3.0 days), seeded per queued email; median 5.1 days, 90th percentile 11.9 days, longest 22.2 days over 192 queued emails.
- Because every queued email is eventually answered and the reviewer is always right, this shows the arithmetic of a review workflow and its delay. It says nothing about real reviewer accuracy, return rates, or workload.

## Label coverage and delay

| Within | Block | Queued | Returned | Returned, of assessed emails | Warned emails reviewed, of warned |
| --- | --- | --- | --- | --- | --- |
| 1 day | reference | 76 | 3 | 3 of 2,000 (0.15%) | 1 of 6 (17%) |
| 1 day | current | 116 | 6 | 6 of 2,000 (0.30%) | 1 of 2 (50%) |
| 3 days | reference | 76 | 23 | 23 of 2,000 (1.15%) | 2 of 6 (33%) |
| 3 days | current | 116 | 36 | 36 of 2,000 (1.80%) | 1 of 2 (50%) |
| 7 days | reference | 76 | 47 | 47 of 2,000 (2.35%) | 4 of 6 (67%) |
| 7 days | current | 116 | 80 | 80 of 2,000 (4.00%) | 2 of 2 (100%) |
| 14 days | reference | 76 | 73 | 73 of 2,000 (3.65%) | 6 of 6 (100%) |
| 14 days | current | 116 | 112 | 112 of 2,000 (5.60%) | 2 of 2 (100%) |
| 30 days | reference | 76 | 76 | 76 of 2,000 (3.80%) | 6 of 6 (100%) |
| 30 days | current | 116 | 116 | 116 of 2,000 (5.80%) | 2 of 2 (100%) |

## Efficacy from returned labels

Recall and false interventions are computed from returned labels only, with the counts shown. Recall is confirmed warned mistakes over all mistakes, where the mistakes among allowed emails are estimated from the sampled strata; the interval adds the per-stratum 95% Clopper-Pearson intervals, so it is conservative and not simultaneous. Emails not yet reviewed are unknown, not zero. Reference means windows 1, 2, 3, 4; current means windows 5, 6, 7, 8.

**Labels returned within 1 day**

| Block | Reviewed warned emails | Confirmed false interventions | Confirmed misdirected, all strata | Reviewed allowed emails (mistakes / reviewed / population) | Estimated recall (conservative interval) |
| --- | --- | --- | --- | --- | --- |
| reference | 1 of 1 (100%) misdirected | 0 of 1 reviewed warned | 1 | `0.5_to_0.9`: 0 / 0 / 33; `at_least_0.9`: 0 / 0 / 40; `below_0.5`: 0 / 2 / 1921 | not estimable |
| current | 1 of 1 (100%) misdirected | 0 of 1 reviewed warned | 1 | `0.5_to_0.9`: 0 / 0 / 36; `at_least_0.9`: 0 / 5 / 93; `below_0.5`: 0 / 0 / 1869 | not estimable |

**Labels returned within 3 days**

| Block | Reviewed warned emails | Confirmed false interventions | Confirmed misdirected, all strata | Reviewed allowed emails (mistakes / reviewed / population) | Estimated recall (conservative interval) |
| --- | --- | --- | --- | --- | --- |
| reference | 2 of 2 (100%) misdirected | 0 of 2 reviewed warned | 7 | `0.5_to_0.9`: 0 / 1 / 33; `at_least_0.9`: 5 / 13 / 40; `below_0.5`: 0 / 7 / 1921 | 0.281 (0.003 to 0.407) † |
| current | 1 of 1 (100%) misdirected | 0 of 1 reviewed warned | 1 | `0.5_to_0.9`: 0 / 0 / 36; `at_least_0.9`: 0 / 28 / 93; `below_0.5`: 0 / 7 / 1869 | not estimable |

**Labels returned within 7 days**

| Block | Reviewed warned emails | Confirmed false interventions | Confirmed misdirected, all strata | Reviewed allowed emails (mistakes / reviewed / population) | Estimated recall (conservative interval) |
| --- | --- | --- | --- | --- | --- |
| reference | 4 of 4 (100%) misdirected | 0 of 4 reviewed warned | 12 | `0.5_to_0.9`: 0 / 2 / 33; `at_least_0.9`: 8 / 28 / 40; `below_0.5`: 0 / 13 / 1921 | 0.344 (0.009 to 0.385) † |
| current | 2 of 2 (100%) misdirected | 0 of 2 reviewed warned | 2 | `0.5_to_0.9`: 0 / 3 / 36; `at_least_0.9`: 0 / 62 / 93; `below_0.5`: 0 / 13 / 1869 | 1.000 (0.004 to 1.000) † |

**Labels returned within 14 days**

| Block | Reviewed warned emails | Confirmed false interventions | Confirmed misdirected, all strata | Reviewed allowed emails (mistakes / reviewed / population) | Estimated recall (conservative interval) |
| --- | --- | --- | --- | --- | --- |
| reference | 6 of 6 (100%) misdirected | 0 of 6 reviewed warned | 16 | `0.5_to_0.9`: 0 / 2 / 33; `at_least_0.9`: 10 / 38 / 40; `below_0.5`: 0 / 27 / 1921 | 0.363 (0.021 to 0.369) † |
| current | 2 of 2 (100%) misdirected | 0 of 2 reviewed warned | 2 | `0.5_to_0.9`: 0 / 3 / 36; `at_least_0.9`: 0 / 89 / 93; `below_0.5`: 0 / 18 / 1869 | 1.000 (0.005 to 1.000) † |

**Labels returned within 30 days**

| Block | Reviewed warned emails | Confirmed false interventions | Confirmed misdirected, all strata | Reviewed allowed emails (mistakes / reviewed / population) | Estimated recall (conservative interval) |
| --- | --- | --- | --- | --- | --- |
| reference | 6 of 6 (100%) misdirected | 0 of 6 reviewed warned | 18 | `0.5_to_0.9`: 0 / 3 / 33; `at_least_0.9`: 12 / 40 / 40; `below_0.5`: 0 / 27 / 1921 | 0.333 (0.021 to 0.333) † |
| current | 2 of 2 (100%) misdirected | 0 of 2 reviewed warned | 2 | `0.5_to_0.9`: 0 / 3 / 36; `at_least_0.9`: 0 / 93 / 93; `below_0.5`: 0 / 18 / 1869 | 1.000 (0.005 to 1.000) † |

† Fewer than 30 confirmed misdirected emails. That is arithmetic on a handful of cases, not a finding, and the performance check refuses to compare it.

## Confirmed performance change

A performance statement needs at least 30 confirmed misdirected emails in the reference and in the current block, and it is made only when the recall intervals do not overlap. At 14 days the reference block has 16 and the current block 2. At 30 days they hold 18 and 2, so the confirmed mistakes are not spread evenly over the replayed period.

**Finding: insufficient sample.** No performance statement: 16 and 2 confirmed misdirected emails, minimum 30 on each side.

At a misdirection rate of 0.5% a block of 2,000 emails holds about 10 mistakes, so 30 confirmed mistakes need roughly 6,000 emails on each side with every mistake confirmed, and more when only a sample is reviewed. This is the reason input drift and decision-rate change are watched first and are reported separately: they arrive long before confirmed performance can.

## What this does not show

- It does not show how well real reviewers would label, how many would respond, or how fast.
- It does not show that detection improved. It shows how to measure detection when labels arrive, and why a click stream cannot do it.
- The reference recall for a future comparison is the one recorded frozen test pass: 9 of 30 (30.00%) misdirected emails warned (exact interval 0.147 to 0.494, if emails were independent). The validation figure is not independent of the cutoff.
