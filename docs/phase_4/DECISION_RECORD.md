# Phase 4 — Model selection

## Rule

Choose the simplest behavior-only model whose email-level average precision on `validation_product_like` falls inside the family bootstrap interval of the best behavior-only model on that same metric. Rules are simpler than logistic regression. Logistic regression is simpler than the tree. When two models are equally simple, the higher mean email average precision from the training folds wins. That tie-break does not use the validation point estimate. Always-allow is the floor and is not eligible. Fusion, the recency-floor diagnostic, and the dropped-rate diagnostic are not eligible.

The rule selects `logistic_behavior_only_unweighted`.

On `validation_product_like` its email average precision is 0.891 [0.583, 1.000] (5 positive emails out of 1000). On `validation_diagnostic` it is 0.977 [0.948, 0.998] (28 positive emails out of 64). The diagnostic figure is not a 0.5% prevalence result.

## Why this model

The highest behavior-only email average precision on product-like validation is `logistic_behavior_only_unweighted` at 0.891 [0.583, 1.000]. Outside that interval: `rules` at 0.410, `tree_behavior_only` at 0.029. Inside it: `logistic_behavior_only_unweighted`, `logistic_behavior_only_balanced`. `logistic_behavior_only_unweighted` and `logistic_behavior_only_balanced` are equally simple. The higher training-fold mean is kept, not the validation point estimate. It does not use the content cosine columns.

## Content features

The selected model does not use content cosine, the content-observed flag, or the pair-text count. `logistic` email average precision on product-like validation is 0.891 [0.583, 1.000] without those content columns and 1.000 [1.000, 1.000] with all features. `tree` email average precision on product-like validation is 0.029 [0.006, 0.057] without those content columns and 1.000 [1.000, 1.000] with all features.

## First contact

On product-like validation, the 6 unintended recipient rows have median risk 0.9998. Rewriting each of those rows as a first contact for the same sender (no pair counts, novelty on, recency marked unobserved) moves the median to 0.0000. Unobserved recency is replaced with the median observed recency on the fitting rows, 1.0 minutes, and then log-transformed. The old 3650-day fallback is not a raw input. This version still assigns essentially no risk to a mistaken first contact. On the diagnostic subset the same rewrite moves the positive median from 0.9998 to 0.0000 (32 positive rows).

## Recency

Legitimate rows often have another message to the same recipient less than five minutes earlier. That share is 66.5% of 2212 legitimate training rows and 68.3% of 2259 legitimate product-like validation rows. No misdirected row in those sets is that recent. The shortest misdirected gap is 0.027 days in train and 0.888 days on product-like validation. The generator writes some legitimate mail in one-minute bursts, so recency is partly a timing artifact. A diagnostic behavior-only logistic model floors recency at one day before the log. Its product-like email average precision is 0.731 [0.181, 1.000]. It is not a selection candidate.

## Coefficients

The selected logistic `C` is 100.0. The train grid is 0.01, 0.1, 1, 10, and 100. Tuning stopped on the top edge, so the fit is the least regularized point in that grid. The largest standardized coefficients are `pair_outbound_rate_per_day` -25.57, `pair_outbound_count` +9.52, `pair_inbound_count` +5.68, `pair_outbound_count_28d` -5.65, `pair_inbound_count_28d` -5.30, `co_focus_conditional_fraction` -3.77. Those weights sit on overlapping count features and are not separate effects. A single coefficient, including the novelty coefficient, is not a behavioral finding. Dropping `pair_outbound_rate_per_day` and refitting on train gives product-like email average precision 0.826 [0.383, 1.000]. That run is a collinearity check, not a selection candidate.

## Tree scores

The behavior-only tree writes 2 distinct scores on product-like validation. Its 6 positive recipient rows share the score 0.928 with 170 legitimate rows in that same score. Average precision counts those ties as a mixed leaf, so the low number is a tie penalty, not a separate story about what the tree learned. Train-fold mean email average precision was 0.520. The rejection stands.

## Novelty coefficient

`logistic_behavior_only_unweighted` has a standardized coefficient of -0.1274 on `recipient_novel_to_sender` (negative). That coefficient is not a behavioral finding. The paired first-contact scores are the check. `logistic_behavior_only_balanced` has a standardized coefficient of -0.5167 on `recipient_novel_to_sender` (negative). That coefficient is not a behavioral finding. The paired first-contact scores are the check. `tree_behavior_only` does not split on `recipient_novel_to_sender` (importance 0.0000).

## Rejected options

- `rules` email average precision 0.410 [0.004, 1.000] on product-like validation.
- `logistic_behavior_only_balanced` email average precision 0.724 [0.147, 1.000] on product-like validation.
- `tree_behavior_only` email average precision 0.029 [0.006, 0.057] on product-like validation.

## Limitations

- Content cosine almost separates training mistakes from ordinary repeat mail because relationships keep separate topics. An all-features or content-only score restates that generator.
- No training row is a misdirected first contact. The paired score check is the evidence for how this model treats one, not the sign of a single coefficient.
- Many legitimate rows have another message to the same recipient less than five minutes earlier, and no misdirected row does. Part of the behavior-only score is that generator timing.
- `validation_product_like` has 5 misdirected emails. Intervals are wide. A gap smaller than an interval is not a ranking.
- The training mix is 10% misdirected. Precision at that mix is not an operating point. Product-like prevalence is a 0.5% simulation assumption.
- Scores are risk scores. Nothing was calibrated. No threshold was selected. The frozen test subsets were not scored.
- AC01, AC02, and AC05 were not measured.
