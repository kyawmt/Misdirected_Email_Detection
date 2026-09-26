# Phase 3 — Feature quality report

Feature specification `med-features-v1`. Dataset `med-synth-v2`.

This report describes feature matrices for train and validation only. It does not measure detection, precision, recall, or a warning rate. Scenario and label fields were joined after the matrix was built and are not model inputs. `test_product_like` and `test_diagnostic` are not included. Every exported value is finite; the build rejects a matrix that breaks the fallback checks.

## Fit scope

- `corpus`: sent_messages_before_validation_window
- `document_count`: 17954
- `vocabulary_size`: 600
- `messages_in_window`: 17956
- `empty_documents_skipped`: 2
- `first_sent_at`: 2024-01-08T09:00:00Z
- `last_sent_at`: 2025-03-28T14:50:30Z
- `fit_sent_at_end_exclusive`: 2025-03-31T00:00:00Z
- `warmup_included`: True
- `validation_and_test_excluded`: True

## Populations

### `train`

1000 drafts, 2320 recipient rows, 13 senders.

| Feature | Min | Mean | Max | Unique | Undefined |
| --- | --- | --- | --- | --- | --- |
| `address_similarity_max` | 0.2000 | 0.4962 | 0.8889 | 18 | 0.0000 |
| `addressed_recipient_count` | 1.0000 | 3.3491 | 6.0000 | 6 | 0.0000 |
| `co_focus_conditional_fraction` | 0.0000 | 0.9472 | 1.0000 | 419 | 0.2353 |
| `co_focus_history_available` | 0.0000 | 0.9931 | 1.0000 | 2 | 0.0000 |
| `co_joint_message_count` | 0.0000 | 1260.2784 | 3069.0000 | 760 | 0.0000 |
| `co_partner_fraction` | 0.0000 | 0.9322 | 1.0000 | 4 | 0.2319 |
| `co_support_applicable` | 0.0000 | 0.7681 | 1.0000 | 2 | 0.0000 |
| `contact_similarity_observed` | 1.0000 | 1.0000 | 1.0000 | 1 | 0.0000 |
| `content_cosine` | 0.0000 | 0.6718 | 0.8708 | 2271 | 0.0078 |
| `content_similarity_observed` | 0.0000 | 0.9922 | 1.0000 | 2 | 0.0000 |
| `domain_novel_to_sender` | 0.0000 | 0.0052 | 1.0000 | 2 | 0.0000 |
| `domain_outbound_count` | 0.0000 | 3939.9672 | 6665.0000 | 977 | 0.0000 |
| `domain_seen_in_history` | 0.0000 | 0.9983 | 1.0000 | 2 | 0.0000 |
| `draft_body_blank` | 0.0000 | 0.0034 | 1.0000 | 2 | 0.0000 |
| `draft_raw_token_count` | 0.0000 | 16.8194 | 21.0000 | 11 | 0.0000 |
| `draft_subject_blank` | 0.0000 | 0.0009 | 1.0000 | 2 | 0.0000 |
| `draft_text_empty` | 0.0000 | 0.0000 | 0.0000 | 1 | 0.0000 |
| `draft_text_oov` | 0.0000 | 0.0009 | 1.0000 | 2 | 0.0000 |
| `draft_text_short` | 0.0000 | 0.0043 | 1.0000 | 2 | 0.0000 |
| `name_similarity_max` | 0.2727 | 0.4353 | 0.8889 | 17 | 0.0000 |
| `near_name_count` | 0.0000 | 0.0720 | 1.0000 | 2 | 0.0000 |
| `pair_inbound_count` | 0.0000 | 390.4862 | 2813.0000 | 693 | 0.0000 |
| `pair_inbound_count_28d` | 0.0000 | 35.3845 | 176.0000 | 10 | 0.0000 |
| `pair_outbound_count` | 0.0000 | 1315.6336 | 3073.0000 | 1221 | 0.0000 |
| `pair_outbound_count_28d` | 0.0000 | 119.3440 | 193.0000 | 12 | 0.0000 |
| `pair_outbound_rate_per_day` | 0.0000 | 4.2967 | 6.9663 | 1799 | 0.0034 |
| `pair_recency_days` | 0.0003 | 1.0536 | 6.9997 | 87 | 0.0069 |
| `pair_recency_observed` | 0.0000 | 0.9931 | 1.0000 | 2 | 0.0000 |
| `pair_text_message_count` | 0.0000 | 1705.9022 | 5884.0000 | 1628 | 0.0000 |
| `recipient_is_internal` | 0.0000 | 0.9315 | 1.0000 | 2 | 0.0000 |
| `recipient_novel_to_sender` | 0.0000 | 0.0069 | 1.0000 | 2 | 0.0000 |
| `sender_history_available` | 0.0000 | 0.9966 | 1.0000 | 2 | 0.0000 |
| `sender_history_span_days` | 175.0000 | 308.5918 | 445.1319 | 988 | 0.0034 |
| `sender_outbound_count` | 0.0000 | 4955.4078 | 7821.0000 | 989 | 0.0000 |

Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.

