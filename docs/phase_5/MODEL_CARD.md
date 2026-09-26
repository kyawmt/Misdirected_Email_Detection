# Phase 5 — Model card

## Intended use

Rank recipients of a fictional draft email by **risk score** of being unintended, and warn before a simulated send when the email risk score reaches the frozen cutoff. The corpus is synthetic, on reserved `.example` domains. This card describes a simulation, not a deployable product.

## Out of scope

Real mail, blocking, probability interpretation of scores, reason-code text, duplicate-address merging, distribution lists, and any prevalence other than the simulated mix.

## Frozen bundle

| Component | Version |
| --- | --- |
| Dataset | `med-synth-v4` |
| Features | `med-features-v2` |
| Model | `med-model-v2` (`logistic_all_balanced`, logistic regression, `C = 1000`, balanced, all features, content cosine included) |
| Policy | `med-policy-v2`, `T_warn = 0.999677`, blocking disabled, calibration not fit |
| Seed | 20260926 |

## Metrics at the frozen cutoff

| Subset | Warned mistakes | False interventions | Email AP | Emails |
| --- | --- | --- | --- | --- |
| `validation_product_like` | 8 / 20 | 0 / 3980 = 0.00 per 1,000 | 0.831 | 4000 |
| `validation_diagnostic` | 33 / 80 | 0 / 160 = 0.00 per 1,000 | 0.949 | 240 |
| `test_product_like` | 9 / 30 | 0 / 5970 = 0.00 per 1,000 | 0.741 | 6000 |
| `test_diagnostic` | 37 / 88 | 0 / 168 = 0.00 per 1,000 | 0.938 | 256 |

Diagnostic subsets are scenario challenge sets and not the operating mix. Intervals are in the [evaluation report](EVALUATION_REPORT.md).

## Acceptance status

| Criterion | Status | Evidence |
| --- | --- | --- |
| AC01 | **insufficient evidence** | Descriptive pass on this corpus: 0 false interventions on 5,970 legitimate `test_product_like` emails (0.00 per 1,000; warnings 9, blocks 0, coverage 100.0%, assumed prevalence 0.5%). The point estimate is within the budget of 1, which is provisional. The exact upper 95% bound is 0.62 per 1,000. The exact bound assumes independent emails. On `test_product_like`, 5,682 of 6,000 drafts come from one sender (19 senders in all), and routine drafts repeat generated communication patterns, so errors can be correlated by sender. One-draft families remove thread copies but do not establish independence, and a sender-clustered interval has no upper bound for a zero count. The confidence-supported claim needs an independence argument or a more independent evaluation, which would need a new frozen dataset version. The validation bound is not evidence either, because validation chose the cutoff. |
| AC02 | **met for S09; partly met for S02, S08; not met for S01, S04, S11** | On this simulation only, on `test_product_like`: 9 of 30 misdirected emails warned (S02 2, S08 5, S09 2; 1 to 7 recipients; risk scores 0.9997 to 1) with 0 false interventions; exact 95% recall interval [0.147, 0.494]. Missed: S01 6, S02 4, S04 5, S08 3, S11 3; 1 to 5 recipients; risk scores 0.1514 to 0.9985. Always-allow warns on none. The rules policy under the same validation rule warned 0 with 0 false interventions (0.00 per 1,000), within the budget on this test. |
| AC03 | **met** | T_warn was chosen on validation_product_like only, written to policy.json before any test label was read, and applied once to the frozen test. The policy checksum is stored in test_evaluation.json. |
| AC04 | **met** | Blocking is disabled. T_block is null and the block count is 0 on every subset. |

## Failure modes

- Mistaken first contacts (S11), lookalike replacements (S01), and familiar-recipient, unusual-topic mistakes (S04) are allowed at the frozen cutoff: `validation_product_like`: S01 0 of 4 warned, S04 0 of 4 warned, S11 0 of 2 warned; `validation_diagnostic`: S01 0 of 10 warned, S04 0 of 10 warned, S11 0 of 10 warned; `test_product_like`: S01 0 of 6 warned, S04 0 of 5 warned, S11 0 of 3 warned; `test_diagnostic`: S01 0 of 11 warned, S04 0 of 11 warned, S11 0 of 11 warned.
- Legitimate first contacts score just below the cutoff. A small drift in legitimate scores, or a new kind of legitimate first contact, would add false warnings.
- The cutoff sits just above the highest legitimate validation score, so it is tight by construction.
- Content cosine is an input. Off-topic mistakes are partly caught because the generator wrote them off-topic.
- An address that is not in the directory is `unable_to_assess`, not a warning. A missing or mismatched policy or model also returns `unable_to_assess`; it never allows.

Read every recall figure in this phase next to these limits of the synthetic data and the frozen scorer:

- **Content signal.** The scorer uses all features, content cosine included. On train, content cosine alone separates mistakes from ordinary mail with separation 0.932 (the eligibility audit flags a feature only beyond 0.95). The same-family behavior-only model has product-like validation email average precision 0.467 against 0.831 for the scorer. S01, S04, and S11 outcomes by subset: `validation_product_like`: S01 0 of 4 warned, S04 0 of 4 warned, S11 0 of 2 warned; `validation_diagnostic`: S01 0 of 10 warned, S04 0 of 10 warned, S11 0 of 10 warned; `test_product_like`: S01 0 of 6 warned, S04 0 of 5 warned, S11 0 of 3 warned; `test_diagnostic`: S01 0 of 11 warned, S04 0 of 11 warned, S11 0 of 11 warned. The drafts are listed in the [error analysis](ERROR_ANALYSIS.md).
- **Five-minute recency.** 0 of 4948 legitimate recipient rows on `validation_product_like` had earlier mail between the sender and that recipient under five minutes before the draft; 1 of 22 unintended rows did.
- **First contacts.** Rewriting the 22 unintended `validation_product_like` rows as first contacts (no pair history, no pair text) moves their median risk score from 0.9940 to 0.9986; 9 are flagged as stored and 9 after the rewrite. The 30 intended first-contact rows reach a highest risk score of 0.99737, just below `T_warn`, and none is flagged. Legitimate first contacts are among the highest-scoring legitimate rows; the high cutoff, not the score, keeps them allowed.
- **Few positives.** `validation_product_like` has 20 misdirected emails and `test_product_like` has 30. Recall intervals are wide.
- **Weak regularization.** The scorer is logistic regression with `C = 1000`, the top edge of its training grid. Coefficients on overlapping counts are not separate effects.
