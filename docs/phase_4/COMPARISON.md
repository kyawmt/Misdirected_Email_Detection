# Phase 4 — Baseline and challenger comparison

Always-allow scores every recipient 0. The rules score is the mean of three behavioral checks and cannot reach 1 from one check. Logistic regression and one depth-limited tree are the learned models. Fusion is an equal-weight sum of the three rule checks plus a content term. It is not a behavior-only model.

The tree is a single decision tree rather than a boosted ensemble so the novelty split can be read. Its depth and leaf size are the only tuned settings. Class weight for the tree is fixed at balanced.

| Run | Ablation | Product-like email AP | Product-like recipient AP | Diagnostic email AP | CV email AP | Fit seconds | Score seconds / 1,000 rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `always_allow` | none | 0.005 [0.003, 0.007] (20 pos / 4000) | 0.004 [0.002, 0.007] (22 pos / 4970) | 0.333 [0.298, 0.368] (80 pos / 240) | 0.099 | 0.000 | 0.0000 |
| `rules` | behavior_only | 0.036 [0.006, 0.161] (20 pos / 4000) | 0.034 [0.006, 0.151] (22 pos / 4970) | 0.515 [0.432, 0.603] (80 pos / 240) | 0.310 | 0.000 | 0.0000 |
| `fusion` | fusion | 0.424 [0.200, 0.707] (20 pos / 4000) | 0.407 [0.195, 0.651] (22 pos / 4970) | 0.730 [0.624, 0.829] (80 pos / 240) | 0.685 | 0.000 | 0.0000 |
| `logistic_all_unweighted` | all | 0.883 [0.754, 0.976] (20 pos / 4000) | 0.858 [0.731, 0.960] (22 pos / 4970) | 0.961 [0.931, 0.983] (80 pos / 240) | 0.943 | 0.028 | 0.0003 |
| `logistic_all_balanced` | all | 0.831 [0.676, 0.954] (20 pos / 4000) | 0.820 [0.667, 0.942] (22 pos / 4970) | 0.949 [0.911, 0.977] (80 pos / 240) | 0.947 | 0.046 | 0.0002 |
| `tree_all` | all | 0.276 [0.156, 0.419] (20 pos / 4000) | 0.265 [0.155, 0.399] (22 pos / 4970) | 0.733 [0.643, 0.823] (80 pos / 240) | 0.818 | 0.009 | 0.0002 |
| `logistic_behavior_only_unweighted` | behavior_only | 0.494 [0.253, 0.710] (20 pos / 4000) | 0.502 [0.258, 0.710] (22 pos / 4970) | 0.852 [0.794, 0.906] (80 pos / 240) | 0.692 | 0.018 | 0.0002 |
| `logistic_behavior_only_balanced` | behavior_only | 0.467 [0.223, 0.688] (20 pos / 4000) | 0.486 [0.231, 0.694] (22 pos / 4970) | 0.854 [0.795, 0.904] (80 pos / 240) | 0.689 | 0.019 | 0.0002 |
| `tree_behavior_only` | behavior_only | 0.459 [0.230, 0.686] (20 pos / 4000) | 0.466 [0.237, 0.677] (22 pos / 4970) | 0.775 [0.699, 0.836] (80 pos / 240) | 0.541 | 0.009 | 0.0002 |

Behavior-only rows drop `content_cosine`, `content_similarity_observed`, and `pair_text_message_count`. All-features rows keep them. Whether an all-features model may be selected is decided by the recorded eligibility checks in the [decision record](DECISION_RECORD.md), not by this table. Unobserved recency is imputed with the training median and then log-transformed, so the 3650-day fallback is not a raw input.