| scenario_id | drafts | recipient_rows | recipient_novel_to_sender | domain_novel_to_sender | pair_outbound_count | content_similarity_observed | content_cosine | name_similarity_max | draft_text_empty | draft_text_oov | co_support_applicable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 24 | 24 | 0.0000 | 0.0000 | 182.2083 | 1.0000 | 0.0534 | 0.8283 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 24 | 120 | 0.0000 | 0.0000 | 1350.5667 | 1.0000 | 0.2559 | 0.3565 | 0.0000 | 0.0000 | 1.0000 |
| S03 | 4 | 4 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.7510 | 0.0000 | 0.0000 | 0.0000 |
| S04 | 20 | 20 | 0.0000 | 0.0000 | 43.3500 | 1.0000 | 0.0168 | 0.7370 | 0.0000 | 0.0000 | 0.0000 |
| S05 | 396 | 1273 | 0.0000 | 0.0000 | 1855.1658 | 1.0000 | 0.7734 | 0.3683 | 0.0000 | 0.0000 | 0.9097 |
| S06 | 4 | 4 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |  | 0.7324 | 0.0000 | 0.0000 | 0.0000 |
| S07 | 4 | 4 | 0.0000 | 0.0000 | 40.5000 | 1.0000 | 0.0860 | 0.8007 | 0.0000 | 0.0000 | 0.0000 |
| S08 | 26 | 138 | 0.0000 | 0.0000 | 1610.2826 | 1.0000 | 0.5942 | 0.4283 | 0.0000 | 0.0000 | 1.0000 |
| S09 | 14 | 18 | 0.4444 | 0.4444 | 483.7778 | 0.4444 | 0.0000 | 0.4714 | 0.0000 | 0.1111 | 0.4444 |
| routine | 484 | 715 | 0.0000 | 0.0000 | 408.7371 | 1.0000 | 0.6256 | 0.5412 | 0.0000 | 0.0000 | 0.5007 |

Constant features in this subset: `contact_similarity_observed`, `draft_text_empty`.

Intended and unintended means use the stipulated label after scoring. They are not a precision or recall result, and the training mix is enriched.

| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |
| --- | --- | --- | --- | --- | --- |
| intended | 2212 | 1370.4842 | 0.0072 | 0.7038 | 0.4245 |
| unintended | 108 | 192.2130 | 0.0000 | 0.0213 | 0.6579 |

### `validation_product_like`

1000 drafts, 2265 recipient rows, 11 senders.

