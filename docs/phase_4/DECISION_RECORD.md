# Phase 4 — Model selection

Model bundle `med-model-v2`. Dataset `med-synth-v4`. Features `med-features-v2`.

## Rule

Choose the simplest eligible model whose email-level average precision on `validation_product_like` falls inside the family bootstrap interval of the best eligible model on that same metric. Rules are simpler than logistic regression. Logistic regression is simpler than the tree. When two models are equally simple, the higher mean email average precision from the training folds wins. That tie-break does not use the validation point estimate. Always-allow is the floor and is not eligible. Fusion and the diagnostic runs (recency floor, dropped rate) are not eligible.

Behavior-only models are always eligible. An all-features model is eligible only if the checks in the next section hold for its model family.

## Eligibility of all-features models

An all-features model is a selection candidate only if (1) the train shortcut audit flags no content feature, (2) it beats the behavior-only model of the same family in every chronological train fold, and (3) it beats the content-only model of the same family in every train fold. Otherwise behavior-only selection stands. Validation is not used for these checks.

Check 1, train shortcut audit (from the feature artifact): content features `content_cosine` AUC 0.068 (separation 0.932), `content_similarity_observed` AUC 0.459 (separation 0.541), `pair_text_message_count` AUC 0.525 (separation 0.525). Flag bounds are 0.05 and 0.95. No content feature is flagged, so the check passes.

Checks 2 and 3 compare email average precision fold by fold on the expanding chronological train folds, each model at its own tuned setting. A margin is all-features minus the other model on that fold.

| Family | All-features run | Check 2: min margin over behavior-only (per fold) | Check 3: min margin over content-only (per fold) | Checks passed | Eligible |
| --- | --- | --- | --- | --- | --- |
| logistic_unweighted | `logistic_all_unweighted` | +0.229 (+0.241, +0.281, +0.229) | +0.040 (+0.116, +0.134, +0.040) | audit, fold_stability, not_content_alone | yes |
| logistic_balanced | `logistic_all_balanced` | +0.234 (+0.257, +0.282, +0.234) | +0.117 (+0.214, +0.223, +0.117) | audit, fold_stability, not_content_alone | yes |
| tree | `tree_all` | +0.191 (+0.384, +0.191, +0.255) | +0.015 (+0.033, +0.015, +0.095) | audit, fold_stability, not_content_alone | yes |

Train-fold mean email average precision by ablation, with the product-like validation figure beside it for reference only:

| Family | All | Behavior-only | Content-only | Drop content (all text) | Drop similarity |
| --- | --- | --- | --- | --- | --- |
| logistic_unweighted | 0.943 (val 0.883) | 0.692 (val 0.494) | 0.846 (val 0.557) | 0.680 (val 0.456) | 0.944 (val 0.873) |
| logistic_balanced | 0.947 (val 0.831) | 0.689 (val 0.467) | 0.762 (val 0.300) | 0.676 (val 0.419) | 0.948 (val 0.898) |
| tree | 0.818 (val 0.276) | 0.541 (val 0.459) | 0.770 (val 0.220) | 0.541 (val 0.459) | 0.778 (val 0.186) |

## Selected model

The rule selects `logistic_all_balanced`.

On `validation_product_like` its email average precision is 0.831 [0.676, 0.954] (20 positive emails out of 4000). On `validation_diagnostic` it is 0.949 [0.911, 0.977] (80 positive emails out of 240). The diagnostic figure is not a 0.5% prevalence result.

## Why this model

The highest email average precision among eligible models on product-like validation is `logistic_all_unweighted` at 0.883 [0.754, 0.976]. Outside that interval: `rules` at 0.036, `tree_all` at 0.276, `logistic_behavior_only_unweighted` at 0.494, `logistic_behavior_only_balanced` at 0.467, `tree_behavior_only` at 0.459. Inside it: `logistic_all_unweighted`, `logistic_all_balanced`. `logistic_all_balanced` and `logistic_all_unweighted` are equally simple. The higher training-fold mean is kept, not the validation point estimate. The best behavior-only model is `logistic_behavior_only_unweighted` at 0.494 [0.253, 0.710].

