# Phase 8 — Sender-level A/B test proposal

**This is a proposal. There is no online evidence.** No experiment has been run, no real user has seen a warning, and every number below is arithmetic on stated assumptions. The served bundle is contract `med-api-v1`, snapshot `med-synth-v4`, features `med-features-v2`, model `med-model-v2`, policy `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled. Blocking stays disabled in every arm.

## Question

When a sender is shown a warning about a recipient, does the sender correct the mistake more often than when nothing is shown, and at what cost in interruptions?

**What the test can and cannot measure.** Both arms run the same frozen policy on the same kind of draft, so its scores, its warnings, and its recall are the same in both arms by construction. Showing a decision does not change the policy's prediction. Recall therefore describes the model and is not an effect of the treatment. What can differ between the arms is what senders do: whether a flagged recipient is removed or replaced before the email is sent. The outcomes below measure that.

## Design

- **Arms.** Control: the policy scores every draft in shadow and no warning is shown. Treatment: the same policy, warnings shown. Both arms are scored, so every metric except sender behavior is observable in both.
- **Unit of randomization: the sender.** A sender's drafts share history, habits, and recipients, so randomizing emails would leak treatment across a sender's mail and understate variance. Analysis uses sender-level clustering.
- **Feasibility on this population.** The validation traffic has 14 senders and 95.1% of emails come from one of them, so a sender-level test cannot be run on it. A real test needs many senders with comparable volume.
- **Exposure.** Fixed horizon; no interim looks at the primary outcome.

### When drafts, labels, and outcomes are captured

1. **First assessment.** In both arms, record the draft's recipient set as first assessed (the *as-assessed snapshot*) and the policy's decision. In the treatment arm the warning is shown after this capture.
2. **Review.** A reviewer labels each recipient of the as-assessed snapshot as intended or unintended, from a stratified sample with known inclusion probabilities (see [the feedback review](FEEDBACK_REVIEW.md#review-workflow)). The reviewer sees neither the sent mail nor the sender's arm. Labels attach to the snapshot, so a correction cannot erase the mistake it corrected.
3. **Send.** Record the recipient set at send. A mistake is *corrected* when every recipient the reviewer marked unintended is absent at send.
4. **Label cutoff.** The date after which a returning label is not counted is fixed before the test starts.

## Metrics

| Role | Metric | Definition | Baseline and its source |
| --- | --- | --- | --- |
| **Primary** | Correction rate among warned mistakes | Of the drafts the policy warns (shown in treatment, shadow in control) whose as-assessed recipients a reviewer marks misdirected, the share in which every unintended recipient is gone at send. Treatment against control | Not measured; no correction data exists. Assumed values are in the sample-size grid |
| Secondary | Misdirected emails sent per 1,000 emails | Emails a reviewer marks misdirected on the as-assessed snapshot whose unintended recipient is still present at send, per 1,000 emails | Not measured. It is the outcome that matters most and the one this test is least able to resolve; see the sample sizes |
| Descriptive, both arms | Recall of the frozen policy | Warned confirmed mistakes over all confirmed mistakes on the as-assessed snapshot. Identical in the two arms by construction, so it is reported, not compared | 8 of 20 (40.00%) on validation product-like, the subset that chose the cutoff, so not independent of it |
| Guardrail | Warning rate | Emails warned over emails assessed | 8 of 4,000 (0.20%) on validation product-like, the subset that chose the cutoff |
| Guardrail | Confirmed false interventions | Reviewed warned emails confirmed all intended, per 1,000 legitimate emails; budget 1 per 1,000 | 0 of 3,980 (0.00%) on validation; not confidence-supported (AC01 is insufficient evidence) |
| Guardrail | Intended recipients removed after a warning | Of warned drafts a reviewer marks all intended, the share in which the sender removes or replaces a recipient before send. The cost of a false warning that a sender obeys | none measured |
| Guardrail | Latency | Client p95 per arm, at least 1,000 requests per arm, below 300 ms | the recorded AC05 measurement |
| Guardrail | Unable to assess | Share of requests that return unable to assess, by category | 0 of 2,000 (0.00%) in the reference windows |
| Safety | Blocks | Must be 0 | 0 in the reference windows |

## Sample size

Alpha 0.05, power 0.8, assumed misdirection rate 0.5% (a simulation assumption), 200 emails per sender over the test period. Clustering inflates emails by the design effect 1 + (m - 1) * ICC; ICC is unknown, so three values are shown. A mistake is warned with probability equal to the policy's recall (0.40 on validation), so the test sees about 2.0 warned mistakes per 1,000 emails.

There is no correction data, so the two behavioral inputs are **assumptions, shown as a grid**: the share of warned mistakes a sender fixes with no warning shown, and the further share of the rest that a shown warning gets fixed.

### Primary outcome: correction rate among warned mistakes

| Fixed with no warning | Extra fixed by a shown warning | Correction rate with a warning | Confirmed warned mistakes per arm | Emails per arm if independent | With sender clustering (per arm) |
| --- | --- | --- | --- | --- | --- |
| 0.05 | 0.20 | 0.240 | 53 | 26,500 | ICC 0: 26,500 emails, 133 senders; ICC 0.01: 79,235 emails, 397 senders; ICC 0.05: 290,175 emails, 1,451 senders |
| 0.05 | 0.50 | 0.525 | 14 | 7,000 | ICC 0: 7,000 emails, 35 senders; ICC 0.01: 20,930 emails, 105 senders; ICC 0.05: 76,651 emails, 384 senders |
| 0.10 | 0.20 | 0.280 | 74 | 37,000 | ICC 0: 37,000 emails, 185 senders; ICC 0.01: 110,631 emails, 554 senders; ICC 0.05: 405,151 emails, 2,026 senders |
| 0.10 | 0.50 | 0.550 | 16 | 8,000 | ICC 0: 8,000 emails, 40 senders; ICC 0.01: 23,920 emails, 120 senders; ICC 0.05: 87,601 emails, 439 senders |
| 0.20 | 0.20 | 0.360 | 123 | 61,500 | ICC 0: 61,500 emails, 308 senders; ICC 0.01: 183,885 emails, 920 senders; ICC 0.05: 673,426 emails, 3,368 senders |
| 0.20 | 0.50 | 0.600 | 23 | 11,500 | ICC 0: 11,500 emails, 58 senders; ICC 0.01: 34,385 emails, 172 senders; ICC 0.05: 125,926 emails, 630 senders |

### Why misdirected emails sent is only secondary

Only warned mistakes can change, and the policy warned 8 of 20 (40%) of the validation mistakes, so the treatment moves a rate that is already small by a fraction of itself:

| Fixed with no warning | Extra fixed by a shown warning | Control, sent per 1,000 emails | Treatment, sent per 1,000 emails | Emails per arm if independent |
| --- | --- | --- | --- | --- |
| 0.05 | 0.20 | 4.75 | 4.37 | 493,458 |
| 0.05 | 0.50 | 4.75 | 3.80 | 74,039 |
| 0.10 | 0.20 | 4.50 | 4.14 | 520,997 |
| 0.10 | 0.50 | 4.50 | 3.60 | 78,170 |
| 0.20 | 0.20 | 4.00 | 3.68 | 586,405 |
| 0.20 | 0.50 | 4.00 | 3.20 | 87,981 |

### Warning rate (detect a doubling)

| Baseline rate | Target rate | Emails per arm if independent | With sender clustering (per arm) |
| --- | --- | --- | --- |
| 0.0020 | 0.0040 | 11,737 | ICC 0: 11,737 emails, 59 senders; ICC 0.01: 35,094 emails, 176 senders; ICC 0.05: 128,521 emails, 643 senders |

### False-intervention guardrail

To show with 95% confidence that the false-intervention rate is no higher than 1 per 1,000 after observing zero, an arm needs about 2,996 reviewed legitimate emails if they were independent. With sender clustering: ICC 0: 2,996 emails, 15 senders; ICC 0.01: 8,959 emails, 45 senders; ICC 0.05: 32,807 emails, 165 senders.

## Stopping rules

- **Stop an arm at once** on any block decision, any response that carries a decision or score with a failure, a served version that is not the frozen bundle, a service answering without a loaded bundle, or an unable-to-assess alert (see [monitoring](MONITORING.md)).
- **Stop the treatment for harm** when confirmed false interventions reach 9 within 2,996 reviewed legitimate emails: at the budget rate a count that high has a probability of 0.01 or less. It is a safety stop, not a success criterion.
- **Do not stop early for success.** The primary outcome is read once, at the planned horizon, on labels returned by the label cutoff.
- **Do not extend** a test whose primary outcome is inconclusive without a new protocol; extending by peeking inflates the error rate.

## Analysis and reading

- Cluster-robust intervals at the sender level. Report counts and denominators for every metric.
- Reviewed labels come from the stratified queue with known inclusion probabilities, so mistakes the policy misses are weighted back. Feedback clicks are not labels.
- A positive primary result would say that, for the senders tested, a shown warning got more flagged mistakes corrected, at a stated interruption cost. It would not say the model improved, and it would not measure the mistakes the policy does not warn on.

## Preconditions not met today

- **Correction logging.** The UI records only an intended or unintended click. The primary outcome needs the recipient set at first assessment and at send, linked by a draft identifier. The API accepts an optional `draft_reference` correlation label that the UI does not send, and nothing records a send.
- Reviewers who label the as-assessed snapshot without seeing the sent mail or the arm.
- Shadow scoring that records the decision without showing it, and a way to randomize senders at request time.
- Enough senders with comparable volume.
- A privacy decision on the log fields the monitor needs (see [monitoring](MONITORING.md#what-the-structured-log-carries-and-what-it-does-not)) and on storing recipient sets at first assessment and at send.
