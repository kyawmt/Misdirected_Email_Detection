# Phase 4 — Experiment table

Model bundle `med-model-v1`. Dataset `med-synth-v2`. Features `med-features-v1`. Seed `20260926`.

C and tree settings were chosen by mean email-level average precision on expanding chronological folds inside `train`. Each row below was then fit on all of `train` and scored once on validation. No frozen test subset was scored. No threshold was chosen.

Bootstrap intervals resample `family_id` clusters, 1000 draws, seed `20260926`. The interval is the 2.5 and 97.5 percentiles of draws that contain both classes.

## Folds

| Fold | First week | Last week | Drafts | Positive emails | Families |
| --- | --- | --- | --- | --- | --- |
| 0 | 2024-07-01 | 2024-09-02 | 264 | 32 | 264 |
| 1 | 2024-09-09 | 2024-11-11 | 257 | 27 | 257 |
| 2 | 2024-11-18 | 2025-01-13 | 226 | 18 | 226 |
| 3 | 2025-01-20 | 2025-03-24 | 253 | 23 | 253 |

## Validation runs

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

Average precision is the area under the precision-recall curve. Email risk is the maximum recipient score. An email is positive when any recipient was unintended. `validation_product_like` has 5 misdirected emails, so its intervals are wide. Diagnostic rates are not 0.5% prevalence results.

## Train cross-validation of the chosen settings

| Run | Mean | Std | Folds scored |
| --- | --- | --- | --- |
| `always_allow` | 0.092 | 0.010 | 3 |
| `rules` | 0.298 | 0.055 | 3 |
| `fusion` | 0.757 | 0.038 | 3 |
| `logistic_all_unweighted` | 0.996 | 0.004 | 3 |
| `logistic_all_balanced` | 0.997 | 0.002 | 3 |
| `tree_all` | 0.954 | 0.059 | 3 |
| `logistic_behavior_only_unweighted` | 0.841 | 0.038 | 3 |
| `logistic_behavior_only_balanced` | 0.824 | 0.026 | 3 |
| `tree_behavior_only` | 0.520 | 0.109 | 3 |
| `logistic_drop_relationship_unweighted` | 0.979 | 0.027 | 3 |
| `logistic_drop_relationship_balanced` | 0.980 | 0.023 | 3 |
| `tree_drop_relationship` | 0.954 | 0.059 | 3 |
| `logistic_drop_similarity_unweighted` | 0.976 | 0.032 | 3 |
| `logistic_drop_similarity_balanced` | 0.991 | 0.011 | 3 |
| `tree_drop_similarity` | 0.954 | 0.059 | 3 |
| `logistic_content_only_unweighted` | 0.968 | 0.045 | 3 |
| `logistic_content_only_balanced` | 0.966 | 0.048 | 3 |
| `tree_content_only` | 0.954 | 0.059 | 3 |
| `logistic_behavior_recency_floor_unweighted` | 0.874 | 0.089 | 3 |
| `logistic_behavior_drop_rate_unweighted` | 0.809 | 0.040 | 3 |
