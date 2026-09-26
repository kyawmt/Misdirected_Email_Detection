# Phase 4 — Ablations

Each learned ablation was tuned on `train` only, then scored once. Behavior-only drops the three content-cosine columns. Drop-content drops every text-derived column, draft-length flags included. Content-only keeps only text-derived columns. `behavior_recency_floor` floors recency at one day. `behavior_drop_rate` removes `pair_outbound_rate_per_day`. Neither diagnostic enters model selection.

| Run | Ablation | Product-like email AP | Product-like recipient AP | Diagnostic email AP | CV email AP | Fit seconds | Score seconds / 1,000 rows |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `logistic_all_unweighted` | all | 0.883 [0.754, 0.976] (20 pos / 4000) | 0.858 [0.731, 0.960] (22 pos / 4970) | 0.961 [0.931, 0.983] (80 pos / 240) | 0.943 | 0.028 | 0.0003 |
| `logistic_all_balanced` | all | 0.831 [0.676, 0.954] (20 pos / 4000) | 0.820 [0.667, 0.942] (22 pos / 4970) | 0.949 [0.911, 0.977] (80 pos / 240) | 0.947 | 0.046 | 0.0002 |
| `tree_all` | all | 0.276 [0.156, 0.419] (20 pos / 4000) | 0.265 [0.155, 0.399] (22 pos / 4970) | 0.733 [0.643, 0.823] (80 pos / 240) | 0.818 | 0.009 | 0.0002 |
| `logistic_behavior_only_unweighted` | behavior_only | 0.494 [0.253, 0.710] (20 pos / 4000) | 0.502 [0.258, 0.710] (22 pos / 4970) | 0.852 [0.794, 0.906] (80 pos / 240) | 0.692 | 0.018 | 0.0002 |
| `logistic_behavior_only_balanced` | behavior_only | 0.467 [0.223, 0.688] (20 pos / 4000) | 0.486 [0.231, 0.694] (22 pos / 4970) | 0.854 [0.795, 0.904] (80 pos / 240) | 0.689 | 0.019 | 0.0002 |
| `tree_behavior_only` | behavior_only | 0.459 [0.230, 0.686] (20 pos / 4000) | 0.466 [0.237, 0.677] (22 pos / 4970) | 0.775 [0.699, 0.836] (80 pos / 240) | 0.541 | 0.009 | 0.0002 |
| `logistic_drop_content_unweighted` | drop_content | 0.456 [0.212, 0.677] (20 pos / 4000) | 0.468 [0.215, 0.675] (22 pos / 4970) | 0.797 [0.719, 0.863] (80 pos / 240) | 0.680 | 0.014 | 0.0002 |
| `logistic_drop_content_balanced` | drop_content | 0.419 [0.179, 0.642] (20 pos / 4000) | 0.439 [0.186, 0.646] (22 pos / 4970) | 0.800 [0.722, 0.865] (80 pos / 240) | 0.676 | 0.017 | 0.0002 |
| `tree_drop_content` | drop_content | 0.459 [0.230, 0.686] (20 pos / 4000) | 0.466 [0.237, 0.677] (22 pos / 4970) | 0.775 [0.699, 0.836] (80 pos / 240) | 0.541 | 0.008 | 0.0002 |
| `logistic_drop_relationship_unweighted` | drop_relationship | 0.732 [0.551, 0.893] (20 pos / 4000) | 0.720 [0.543, 0.874] (22 pos / 4970) | 0.921 [0.875, 0.957] (80 pos / 240) | 0.926 | 0.018 | 0.0002 |
| `logistic_drop_relationship_balanced` | drop_relationship | 0.708 [0.516, 0.874] (20 pos / 4000) | 0.711 [0.527, 0.862] (22 pos / 4970) | 0.932 [0.889, 0.964] (80 pos / 240) | 0.926 | 0.018 | 0.0001 |
| `tree_drop_relationship` | drop_relationship | 0.267 [0.151, 0.408] (20 pos / 4000) | 0.271 [0.154, 0.410] (22 pos / 4970) | 0.734 [0.647, 0.826] (80 pos / 240) | 0.809 | 0.005 | 0.0001 |
| `logistic_drop_similarity_unweighted` | drop_similarity | 0.873 [0.740, 0.970] (20 pos / 4000) | 0.848 [0.717, 0.953] (22 pos / 4970) | 0.962 [0.932, 0.983] (80 pos / 240) | 0.944 | 0.033 | 0.0002 |
| `logistic_drop_similarity_balanced` | drop_similarity | 0.898 [0.788, 0.976] (20 pos / 4000) | 0.878 [0.768, 0.966] (22 pos / 4970) | 0.962 [0.931, 0.983] (80 pos / 240) | 0.948 | 0.034 | 0.0002 |
| `tree_drop_similarity` | drop_similarity | 0.186 [0.111, 0.279] (20 pos / 4000) | 0.192 [0.113, 0.288] (22 pos / 4970) | 0.845 [0.770, 0.918] (80 pos / 240) | 0.778 | 0.010 | 0.0002 |
| `logistic_content_only_unweighted` | content_only | 0.557 [0.352, 0.762] (20 pos / 4000) | 0.522 [0.340, 0.710] (22 pos / 4970) | 0.824 [0.744, 0.888] (80 pos / 240) | 0.846 | 0.004 | 0.0001 |
| `logistic_content_only_balanced` | content_only | 0.300 [0.160, 0.524] (20 pos / 4000) | 0.264 [0.142, 0.484] (22 pos / 4970) | 0.663 [0.566, 0.781] (80 pos / 240) | 0.762 | 0.005 | 0.0001 |
| `tree_content_only` | content_only | 0.220 [0.108, 0.361] (20 pos / 4000) | 0.200 [0.099, 0.325] (22 pos / 4970) | 0.775 [0.691, 0.850] (80 pos / 240) | 0.770 | 0.003 | 0.0001 |
| `logistic_behavior_recency_floor_unweighted` | behavior_recency_floor | 0.501 [0.264, 0.726] (20 pos / 4000) | 0.508 [0.265, 0.710] (22 pos / 4970) | 0.854 [0.795, 0.906] (80 pos / 240) | 0.695 | 0.019 | 0.0002 |
| `logistic_behavior_drop_rate_unweighted` | behavior_drop_rate | 0.483 [0.238, 0.703] (20 pos / 4000) | 0.492 [0.244, 0.692] (22 pos / 4970) | 0.844 [0.782, 0.898] (80 pos / 240) | 0.693 | 0.015 | 0.0002 |

## Behavior-only against all features

| Model | Behavior-only email AP | All-features email AP | Content-only email AP |
| --- | --- | --- | --- |
| logistic | 0.494 [0.253, 0.710] | 0.883 [0.754, 0.976] | 0.557 [0.352, 0.762] |
| tree | 0.459 [0.230, 0.686] | 0.276 [0.156, 0.419] | 0.220 [0.108, 0.361] |