| Feature | Min | Mean | Max | Unique | Undefined |
| --- | --- | --- | --- | --- | --- |
| `address_similarity_max` | 0.2000 | 0.4924 | 0.8889 | 18 | 0.0000 |
| `addressed_recipient_count` | 1.0000 | 3.1881 | 6.0000 | 6 | 0.0000 |
| `co_focus_conditional_fraction` | 0.0000 | 0.9724 | 1.0000 | 426 | 0.2340 |
| `co_focus_history_available` | 0.0000 | 0.9956 | 1.0000 | 2 | 0.0000 |
| `co_joint_message_count` | 0.0000 | 2147.2967 | 4124.0000 | 749 | 0.0000 |
| `co_partner_fraction` | 0.0000 | 0.9933 | 1.0000 | 4 | 0.2322 |
| `co_support_applicable` | 0.0000 | 0.7678 | 1.0000 | 2 | 0.0000 |
| `contact_similarity_observed` | 1.0000 | 1.0000 | 1.0000 | 1 | 0.0000 |
| `content_cosine` | 0.0004 | 0.7171 | 0.8482 | 2224 | 0.0049 |
| `content_similarity_observed` | 0.0000 | 0.9951 | 1.0000 | 2 | 0.0000 |
| `domain_novel_to_sender` | 0.0000 | 0.0031 | 1.0000 | 2 | 0.0000 |
| `domain_outbound_count` | 0.0000 | 6630.5629 | 8970.0000 | 965 | 0.0000 |
| `domain_seen_in_history` | 0.0000 | 0.9987 | 1.0000 | 2 | 0.0000 |
| `draft_body_blank` | 0.0000 | 0.0004 | 1.0000 | 2 | 0.0000 |
| `draft_raw_token_count` | 0.0000 | 16.7541 | 21.0000 | 10 | 0.0000 |
| `draft_subject_blank` | 0.0000 | 0.0004 | 1.0000 | 2 | 0.0000 |
| `draft_text_empty` | 0.0000 | 0.0000 | 0.0000 | 1 | 0.0000 |
| `draft_text_oov` | 0.0000 | 0.0004 | 1.0000 | 2 | 0.0000 |
| `draft_text_short` | 0.0000 | 0.0009 | 1.0000 | 2 | 0.0000 |
| `name_similarity_max` | 0.2727 | 0.4337 | 0.8889 | 18 | 0.0000 |
| `near_name_count` | 0.0000 | 0.0706 | 1.0000 | 2 | 0.0000 |
| `pair_inbound_count` | 0.0000 | 654.0274 | 3780.0000 | 695 | 0.0000 |
| `pair_inbound_count_28d` | 0.0000 | 34.9091 | 176.0000 | 10 | 0.0000 |
| `pair_outbound_count` | 0.0000 | 2236.1470 | 4131.0000 | 1144 | 0.0000 |
| `pair_outbound_count_28d` | 0.0000 | 119.3894 | 193.0000 | 12 | 0.0000 |
| `pair_outbound_rate_per_day` | 0.0000 | 4.2814 | 6.9106 | 1796 | 0.0018 |
| `pair_recency_days` | 0.0003 | 0.9740 | 6.9997 | 46 | 0.0044 |
| `pair_recency_observed` | 0.0000 | 0.9956 | 1.0000 | 2 | 0.0000 |
| `pair_text_message_count` | 0.0000 | 2889.6870 | 7907.0000 | 1660 | 0.0000 |
| `recipient_is_internal` | 0.0000 | 0.9391 | 1.0000 | 2 | 0.0000 |
| `recipient_novel_to_sender` | 0.0000 | 0.0044 | 1.0000 | 2 | 0.0000 |
| `sender_history_available` | 0.0000 | 0.9982 | 1.0000 | 2 | 0.0000 |
| `sender_history_span_days` | 448.0000 | 523.0607 | 599.1396 | 988 | 0.0018 |
| `sender_outbound_count` | 0.0000 | 8261.0914 | 10526.0000 | 994 | 0.0000 |

Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.

