# Phase 5 — Evaluation report

This report evaluates the frozen logistic **risk score** (`med-model-v2`, run `logistic_all_balanced`, all features, content cosine included) on dataset `med-synth-v4` with features `med-features-v2`, under warning policy `med-policy-v2`. Scores are risk scores, not probabilities: no calibrator was fit. `T_warn = 0.999677` was chosen on `validation_product_like` only. The frozen test subsets were scored once, after `policy.json` was written.

Email risk is the maximum recipient risk score. An email warns when its risk score is at or above `T_warn`. Blocking is disabled.

## Acceptance status

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC01 | **met** | On this simulation only: 0 false interventions on 5970 legitimate `test_product_like` emails, 0.00 per 1,000, with an exact upper 95% bound of 0.62 per 1,000, within the budget of 1. Warnings 9, blocks 0, coverage 100.0%, assumed prevalence 0.5%. The validation bound is not independent evidence, because validation chose the cutoff. |
| AC02 | **met for S09; partly met for S02, S08; not met for S01, S04, S11** | On this simulation only, on `test_product_like`: 9 of 30 misdirected emails warned (S02 2, S08 5, S09 2; 1 to 7 recipients; risk scores 0.9997 to 1) with 0 false interventions; exact 95% recall interval [0.147, 0.494]. Missed: S01 6, S02 4, S04 5, S08 3, S11 3; 1 to 5 recipients; risk scores 0.1514 to 0.9985. Always-allow warns on none. The rules policy under the same validation rule warned 0 with 0 false interventions (0.00 per 1,000), within the budget on this test. |
| AC03 | **met** | T_warn was chosen on validation_product_like only, written to policy.json before any test label was read, and applied once to the frozen test. The policy checksum is stored in test_evaluation.json. |
| AC04 | **met** | Blocking is disabled. T_block is null and the block count is 0 on every subset. |