## Content features

The selected model uses content features. It was a candidate only because its family passed the eligibility checks above; the behavior-only model of the same family is reported beside it. `logistic` email average precision on product-like validation is 0.494 [0.253, 0.710] without those content columns and 0.883 [0.754, 0.976] with all features. `tree` email average precision on product-like validation is 0.459 [0.230, 0.686] without those content columns and 0.276 [0.156, 0.419] with all features.

## First contact

On product-like validation, the 22 unintended recipient rows have median risk 0.9940. Rewriting each of those rows as a first contact for the same sender (no pair counts, novelty on, recency unobserved, no pair text) moves the median to 0.9986. Unobserved recency is replaced with the median observed recency on the fitting rows, 337.5 minutes, and then log-transformed. The old 3650-day fallback is not a raw input. The rewrite is a synthetic check; the S11 comparison below scores real mistaken first contacts. On the diagnostic subset the same rewrite moves the positive median from 0.9980 to 1.0000 (90 positive rows).

### Mistaken first contacts (S11) against legitimate first contacts (S03, S06)

Recipient-level risk scores, no cutoff applied. S11 rows are unintended recipients the sender had never emailed. Legitimate first-contact rows are intended S03 and S06 recipients who are novel to the sender. AUC is the chance that an S11 row outranks a legitimate first-contact row. No recall is reported here: recall needs the operating cutoff, which Phase 5 sets.

| Run | Subset | S11 rows | S11 median [p25, p75] | Legitimate first-contact rows | Legitimate median [p25, p75] | AUC | AP | S11 above every legitimate first contact | AUC against all other legitimate rows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `logistic_all_balanced` | `validation_product_like` | 2 | 0.954 [0.94, 0.968] | 20 | 0.406 [8.09e-28, 0.953] | 0.750 | 0.236 | 0 of 2 | 0.996 |
| `logistic_all_balanced` | `validation_diagnostic` | 10 | 0.996 [0.989, 0.998] | 20 | 0.461 [2.21e-27, 0.981] | 0.880 | 0.688 | 0 of 10 | 1.000 |
| `logistic_all_unweighted` | `validation_product_like` | 2 | 0.648 [0.644, 0.651] | 20 | 0.231 [6.12e-10, 0.495] | 0.900 | 0.417 | 0 of 2 | 1.000 |
| `logistic_all_unweighted` | `validation_diagnostic` | 10 | 0.75 [0.575, 0.848] | 20 | 0.172 [3.02e-10, 0.427] | 0.930 | 0.870 | 5 of 10 | 1.000 |
| `tree_all` | `validation_product_like` | 2 | 0.987 [0.987, 0.987] | 20 | 0.987 [0.987, 0.987] | 0.500 | 0.091 | 0 of 2 | 0.999 |
| `tree_all` | `validation_diagnostic` | 10 | 0.987 [0.987, 0.987] | 20 | 0.987 [0.987, 0.987] | 0.500 | 0.333 | 0 of 10 | 0.998 |
| `logistic_behavior_only_unweighted` | `validation_product_like` | 2 | 0.579 [0.492, 0.667] | 20 | 0.136 [1.79e-06, 0.56] | 0.750 | 0.267 | 0 of 2 | 1.000 |
| `logistic_behavior_only_unweighted` | `validation_diagnostic` | 10 | 0.819 [0.769, 0.825] | 20 | 0.212 [2.05e-06, 0.716] | 0.850 | 0.622 | 0 of 10 | 1.000 |
| `tree_behavior_only` | `validation_product_like` | 2 | 0.974 [0.974, 0.974] | 20 | 0.918 [0.862, 0.974] | 0.750 | 0.167 | 0 of 2 | 1.000 |
| `tree_behavior_only` | `validation_diagnostic` | 10 | 0.974 [0.974, 0.974] | 20 | 0.918 [0.862, 0.974] | 0.750 | 0.500 | 0 of 10 | 1.000 |