| scenario_id | drafts | recipient_rows | recipient_novel_to_sender | domain_novel_to_sender | pair_outbound_count | content_similarity_observed | content_cosine | name_similarity_max | draft_text_empty | draft_text_oov | co_support_applicable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 1 | 1 | 0.0000 | 0.0000 | 320.0000 | 1.0000 | 0.0469 | 0.8889 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 1 | 5 | 0.0000 | 0.0000 | 1983.2000 | 1.0000 | 0.2568 | 0.3646 | 0.0000 | 0.0000 | 1.0000 |
| S03 | 3 | 3 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.6875 | 0.0000 | 0.0000 | 0.0000 |
| S04 | 1 | 1 | 0.0000 | 0.0000 | 64.0000 | 1.0000 | 0.0187 | 0.7500 | 0.0000 | 0.0000 | 0.0000 |
| S05 | 446 | 1421 | 0.0000 | 0.0000 | 3152.8663 | 1.0000 | 0.7709 | 0.3701 | 0.0000 | 0.0000 | 0.9064 |
| S06 | 3 | 3 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |  | 0.6435 | 0.0000 | 0.0000 | 0.0000 |
| S07 | 3 | 3 | 0.0000 | 0.0000 | 71.0000 | 1.0000 | 0.0876 | 0.6673 | 0.0000 | 0.0000 | 0.0000 |
| S08 | 2 | 11 | 0.0000 | 0.0000 | 2537.0909 | 1.0000 | 0.5659 | 0.4657 | 0.0000 | 0.0000 | 1.0000 |
| S09 | 4 | 6 | 0.6667 | 0.6667 | 1106.8333 | 0.1667 | 0.0004 | 0.2929 | 0.0000 | 0.1667 | 0.6667 |
| routine | 536 | 811 | 0.0000 | 0.0000 | 665.3366 | 1.0000 | 0.6327 | 0.5427 | 0.0000 | 0.0000 | 0.5314 |

Constant features in this subset: `contact_similarity_observed`, `draft_text_empty`.

Intended and unintended means use the stipulated label after scoring. They are not a precision or recall result, and the training mix is enriched.

| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |
| --- | --- | --- | --- | --- | --- |
| intended | 2259 | 2241.2240 | 0.0044 | 0.7190 | 0.4329 |
| unintended | 6 | 324.6667 | 0.0000 | 0.0222 | 0.7210 |

### `validation_diagnostic`

64 drafts, 192 recipient rows, 2 senders.

