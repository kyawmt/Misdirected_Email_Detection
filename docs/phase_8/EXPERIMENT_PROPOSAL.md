# Phase 8 — Sender-level A/B test proposal

**This is a proposal. There is no online evidence.** No experiment has been run, no real user has seen a warning, and every number below is arithmetic on stated assumptions. The served bundle is contract `med-api-v1`, snapshot `med-synth-v4`, features `med-features-v2`, model `med-model-v2`, policy `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled. Blocking stays disabled in every arm.

## Question

Does showing the frozen warning policy to senders lead to more confirmed detections of misdirected mail, at an acceptable cost in interruptions, than showing nothing (shadow scoring only)?

## Design

- **Arms.** Control: the policy scores every draft in shadow and no warning is shown. Treatment: the same policy, warnings shown. Both arms are scored, so every metric except user behavior is observable in both.
- **Unit of randomization: the sender.** A sender's drafts share history, habits, and recipients, so randomizing emails would leak treatment across a sender's mail and understate variance. Analysis uses sender-level clustering.
- **Feasibility on this population.** The validation traffic has 14 senders and 95.1% of emails come from one of them, so a sender-level test cannot be run on it. A real test needs many senders with comparable volume.
- **Exposure.** Fixed horizon; no interim looks at the primary metric.

## Metrics

| Role | Metric | Definition | Baseline and its source |
| --- | --- | --- | --- |
| Primary | Confirmed detections | Warned emails a reviewer confirms are misdirected, over all confirmed misdirected emails (recall), from the stratified review | 0.30: 9 of 30 (30.00%), the one recorded frozen test pass |
| Guardrail | Warning rate | Emails warned over emails assessed | 8 of 4,000 (0.20%) on validation product-like, the subset that chose the cutoff |
| Guardrail | Confirmed false interventions | Reviewed warned emails confirmed all intended, per 1,000 legitimate emails; budget 1 per 1,000 | 0 of 3,980 (0.00%) on validation and 0 of 5,970 (0.00%) on the recorded test pass; not confidence-supported (AC01 is insufficient evidence) |
| Guardrail | User corrections | Share of warned emails in which the sender changes a flagged recipient before sending. **Not measurable today:** the UI records no correction, only an intended or unintended click | none measured |
| Guardrail | Latency | Client p95 per arm, at least 1,000 requests per arm, below 300 ms | the recorded AC05 measurement |
| Guardrail | Unable to assess | Share of requests that return unable to assess, by category | 0 of 2,000 (0.00%) in the reference windows |
| Safety | Blocks | Must be 0 | 0 in the reference windows |

## Sample size

Alpha 0.05, power 0.8, assumed misdirection rate 0.5% (a simulation assumption), 200 emails per sender over the test period. Clustering inflates emails by the design effect 1 + (m - 1) * ICC; ICC is unknown, so three values are shown.

### Confirmed detections

| Baseline recall | Target recall | Confirmed misdirected emails per arm | Emails per arm if independent | With sender clustering (per arm) |
| --- | --- | --- | --- | --- |
| 0.30 | 0.40 | 356 | 71,200 | ICC 0: 71,200 emails, 356 senders; ICC 0.01: 212,889 emails, 1,065 senders; ICC 0.05: 779,641 emails, 3,899 senders |
| 0.30 | 0.50 | 93 | 18,600 | ICC 0: 18,600 emails, 93 senders; ICC 0.01: 55,615 emails, 279 senders; ICC 0.05: 203,671 emails, 1,019 senders |

### Warning rate (detect a doubling)

| Baseline rate | Target rate | Emails per arm if independent | With sender clustering (per arm) |
| --- | --- | --- | --- |
| 0.0020 | 0.0040 | 11,737 | ICC 0: 11,737 emails, 59 senders; ICC 0.01: 35,094 emails, 176 senders; ICC 0.05: 128,521 emails, 643 senders |

### False-intervention guardrail

To show with 95% confidence that the false-intervention rate is no higher than 1 per 1,000 after observing zero, an arm needs about 2,996 reviewed legitimate emails if they were independent. With sender clustering: ICC 0: 2,996 emails, 15 senders; ICC 0.01: 8,959 emails, 45 senders; ICC 0.05: 32,807 emails, 165 senders.

## Stopping rules

- **Stop an arm at once** on any block decision, any response that carries a decision or score with a failure, a served version that is not the frozen bundle, or an unable-to-assess alert (see [monitoring](MONITORING.md)).
- **Stop the treatment for harm** when confirmed false interventions reach 9 within 2,996 reviewed legitimate emails: at the budget rate that count has a probability of 1% or less. It is a safety stop, not a success criterion.
- **Do not stop early for success.** The primary metric is read once, at the planned horizon, on labels returned by then. A late-returning label is counted only if the protocol fixes a cutoff date before the test starts.
- **Do not extend** a test whose primary metric is inconclusive without a new protocol; extending by peeking inflates the error rate.

## Analysis and reading

- Cluster-robust intervals at the sender level. Report counts and denominators for every metric.
- Reviewed labels come from the stratified queue with known inclusion probabilities, so misses are weighted back. Feedback clicks are not labels.
- A positive result would say the warning surfaced mistakes at a given interruption cost for the senders tested. It would not say the model improved.

## Preconditions not met today

- Enough senders, and a way to randomize them at request time.
- Correction logging in the UI, and a reviewer workflow with real reviewers.
- Shadow scoring that records the decision without showing it.
- A privacy decision on the log fields the monitor needs (see [monitoring](MONITORING.md#what-the-structured-log-carries-and-what-it-does-not)).