AC05 is measured at the API boundary in Phase 6; see [latency](#latency-ac05). AC06 is partial here: maximum aggregation, threshold equality, and flagging every recipient at or above `T_warn` are implemented and tested; duplicate-address merging is in the Phase 6 request normalizer. AC07: **insufficient evidence**. Wrong interventions on the legitimate-novelty scenarios: `validation_product_like` 0 of 349 S03/S05/S06/S07 emails warned, S11 0 of 2 warned; `validation_diagnostic` 0 of 50 S03/S05/S06/S07 emails warned, S11 0 of 10 warned; `test_product_like` 0 of 541 S03/S05/S06/S07 emails warned, S11 0 of 3 warned; `test_diagnostic` 0 of 55 S03/S05/S06/S07 emails warned, S11 0 of 11 warned. Those allows are the desired outcome, but legitimate first contacts score close to the cutoff (highest 0.99737 on `validation_product_like` against `T_warn` 0.99968), and removing pair history from a familiar mistake raises its risk score. The report cannot show that novelty is weighed only with other signals rather than setting a score near the cutoff by itself. AC08 and AC09 are Phase 6 behaviors and are not assessed in this report.

## Operating points at the frozen cutoff

| Subset | Scorer | Warned mistakes | Email recall | Email precision | False interventions | Warnings | Blocks | Flagged unintended recipients | Mistakes with a flagged unintended recipient | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` | policy | 8 / 20 | 0.400 | 1.000 | 0 / 3980 = 0.00 per 1,000 | 8 | 0 | 9 / 22 | 40.0% | 100.0% |
| `validation_product_like` | rules, same validation rule | 0 / 20 | 0.000 | n/a | 0 / 3980 = 0.00 per 1,000 | 0 | 0 | 0 / 22 | 0.0% | 100.0% |
| `validation_product_like` | always-allow | 0 / 20 | 0.000 | n/a | 0 / 3980 = 0.00 per 1,000 | 0 | 0 | 0 / 22 | 0.0% | 100.0% |
| `validation_diagnostic` | policy | 33 / 80 | 0.412 | 1.000 | 0 / 160 = 0.00 per 1,000 | 33 | 0 | 38 / 90 | 41.2% | 100.0% |
| `validation_diagnostic` | rules, same validation rule | 0 / 80 | 0.000 | n/a | 0 / 160 = 0.00 per 1,000 | 0 | 0 | 0 / 90 | 0.0% | 100.0% |
| `validation_diagnostic` | always-allow | 0 / 80 | 0.000 | n/a | 0 / 160 = 0.00 per 1,000 | 0 | 0 | 0 / 90 | 0.0% | 100.0% |
| `test_product_like` | policy | 9 / 30 | 0.300 | 1.000 | 0 / 5970 = 0.00 per 1,000 | 9 | 0 | 11 / 33 | 30.0% | 100.0% |
| `test_product_like` | rules, same validation rule | 0 / 30 | 0.000 | n/a | 0 / 5970 = 0.00 per 1,000 | 0 | 0 | 0 / 33 | 0.0% | 100.0% |
| `test_product_like` | always-allow | 0 / 30 | 0.000 | n/a | 0 / 5970 = 0.00 per 1,000 | 0 | 0 | 0 / 33 | 0.0% | 100.0% |
| `test_diagnostic` | policy | 37 / 88 | 0.420 | 1.000 | 0 / 168 = 0.00 per 1,000 | 37 | 0 | 44 / 99 | 42.0% | 100.0% |
| `test_diagnostic` | rules, same validation rule | 0 / 88 | 0.000 | n/a | 0 / 168 = 0.00 per 1,000 | 0 | 0 | 0 / 99 | 0.0% | 100.0% |
| `test_diagnostic` | always-allow | 0 / 88 | 0.000 | n/a | 0 / 168 = 0.00 per 1,000 | 0 | 0 | 0 / 99 | 0.0% | 100.0% |

Email precision of 1.000 on a policy row is forced by zero observed false warnings; it is not an estimate of precision in use. At the exact upper 95% false-positive rate and the assumed 0.5% prevalence, precision would be 0.685 on `validation_product_like` and 0.709 on `test_product_like`. See [uncertainty and prevalence](UNCERTAINTY_AND_PREVALENCE.md).

The confidence bound on `validation_product_like` is not independent confirmation of the budget, because that subset selected the cutoff. Only the one `test_product_like` pass can support or fail AC01.

The rules policy uses the same selection rule on `validation_product_like` and gets cutoff 0.6667. It is a comparison for AC02 only. Always-allow is the floor.

## Confusion counts

| Subset | Email TP | Email FP | Email FN | Email TN | Recipient TP | Recipient FP | Recipient FN | Recipient TN | Recipient recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` | 8 | 0 | 12 | 3980 | 9 | 0 | 13 | 4948 | 0.409 |
| `validation_diagnostic` | 33 | 0 | 47 | 160 | 38 | 0 | 52 | 492 | 0.422 |
| `test_product_like` | 9 | 0 | 21 | 5970 | 11 | 0 | 22 | 7441 | 0.333 |
| `test_diagnostic` | 37 | 0 | 51 | 168 | 44 | 0 | 55 | 518 | 0.444 |

## Intervals

| Subset | False interventions per 1,000, exact 95% | Same, family bootstrap | Email recall, exact 95% | Email recall, family bootstrap |
| --- | --- | --- | --- | --- |
| `validation_product_like` | [0.00, 0.93] | no upper bound: a zero count resamples to [0.00, 0.00] in all 1000 draws | [0.191, 0.639] | [0.176, 0.632] (1000 draws kept) |
| `validation_diagnostic` | not valid (shared families) | no upper bound: a zero count resamples to [0.00, 0.00] in all 1000 draws | not valid (shared families) | [0.303, 0.519] (1000 draws kept) |
| `test_product_like` | [0.00, 0.62] | no upper bound: a zero count resamples to [0.00, 0.00] in all 1000 draws | [0.147, 0.494] | [0.130, 0.476] (1000 draws kept) |
| `test_diagnostic` | not valid (shared families) | no upper bound: a zero count resamples to [0.00, 0.00] in all 1000 draws | not valid (shared families) | [0.321, 0.528] (1000 draws kept) |

The family bootstrap of a zero count is always [0, 0]. It says nothing about an upper bound. The exact interval treats emails as independent, which holds on product-like subsets because each family has one draft. See [uncertainty and prevalence](UNCERTAINTY_AND_PREVALENCE.md).

## Precision–recall curves

Average precision is carried forward from the frozen risk score. The marked point is the frozen cutoff.

| Subset | Email AP | Email AP, family bootstrap | Recipient AP | Curve |
| --- | --- | --- | --- | --- |
| `validation_product_like` | 0.831 | [0.676, 0.954] | 0.820 | ![PR curve](figures/pr_validation_product_like.svg) |
| `validation_diagnostic` | 0.949 | [0.911, 0.977] | 0.948 | ![PR curve](figures/pr_validation_diagnostic.svg) |
| `test_product_like` | 0.741 | [0.582, 0.867] | 0.748 | ![PR curve](figures/pr_test_product_like.svg) |
| `test_diagnostic` | 0.938 | [0.902, 0.968] | 0.936 | ![PR curve](figures/pr_test_diagnostic.svg) |

## Slices

Counts are at the frozen cutoff. A warning on S03, S05, S06, or S07 is a false positive.

### `validation_product_like`

| Recipient slice | Rows | Unintended | Flagged unintended | Intended | Flagged intended |
| --- | --- | --- | --- | --- | --- |
| internal: external | 237 | 6 | 5 | 231 | 0 |
| internal: internal | 4733 | 16 | 4 | 4717 | 0 |
| contact: familiar | 4938 | 20 | 9 | 4918 | 0 |
| contact: new | 32 | 2 | 0 | 30 | 0 |

| Email slice | Emails | Misdirected | Warned misdirected | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| recipients: 1 | 3600 | 11 | 1 | 3589 | 0 | 3600 |
| recipients: 2 | 100 | 3 | 2 | 97 | 0 | 100 |
| recipients: 3-4 | 264 | 0 | 0 | 264 | 0 | 264 |
| recipients: 5+ | 36 | 6 | 5 | 30 | 0 | 36 |
| unintended recipients: 0 | 3980 | 0 | 0 | 3980 | 0 | 3980 |
| unintended recipients: 1 | 18 | 18 | 6 | 0 | 0 | 18 |
| unintended recipients: 2+ | 2 | 2 | 2 | 0 | 0 | 2 |

| Scenario | Emails | Misdirected | Warned misdirected (scenario recall) | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | 4 | 4 | 0 / 4 | 0 | 0 | 4 |
| S02 | 4 | 4 | 3 / 4 | 0 | 0 | 4 |
| S03 | 10 | 0 | — | 10 | 0 | 10 |
| S04 | 4 | 4 | 0 / 4 | 0 | 0 | 4 |
| S05 | 319 | 0 | — | 319 | 0 | 319 |
| S06 | 10 | 0 | — | 10 | 0 | 10 |
| S07 | 10 | 0 | — | 10 | 0 | 10 |
| S08 | 5 | 5 | 4 / 5 | 0 | 0 | 5 |
| S09 | 11 | 1 | 1 / 1 | 10 | 0 | 11 |
| S11 | 2 | 2 | 0 / 2 | 0 | 0 | 2 |
| routine | 3621 | 0 | — | 3621 | 0 | 3621 |

### `validation_diagnostic`

| Recipient slice | Rows | Unintended | Flagged unintended | Intended | Flagged intended |
| --- | --- | --- | --- | --- | --- |
| internal: external | 45 | 25 | 16 | 20 | 0 |
| internal: internal | 537 | 65 | 22 | 472 | 0 |
| contact: familiar | 532 | 80 | 38 | 452 | 0 |
| contact: new | 50 | 10 | 0 | 40 | 0 |

| Email slice | Emails | Misdirected | Warned misdirected | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| recipients: 1 | 129 | 40 | 10 | 89 | 0 | 99 |
| recipients: 2 | 26 | 9 | 0 | 17 | 0 | 26 |
| recipients: 3-4 | 39 | 0 | 0 | 39 | 0 | 39 |
| recipients: 5+ | 46 | 31 | 23 | 15 | 0 | 41 |
| unintended recipients: 0 | 160 | 0 | 0 | 160 | 0 | 160 |
| unintended recipients: 1 | 70 | 70 | 23 | 0 | 0 | 70 |
| unintended recipients: 2+ | 10 | 10 | 10 | 0 | 0 | 10 |

| Scenario | Emails | Misdirected | Warned misdirected (scenario recall) | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | 20 | 10 | 0 / 10 | 10 | 0 | 10 |
| S02 | 20 | 10 | 1 / 10 | 10 | 0 | 10 |
| S03 | 10 | 0 | — | 10 | 0 | 10 |
| S04 | 20 | 10 | 0 / 10 | 10 | 0 | 10 |
| S05 | 20 | 0 | — | 20 | 0 | 20 |
| S06 | 10 | 0 | — | 10 | 0 | 10 |
| S07 | 10 | 0 | — | 10 | 0 | 10 |
| S08 | 70 | 30 | 22 / 30 | 40 | 0 | 40 |
| S09 | 40 | 10 | 10 / 10 | 30 | 0 | 30 |
| S11 | 20 | 10 | 0 / 10 | 10 | 0 | 10 |

### `test_product_like`

| Recipient slice | Rows | Unintended | Flagged unintended | Intended | Flagged intended |
| --- | --- | --- | --- | --- | --- |
| internal: external | 377 | 10 | 6 | 367 | 0 |
| internal: internal | 7097 | 23 | 5 | 7074 | 0 |
| contact: familiar | 7421 | 30 | 11 | 7391 | 0 |
| contact: new | 53 | 3 | 0 | 50 | 0 |

| Email slice | Emails | Misdirected | Warned misdirected | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| recipients: 1 | 5388 | 16 | 2 | 5372 | 0 | 5388 |
| recipients: 2 | 156 | 5 | 1 | 151 | 0 | 156 |
| recipients: 3-4 | 406 | 0 | 0 | 406 | 0 | 406 |
| recipients: 5+ | 50 | 9 | 6 | 41 | 0 | 50 |
| unintended recipients: 0 | 5970 | 0 | 0 | 5970 | 0 | 5970 |
| unintended recipients: 1 | 27 | 27 | 6 | 0 | 0 | 27 |
| unintended recipients: 2+ | 3 | 3 | 3 | 0 | 0 | 3 |

| Scenario | Emails | Misdirected | Warned misdirected (scenario recall) | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | 6 | 6 | 0 / 6 | 0 | 0 | 6 |
| S02 | 6 | 6 | 2 / 6 | 0 | 0 | 6 |
| S03 | 15 | 0 | — | 15 | 0 | 15 |
| S04 | 5 | 5 | 0 / 5 | 0 | 0 | 5 |
| S05 | 496 | 0 | — | 496 | 0 | 496 |
| S06 | 15 | 0 | — | 15 | 0 | 15 |
| S07 | 15 | 0 | — | 15 | 0 | 15 |
| S08 | 8 | 8 | 5 / 8 | 0 | 0 | 8 |
| S09 | 22 | 2 | 2 / 2 | 20 | 0 | 22 |
| S11 | 3 | 3 | 0 / 3 | 0 | 0 | 3 |
| routine | 5409 | 0 | — | 5409 | 0 | 5409 |

### `test_diagnostic`

| Recipient slice | Rows | Unintended | Flagged unintended | Intended | Flagged intended |
| --- | --- | --- | --- | --- | --- |
| internal: external | 50 | 28 | 19 | 22 | 0 |
| internal: internal | 567 | 71 | 25 | 496 | 0 |
| contact: familiar | 562 | 88 | 44 | 474 | 0 |
| contact: new | 55 | 11 | 0 | 44 | 0 |

| Email slice | Emails | Misdirected | Warned misdirected | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| recipients: 1 | 141 | 44 | 11 | 97 | 0 | 108 |
| recipients: 2 | 26 | 9 | 0 | 17 | 0 | 26 |
| recipients: 3-4 | 39 | 0 | 0 | 39 | 0 | 39 |
| recipients: 5+ | 50 | 35 | 26 | 15 | 0 | 43 |
| unintended recipients: 0 | 168 | 0 | 0 | 168 | 0 | 168 |
| unintended recipients: 1 | 77 | 77 | 26 | 0 | 0 | 76 |
| unintended recipients: 2+ | 11 | 11 | 11 | 0 | 0 | 11 |

| Scenario | Emails | Misdirected | Warned misdirected (scenario recall) | Legitimate | Warned legitimate | Families |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | 21 | 11 | 0 / 11 | 10 | 0 | 11 |
| S02 | 21 | 11 | 2 / 11 | 10 | 0 | 11 |
| S03 | 11 | 0 | — | 11 | 0 | 11 |
| S04 | 21 | 11 | 0 / 11 | 10 | 0 | 11 |
| S05 | 22 | 0 | — | 22 | 0 | 22 |
| S06 | 11 | 0 | — | 11 | 0 | 11 |
| S07 | 11 | 0 | — | 11 | 0 | 11 |
| S08 | 74 | 33 | 24 / 33 | 41 | 0 | 41 |
| S09 | 43 | 11 | 11 / 11 | 32 | 0 | 33 |
| S11 | 21 | 11 | 0 / 11 | 10 | 0 | 11 |

## Legitimate first contacts and the paired check

| Subset | Intended first-contact rows | Flagged | Max risk score | Unintended rows | Flagged as stored | Flagged after first-contact rewrite | Median before | Median after |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` | 30 | 0 | 0.99737 | 22 | 9 | 9 | 0.9940 | 0.9986 |
| `validation_diagnostic` | 40 | 0 | 0.99853 | 90 | 38 | 51 | 0.9980 | 1.0000 |
| `test_product_like` | 50 | 0 | 0.99563 | 33 | 11 | 14 | 0.9927 | 0.9985 |
| `test_diagnostic` | 44 | 0 | 0.99705 | 99 | 44 | 57 | 0.9990 | 1.0000 |

The rewrite removes pair history and pair text from each unintended row. AC07: **insufficient evidence**. Wrong interventions on the legitimate-novelty scenarios: `validation_product_like` 0 of 349 S03/S05/S06/S07 emails warned, S11 0 of 2 warned; `validation_diagnostic` 0 of 50 S03/S05/S06/S07 emails warned, S11 0 of 10 warned; `test_product_like` 0 of 541 S03/S05/S06/S07 emails warned, S11 0 of 3 warned; `test_diagnostic` 0 of 55 S03/S05/S06/S07 emails warned, S11 0 of 11 warned. Those allows are the desired outcome, but legitimate first contacts score close to the cutoff (highest 0.99737 on `validation_product_like` against `T_warn` 0.99968), and removing pair history from a familiar mistake raises its risk score. The report cannot show that novelty is weighed only with other signals rather than setting a score near the cutoff by itself.

## Calibration

`calibration: not_fit`. validation_product_like has 20 misdirected emails. Separate chronological portions for calibration and threshold selection would leave about 10 positives in each, too few to fit a calibrator and still choose a cutoff. validation_diagnostic is not the operating mix and train fit the model. A reliability table on validation_diagnostic is a shape check only.

| Risk score bin | Rows | Mean risk score | Observed unintended fraction |
| --- | --- | --- | --- |
| 0.0–0.1 | 463 | 0.001 | 0.002 |
| 0.1–0.2 | 6 | 0.148 | 0.500 |
| 0.2–0.3 | 6 | 0.259 | 0.000 |
| 0.3–0.4 | 6 | 0.350 | 0.333 |
| 0.4–0.5 | 1 | 0.485 | 1.000 |
| 0.5–0.6 | 1 | 0.548 | 1.000 |
| 0.6–0.7 | 2 | 0.656 | 1.000 |
| 0.7–0.8 | 2 | 0.710 | 0.500 |
| 0.8–0.9 | 4 | 0.852 | 0.500 |
| 0.9–1.0 | 91 | 0.987 | 0.846 |

This table is on `validation_diagnostic`, which is not the 0.5% operating mix. It is a shape check. Most rows fall in the lowest and highest bins; read each bin's row count before its fraction.

## Latency (AC05)

Measured once at the API boundary for this policy bundle (`artifacts/med-api-latency/med-policy-v2/latency.json`): 4000 `POST /assess` calls on `validation_product_like` after 20 warm-up calls, one in flight. Client p50 26.84 ms, p95 57.04 ms against a 300 ms target: AC05 **met** on this machine. Details, workload, and hardware are in [the Phase 6 scoring flow](../phase_6/SCORING_FLOW.md#latency-ac05).

## Synthetic shortcuts

Read every recall figure in this phase next to these limits of the synthetic data and the frozen scorer:

- **Content signal.** The scorer uses all features, content cosine included. On train, content cosine alone separates mistakes from ordinary mail with separation 0.932 (the eligibility audit flags a feature only beyond 0.95). The same-family behavior-only model has product-like validation email average precision 0.467 against 0.831 for the scorer. S01, S04, and S11 outcomes by subset: `validation_product_like`: S01 0 of 4 warned, S04 0 of 4 warned, S11 0 of 2 warned; `validation_diagnostic`: S01 0 of 10 warned, S04 0 of 10 warned, S11 0 of 10 warned; `test_product_like`: S01 0 of 6 warned, S04 0 of 5 warned, S11 0 of 3 warned; `test_diagnostic`: S01 0 of 11 warned, S04 0 of 11 warned, S11 0 of 11 warned. The drafts are listed in the [error analysis](ERROR_ANALYSIS.md).
- **Five-minute recency.** 0 of 4948 legitimate recipient rows on `validation_product_like` had earlier mail between the sender and that recipient under five minutes before the draft; 1 of 22 unintended rows did.
- **First contacts.** Rewriting the 22 unintended `validation_product_like` rows as first contacts (no pair history, no pair text) moves their median risk score from 0.9940 to 0.9986; 9 are flagged as stored and 9 after the rewrite. The 30 intended first-contact rows reach a highest risk score of 0.99737, just below `T_warn`, and none is flagged. Legitimate first contacts are among the highest-scoring legitimate rows; the high cutoff, not the score, keeps them allowed.
- **Few positives.** `validation_product_like` has 20 misdirected emails and `test_product_like` has 30. Recall intervals are wide.
- **Weak regularization.** The scorer is logistic regression with `C = 1000`, the top edge of its training grid. Coefficients on overlapping counts are not separate effects.