| Feature | Min | Mean | Max | Unique | Undefined |
| --- | --- | --- | --- | --- | --- |
| `address_similarity_max` | 0.2000 | 0.4917 | 0.8889 | 12 | 0.0000 |
| `addressed_recipient_count` | 1.0000 | 4.0938 | 6.0000 | 5 | 0.0000 |
| `co_focus_conditional_fraction` | 0.0000 | 0.8785 | 1.0000 | 20 | 0.1406 |
| `co_focus_history_available` | 0.0000 | 0.9792 | 1.0000 | 2 | 0.0000 |
| `co_joint_message_count` | 0.0000 | 2365.0417 | 4052.0000 | 41 | 0.0000 |
| `co_partner_fraction` | 0.0000 | 0.7581 | 1.0000 | 4 | 0.1302 |
| `co_support_applicable` | 0.0000 | 0.8698 | 1.0000 | 2 | 0.0000 |
| `contact_similarity_observed` | 1.0000 | 1.0000 | 1.0000 | 1 | 0.0000 |
| `content_cosine` | 0.0000 | 0.5571 | 0.8394 | 120 | 0.0260 |
| `content_similarity_observed` | 0.0000 | 0.9740 | 1.0000 | 2 | 0.0000 |
| `domain_novel_to_sender` | 0.0000 | 0.0156 | 1.0000 | 2 | 0.0000 |
| `domain_outbound_count` | 0.0000 | 7083.6667 | 8808.0000 | 47 | 0.0000 |
| `domain_seen_in_history` | 0.0000 | 0.9948 | 1.0000 | 2 | 0.0000 |
| `draft_body_blank` | 0.0000 | 0.0208 | 1.0000 | 2 | 0.0000 |
| `draft_raw_token_count` | 0.0000 | 17.0833 | 21.0000 | 8 | 0.0000 |
| `draft_subject_blank` | 0.0000 | 0.0052 | 1.0000 | 2 | 0.0000 |
| `draft_text_empty` | 0.0000 | 0.0000 | 0.0000 | 1 | 0.0000 |
| `draft_text_oov` | 0.0000 | 0.0052 | 1.0000 | 2 | 0.0000 |
| `draft_text_short` | 0.0000 | 0.0260 | 1.0000 | 2 | 0.0000 |
| `name_similarity_max` | 0.2727 | 0.4368 | 0.8889 | 12 | 0.0000 |
| `near_name_count` | 0.0000 | 0.0833 | 1.0000 | 2 | 0.0000 |
| `pair_inbound_count` | 0.0000 | 734.6823 | 3714.0000 | 65 | 0.0000 |
| `pair_inbound_count_28d` | 0.0000 | 39.6250 | 176.0000 | 6 | 0.0000 |
| `pair_outbound_count` | 0.0000 | 2462.4062 | 4059.0000 | 89 | 0.0000 |
| `pair_outbound_count_28d` | 0.0000 | 132.9167 | 193.0000 | 8 | 0.0000 |
| `pair_outbound_rate_per_day` | 0.0000 | 4.8074 | 6.9051 | 103 | 0.0104 |
| `pair_recency_days` | 0.0003 | 0.9612 | 6.8615 | 47 | 0.0208 |
| `pair_recency_observed` | 0.0000 | 0.9792 | 1.0000 | 2 | 0.0000 |
| `pair_text_message_count` | 0.0000 | 3196.5000 | 7769.0000 | 111 | 0.0000 |
| `recipient_is_internal` | 0.0000 | 0.9271 | 1.0000 | 2 | 0.0000 |
| `recipient_novel_to_sender` | 0.0000 | 0.0208 | 1.0000 | 2 | 0.0000 |
| `sender_history_available` | 0.0000 | 0.9896 | 1.0000 | 2 | 0.0000 |
| `sender_history_span_days` | 448.0007 | 516.5178 | 590.0000 | 36 | 0.0104 |
| `sender_outbound_count` | 0.0000 | 8956.6510 | 10334.0000 | 36 | 0.0000 |

Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.

| scenario_id | drafts | recipient_rows | recipient_novel_to_sender | domain_novel_to_sender | pair_outbound_count | content_similarity_observed | content_cosine | name_similarity_max | draft_text_empty | draft_text_oov | co_support_applicable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 8 | 8 | 0.0000 | 0.0000 | 356.8750 | 1.0000 | 0.3100 | 0.8157 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 8 | 36 | 0.0000 | 0.0000 | 2520.8889 | 1.0000 | 0.2857 | 0.3587 | 0.0000 | 0.0000 | 1.0000 |
| S03 | 1 | 1 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.6923 | 0.0000 | 0.0000 | 0.0000 |
| S04 | 8 | 12 | 0.0000 | 0.0000 | 324.5000 | 1.0000 | 0.5027 | 0.4940 | 0.0000 | 0.0000 | 0.6667 |
| S05 | 2 | 5 | 0.0000 | 0.0000 | 2484.8000 | 1.0000 | 0.7522 | 0.3800 | 0.0000 | 0.0000 | 0.8000 |
| S06 | 1 | 1 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |  | 0.7692 | 0.0000 | 0.0000 | 0.0000 |
| S07 | 1 | 1 | 0.0000 | 0.0000 | 80.0000 | 1.0000 | 0.0915 | 0.6923 | 0.0000 | 0.0000 | 0.0000 |
| S08 | 25 | 117 | 0.0000 | 0.0000 | 3043.9145 | 1.0000 | 0.6773 | 0.4002 | 0.0000 | 0.0000 | 1.0000 |
| S09 | 10 | 11 | 0.1818 | 0.1818 | 603.5455 | 0.7273 | 0.2862 | 0.6933 | 0.0000 | 0.0909 | 0.1818 |

