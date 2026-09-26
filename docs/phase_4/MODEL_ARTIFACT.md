# Phase 4 — Selected model artifact

Bundle `med-model-v2` scores one risk number per recipient. The number is a risk score. It was not calibrated, and no warning or block threshold is stored.

## Files

| File | Role |
| --- | --- |
| `model.joblib` | Fitted scorer and metadata. Loading does not refit. |
| `experiments.json` | Every recorded run, including the ones that were not selected. |
| `model_metadata.json` | The selected run's versions, features, folds, and checksums. |

## Identity

- Selected run: `logistic_all_balanced` (logistic, ablation `all`).
- Configuration: `{'C': 1000.0, 'class_weight': 'balanced'}`.
- Dataset: `med-synth-v4`.
- Feature spec: `med-features-v2`.
- Text transformer SHA-256: `a9c59597bd46dbbcfbb1f86bf3dc9ebc1d796c5b3415e2e06e77f604665ae228`.
- Feature schema SHA-256: `b6a05a5fe436a870e8aef48cae1cf7996552e948d510db36e311cac79062c117`.
- scikit-learn `1.9.1`, NumPy `2.4.6`.

## Inputs

The scorer reads only these columns, in this order:

`sender_outbound_count`, `sender_history_available`, `sender_history_span_days`, `pair_outbound_count`, `pair_inbound_count`, `pair_outbound_count_28d`, `pair_inbound_count_28d`, `pair_outbound_rate_per_day`, `pair_recency_days`, `pair_recency_observed`, `recipient_novel_to_sender`, `domain_outbound_count`, `domain_novel_to_sender`, `domain_seen_in_history`, `recipient_is_internal`, `addressed_recipient_count`, `co_support_applicable`, `co_joint_message_count`, `co_partner_fraction`, `co_focus_conditional_fraction`, `co_focus_history_available`, `name_similarity_max`, `address_similarity_max`, `contact_similarity_observed`, `near_name_count`, `content_cosine`, `content_similarity_observed`, `pair_text_message_count`, `draft_raw_token_count`, `draft_text_empty`, `draft_text_short`, `draft_text_oov`, `draft_subject_blank`, `draft_body_blank`

Labels, roles, scenarios, splits, subsets, families, and other audit fields are rejected. A different feature-spec version or a different installed feature list is rejected.

## Preprocessing stored with the model

When recency was not observed (`pair_recency_observed` is 0), the feature row carries the documented 3650-day fallback. The model does not read that value: it replaces it with the median observed `pair_recency_days` on the training rows, 0.234375 days (337.5 minutes), and then applies `log1p`. A first contact therefore enters the model with the recency of a typical recent correspondent, and `pair_recency_observed` = 0 is the input that marks it as unobserved. Counts also take `log1p`. Logistic regression then standardizes with the training mean and standard deviation. All of these values are fit on `train` only and stored in `model.joblib`.

## Output

One `risk_score` per recipient row. Email risk, when needed, is the maximum of those scores. The bundle does not return a decision.

## Load checks

- `model_version` must be `med-model-v2`.
- `feature_spec_version` must match the installed feature package.
- `full_feature_columns` must match `FEATURE_COLUMNS` in order.
- The loader does not call `fit`.
