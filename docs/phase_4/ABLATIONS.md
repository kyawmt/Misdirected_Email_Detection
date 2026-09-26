# Phase 4 — Ablations

Each learned ablation was tuned on `train` only, then scored once. Behavior-only is the comparison that does not use the content shortcut. Content-only is a diagnostic of that shortcut. `behavior_recency_floor` floors recency at one day. `behavior_drop_rate` removes `pair_outbound_rate_per_day`. Neither diagnostic enters model selection.

| Run | Ablation | Product-like email AP | Product-like recipient AP | Diagnostic email AP | CV email AP | Fit seconds | Score seconds / 1,000 rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `logistic_all_unweighted` | all | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.996 | 0.006 | 0.0003 |
| `logistic_all_balanced` | all | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.997 | 0.006 | 0.0003 |
| `tree_all` | all | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.954 | 0.004 | 0.0003 |
| `logistic_behavior_only_unweighted` | behavior_only | 0.891 [0.583, 1.000] (5 pos / 1000) | 0.917 [0.583, 1.000] (6 pos / 2265) | 0.977 [0.948, 0.998] (28 pos / 64) | 0.841 | 0.022 | 0.0003 |
| `logistic_behavior_only_balanced` | behavior_only | 0.724 [0.147, 1.000] (5 pos / 1000) | 0.783 [0.147, 1.000] (6 pos / 2265) | 0.996 [0.985, 1.000] (28 pos / 64) | 0.824 | 0.027 | 0.0003 |
| `tree_behavior_only` | behavior_only | 0.029 [0.006, 0.057] (5 pos / 1000) | 0.034 [0.006, 0.070] (6 pos / 2265) | 0.800 [0.676, 0.926] (28 pos / 64) | 0.520 | 0.004 | 0.0003 |
| `logistic_drop_relationship_unweighted` | drop_relationship | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.979 | 0.005 | 0.0002 |
| `logistic_drop_relationship_balanced` | drop_relationship | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.980 | 0.005 | 0.0002 |
| `tree_drop_relationship` | drop_relationship | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 0.982 [0.947, 1.000] (28 pos / 64) | 0.954 | 0.002 | 0.0002 |
| `logistic_drop_similarity_unweighted` | drop_similarity | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.976 | 0.007 | 0.0003 |
| `logistic_drop_similarity_balanced` | drop_similarity | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 0.990 [0.963, 1.000] (28 pos / 64) | 0.991 | 0.008 | 0.0003 |
| `tree_drop_similarity` | drop_similarity | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.954 | 0.003 | 0.0002 |
| `logistic_content_only_unweighted` | content_only | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.968 | 0.003 | 0.0002 |
| `logistic_content_only_balanced` | content_only | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 1.000 [1.000, 1.000] (28 pos / 64) | 0.966 | 0.005 | 0.0002 |
| `tree_content_only` | content_only | 1.000 [1.000, 1.000] (5 pos / 1000) | 1.000 [1.000, 1.000] (6 pos / 2265) | 0.982 [0.947, 1.000] (28 pos / 64) | 0.954 | 0.002 | 0.0001 |
| `logistic_behavior_recency_floor_unweighted` | behavior_recency_floor | 0.731 [0.181, 1.000] (5 pos / 1000) | 0.787 [0.181, 1.000] (6 pos / 2265) | 0.968 [0.927, 0.994] (28 pos / 64) | 0.874 | 0.021 | 0.0003 |
| `logistic_behavior_drop_rate_unweighted` | behavior_drop_rate | 0.826 [0.383, 1.000] (5 pos / 1000) | 0.859 [0.398, 1.000] (6 pos / 2265) | 0.964 [0.923, 0.992] (28 pos / 64) | 0.809 | 0.019 | 0.0003 |

## Behavior-only against all features

| Model | Behavior-only email AP | All-features email AP | Content-only email AP |
| --- | --- | --- | --- |
| logistic | 0.891 [0.583, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| tree | 0.029 [0.006, 0.057] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