Constant features in this subset: `contact_similarity_observed`, `draft_text_empty`.

Intended and unintended means use the stipulated label after scoring. They are not a precision or recall result, and the training mix is enriched.

| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |
| --- | --- | --- | --- | --- | --- |
| intended | 160 | 2886.5625 | 0.0250 | 0.6683 | 0.3895 |
| unintended | 32 | 341.6250 | 0.0000 | 0.0185 | 0.6737 |

## Hypotheses

These were fixed with the feature definitions. The tables are the place to compare them. Agreement is not evidence that a later model should warn.

- First-contact scenarios should show recipient_novel_to_sender near 1. Routine repeat mail should show it near 0. Novelty is not a label.
- A new external domain should show domain_seen_in_history of 0 and domain_novel_to_sender of 1. A new person on a known internal domain can be novel while the domain has already been seen.
- Lookalike names that are already in the directory should produce name_similarity_max well above the 0.8 near-name threshold. The nearest contact's identity is not a feature.
- Content cosine is summarized only where content_similarity_observed is 1. Empty drafts and out-of-vocabulary drafts stay at the cosine fallback 0, with their own indicators set.
- Single-recipient drafts keep co_support_applicable at 0. A multi-recipient draft with no shared history keeps a measured partner fraction of 0 where the flag is 1.
- Bcc does not appear in the matrix. Intended Bcc mail and unintended Bcc mail are not separated by a role indicator.
- Train contains about 10% misdirected emails and the product-like validation subset contains 0.5%. Means that pool those subsets are not an operating point. Intended and unintended means in this report are descriptive only.

## What the tables show

- Training S03 (4 drafts) is novel to the sender and not novel by domain. Training S06 (4 drafts) is novel on both. Neither scenario has an observed content cosine, because there is no pair text.
- Training S01 name similarity averages about 0.83, above the 0.8 near-name threshold. The maximum in the matrix is 0.8889, one edit on a 9-character name. Training S05 averages about 0.37.
- Training S04 and S07 both have low observed content cosine (about 0.02 and 0.09). Training S05 averages about 0.77. A low cosine shows up on the mismatched topic and on the legitimate topic change.
- Product-like validation has 6 unintended recipient rows. The intended-versus-unintended means are descriptive on that handful of rows.
- Validation diagnostic S04 does not repeat the training S04 cosine. Those rows mix variants. Use the per-scenario sample size before treating a mean as a stable description.

## Limitations

- No classifier was trained. No risk score, threshold, precision, recall, or false-warning rate is claimed.
- IDF is frozen on sent mail before the validation window. It is not re-estimated at each earlier training draft. Historical counts and text centroids still stop at that draft's cutoff.
- Template sentences repeat across weeks. Stripping reference, ticket, and date slots removes unique generator tokens. It does not remove shared topic wording.
- Group-topic profiles are not implemented. A recipient with no direct pair history has no content centroid even if a broader group has discussed the topic.
- Diagnostic rows that share a family are dependent. Product-like families contain one draft. Scenario means pool variants, including clean twins, and are not one story. Do not read a diagnostic rate as the 0.5% prevalence result.
- The fictional history is dense weekly mail, so outbound counts and per-day rates are large. That scale is a property of the generator, not a real-world volume.
- On the exported subsets, contact similarity is always observed because other directory entries are already visible, and train never blanks both subject and body. The unobserved-similarity and both-fields-empty fallbacks remain part of the contract and are covered by fixture tests.
- The product-like test has 10 misdirected emails and was not profiled here.
- Department is a directory field and is not a v1 feature. Communication role is stored on the draft and is not a feature.
