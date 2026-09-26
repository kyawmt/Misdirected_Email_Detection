# Phase 4 — Baseline and challenger comparison

Always-allow scores every recipient 0. The rules score is the mean of three behavioral checks and cannot reach 1 from one check. Logistic regression and one depth-limited tree are the learned models. Fusion is an equal-weight sum of the three rule checks plus a content term. It is not a behavior-only model.

The tree is a single decision tree rather than a boosted ensemble so the novelty split can be read. Its depth and leaf size are the only tuned settings. Class weight for the tree is fixed at balanced.

| Run | Ablation | Product-like email AP | Product-like recipient AP | Diagnostic email AP | CV email AP | Fit seconds | Score seconds / 1,000 rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `always_allow` | none | 0.005 [0.001, 0.010] (5 pos / 1000) | 0.003 [0.000, 0.005] (6 pos / 2265) | 0.438 [0.390, 0.478] (28 pos / 64) | 0.092 | 0.000 | 0.0000 |
| `rules` | behavior_only | 0.410 [0.004, 1.000] (5 pos / 1000) | 0.348 [0.004, 0.679] (6 pos / 2265) | 0.712 [0.590, 0.825] (28 pos / 64) | 0.298 | 0.000 | 0.0001 |
| `fusion` | fusion | 0.806 [0.416, 1.000] (5 pos / 1000) | 0.839 [0.431, 1.000] (6 pos / 2265) | 0.939 [0.885, 0.981] (28 pos / 64) | 0.757 | 0.000 | 0.0001 |
| `logistic_all_unweighted` | all | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.996 | 0.006 | 0.0003 |
| `logistic_all_balanced` | all | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.997 | 0.006 | 0.0003 |
| `tree_all` | all | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.954 | 0.004 | 0.0003 |
| `logistic_behavior_only_unweighted` | behavior_only | 0.891 [0.583, 1.000] (5 pos / 1000) | 0.917 [0.583, 1.000] (6 pos / 2265) | 0.977 [0.948, 0.998] (28 pos / 64) | 0.841 | 0.022 | 0.0003 |
| `logistic_behavior_only_balanced` | behavior_only | 0.724 [0.147, 1.000] (5 pos / 1000) | 0.783 [0.147, 1.000] (6 pos / 2265) | 0.996 [0.985, 1.000] (28 pos / 64) | 0.824 | 0.027 | 0.0003 |
| `tree_behavior_only` | behavior_only | 0.029 [0.006, 0.057] (5 pos / 1000) | 0.034 [0.006, 0.070] (6 pos / 2265) | 0.800 [0.676, 0.926] (28 pos / 64) | 0.520 | 0.004 | 0.0003 |

Behavior-only rows drop `content_cosine`, `content_similarity_observed`, and `pair_text_message_count`. All-features rows keep them. On this generator the all-features gain is the topic shortcut, not a product result. Unobserved recency is imputed with the training median and then log-transformed, so the old 3650-day fallback is not a raw input.