Product-like validation has only a handful of S11 and S03/S06 drafts, so its row is anecdotal. Diagnostic rows share families and are not independent.

## Recency

Share of recipient rows whose last mail between the sender and that recipient was less than five minutes before the draft: 0.0% of 3640 legitimate and 1.9% of 315 misdirected training rows; 0.0% of 4948 legitimate and 4.5% of 22 misdirected product-like validation rows. The shortest misdirected gap is 0.002 days in train. A diagnostic behavior-only logistic model floors recency at one day before the log. Its product-like email average precision is 0.501 [0.264, 0.726]. It is not a selection candidate.

## Coefficients

The selected logistic `C` is 1000. The train grid is 0.001, 0.01, 0.1, 1, 10, 100, 1000. Tuning stopped on the top edge of the grid, the least regularized point; the search may not have reached its best value. The largest standardized coefficients are `pair_text_message_count` -40.28, `pair_outbound_count_28d` +38.05, `pair_outbound_rate_per_day` -25.77, `pair_outbound_count` +24.72, `pair_inbound_count` +16.95, `pair_inbound_count_28d` -16.54. Extending the grid is a tuning change only; it does not remove collinearity, and a larger `C` can make correlated coefficients less stable. Weights on overlapping count features are not separate effects, and no single coefficient, including the novelty coefficient, is a behavioral finding. Dropping `pair_outbound_rate_per_day` and refitting on train gives product-like email average precision 0.483 [0.238, 0.703]. That run is a collinearity check, not a selection candidate.

## Tree scores

The behavior-only tree writes 6 distinct scores on product-like validation. Its 9 positive recipient rows share the score 1.000 with 0 legitimate rows in that same score. Average precision counts those ties as a mixed leaf, so the low number is a tie penalty, not a separate story about what the tree learned. Train-fold mean email average precision was 0.541. The rejection stands.

## Novelty coefficient

`logistic_all_balanced` has a standardized coefficient of 0.9379 on `recipient_novel_to_sender` (positive). That coefficient is not a behavioral finding. The paired first-contact scores are the check. `logistic_behavior_only_unweighted` has a standardized coefficient of 0.4953 on `recipient_novel_to_sender` (positive). That coefficient is not a behavioral finding. The paired first-contact scores are the check. `logistic_behavior_only_balanced` has a standardized coefficient of 0.5452 on `recipient_novel_to_sender` (positive). That coefficient is not a behavioral finding. The paired first-contact scores are the check. `tree_behavior_only` does not split on `recipient_novel_to_sender` (importance 0.0000).

## Rejected options

- `rules` email average precision 0.036 [0.006, 0.161] on product-like validation.
- `logistic_all_unweighted` email average precision 0.883 [0.754, 0.976] on product-like validation.
- `tree_all` email average precision 0.276 [0.156, 0.419] on product-like validation.
- `logistic_behavior_only_unweighted` email average precision 0.494 [0.253, 0.710] on product-like validation.
- `logistic_behavior_only_balanced` email average precision 0.467 [0.223, 0.688] on product-like validation.
- `tree_behavior_only` email average precision 0.459 [0.230, 0.686] on product-like validation.

## Limitations

- Content cosine is a real but strong train signal (separation 0.932). Off-topic mistakes (S02, S04) sit low on it by their scenario definitions, so a content model's gain on those scenarios partly restates how they were written.
- Recency under five minutes: 0.0% of legitimate and 1.9% of misdirected train rows.
- `validation_product_like` has 20 misdirected emails out of 4000. Intervals are wide. A gap smaller than an interval is not a ranking.
- The training mix is 10% misdirected. Precision at that mix is not an operating point. Product-like prevalence is a 0.5% simulation assumption.
- Scores are risk scores. Nothing was calibrated. No threshold was selected. The frozen test subsets were not scored.
- Coefficients on overlapping count features are not separate effects.
- AC01, AC02, and AC05 were not measured in this phase.
