# Phase 4 — Selected model artifact

Bundle `med-model-v1` scores one risk number per recipient. The number is a risk score. It was not calibrated, and no warning or block threshold is stored.

## Files

| File | Role |
| --- | --- |
| `model.joblib` | Fitted scorer and metadata. Loading does not refit. |
| `experiments.json` | Every recorded run, including the ones that were not selected. |
| `model_metadata.json` | The selected run's versions, features, folds, and checksums. |

## Identity

- Selected run: `logistic_behavior_only_unweighted` (logistic, ablation `behavior_only`).
- Configuration: `{'C': 100.0, 'class_weight': 'unweighted'}`.
- Dataset: `med-synth-v2`.
- Feature spec: `med-features-v1`.
- Text transformer SHA-256: `153d7eecddaf64243d50c31e8616b9345492dec051388ba4deca35512eb67cab`.
- Feature schema SHA-256: `1a26f32fa8ff77b54ae3bc82224a343a197f7a2b92e89d1e26e07b449bdd1a81`.
- scikit-learn `1.9.1`, NumPy `2.4.6`.

## Inputs

The scorer reads only these columns, in this order:

`sender_outbound_count`, `sender_history_available`, `sender_history_span_days`, `pair_outbound_count`, `pair_inbound_count`, `pair_outbound_count_28d`, `pair_inbound_count_28d`, `pair_outbound_rate_per_day`, `pair_recency_days`, `pair_recency_observed`, `recipient_novel_to_sender`, `domain_outbound_count`, `domain_novel_to_sender`, `domain_seen_in_history`, `recipient_is_internal`, `addressed_recipient_count`, `co_support_applicable`, `co_joint_message_count`, `co_partner_fraction`, `co_focus_conditional_fraction`, `co_focus_history_available`, `name_similarity_max`, `address_similarity_max`, `contact_similarity_observed`, `near_name_count`, `draft_raw_token_count`, `draft_text_empty`, `draft_text_short`, `draft_text_oov`, `draft_subject_blank`, `draft_body_blank`

Labels, roles, scenarios, splits, subsets, families, and other audit fields are rejected. A different feature-spec version or a different installed feature list is rejected.

## Output

One `risk_score` per recipient row. Email risk, when needed, is the maximum of those scores. The bundle does not return a decision.

## Load checks

- `model_version` must be `med-model-v1`.
- `feature_spec_version` must match the installed feature package.
- `full_feature_columns` must match `FEATURE_COLUMNS` in order.
- The loader does not call `fit`.
