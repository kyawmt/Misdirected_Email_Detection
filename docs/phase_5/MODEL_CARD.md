# Phase 5 — Model card

## Intended use

Rank recipients of a fictional draft email by **risk score** of being unintended, and warn before a simulated send when the email risk score reaches the frozen cutoff. The corpus is synthetic, on reserved `.example` domains. This card describes a simulation, not a deployable product.

## Out of scope

Real mail, blocking, probability interpretation of scores, reason-code text, duplicate-address merging, distribution lists, and any prevalence other than the simulated mix.

## Frozen bundle

| Component | Version |
| --- | --- |
| Dataset | `med-synth-v2` |
| Features | `med-features-v1` |
| Model | `med-model-v1` (`logistic_behavior_only_unweighted`, logistic regression, `C = 100`, unweighted, behavior-only) |
| Policy | `med-policy-v1`, `T_warn = 0.134557`, blocking disabled, calibration not fit |
| Seed | 20260926 |

## Metrics at the frozen cutoff

| Subset | Warned mistakes | False interventions | Email AP | Emails |
| --- | --- | --- | --- | --- |
| `validation_product_like` | 4 / 5 | 0 / 995 = 0.00 per 1,000 | 0.891 | 1000 |
| `validation_diagnostic` | 20 / 28 | 0 / 36 = 0.00 per 1,000 | 0.977 | 64 |
| `test_product_like` | 5 / 10 | 0 / 1990 = 0.00 per 1,000 | 0.622 | 2000 |
| `test_diagnostic` | 25 / 35 | 0 / 44 = 0.00 per 1,000 | 0.959 | 79 |

Diagnostic subsets are scenario challenge sets and not the operating mix. Intervals are in the [evaluation report](EVALUATION_REPORT.md).

## Acceptance status

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC01 | **insufficient evidence** | The point estimate is 0.00 per 1,000 (0 of 1990), which meets the budget only provisionally. The exact upper 95% bound is 1.85 per 1,000, above 1. With 1990 legitimate emails, even zero false warnings cannot put the upper bound at or below the budget. |
| AC02 | **met only for S02, S08; not met for S01, S04** | On this simulation only, on `test_product_like`: 5 of 10 misdirected emails warned (S02 3, S08 2; 5 to 6 recipients; risk scores 0.999 to 1) with 0 false interventions; exact 95% recall interval [0.187, 0.813]. Missed: S01 3, S04 2; 1 recipient each; risk scores 0.00331 to 0.0149. Always-allow warns on none. The rules policy under the same validation rule warned 2 with 3 false interventions (1.51 per 1,000), which is outside the budget on this test. |
| AC03 | **met** | T_warn was chosen on validation_product_like only, written to policy.json before any test label was read, and applied once to the frozen test. The policy checksum is stored in test_evaluation.json. |
| AC04 | **met** | Blocking is disabled. T_block is null and the block count is 0 on every subset. |

## Failure modes

- A mistaken first contact scores near 0 and is allowed.
- Lookalike replacements (S01) and familiar-recipient, unusual-topic mistakes (S04) are missed, because the scorer leaves content out.
- The cutoff sits just above the highest legitimate validation score, so a small drift in legitimate scores adds false warnings.
- Part of the score reflects generator timing (sub-five-minute repeat mail).
- A missing or mismatched policy or model returns `unable_to_assess`; it never allows.

Read every recall figure in this phase next to these limits of the synthetic data and the frozen scorer:

- **Content shortcut.** An all-features logistic model reaches email average precision 1.000 on `validation_product_like` because content cosine restates the generator's per-relationship topics. The frozen scorer is behavior-only and does not use it, so lookalike replacements (S01) and familiar-recipient, unusual-topic mistakes (S04) are mostly missed: `validation_product_like`: S01 0 warned / 1 missed, S04 1 warned / 0 missed; `validation_diagnostic`: S01 0 warned / 4 missed, S04 0 warned / 4 missed; `test_product_like`: S01 0 warned / 3 missed, S04 0 warned / 2 missed; `test_diagnostic`: S01 0 warned / 5 missed, S04 0 warned / 5 missed. The drafts are listed in the [error analysis](ERROR_ANALYSIS.md).
- **Five-minute burst.** 1543 of 2259 legitimate recipient rows on `validation_product_like` had earlier mail to the same recipient under five minutes before the draft; 0 of 6 unintended rows did. Part of the behavior-only risk score is that generator timing.
- **First contact near 0.** Rewriting the 6 unintended `validation_product_like` rows as first contacts moves their median risk score from 0.9998 to 5.3e-08; 0 of them would still be flagged. This version cannot warn on a mistaken first contact.
- **Few positives.** `validation_product_like` has 5 misdirected emails and `test_product_like` has 10. Recall intervals are wide.
- **Unregularized fit.** The scorer is logistic regression with `C = 100`, the top of its training grid. Coefficients on overlapping counts are not separate effects.
