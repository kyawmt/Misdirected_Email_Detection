# Phase 3 — Feature quality report

Feature specification `med-features-v2`. Dataset `med-synth-v4`.

This report describes feature matrices for train and validation only. It does not measure detection, precision, recall, or a warning rate. Scenario and label fields were joined after the matrix was built and are not model inputs. `test_product_like` and `test_diagnostic` are not included. Every exported value is finite; the build rejects a matrix that breaks the fallback checks.

## Fit scope

- `corpus`: sent_messages_before_validation_window
- `document_count`: 95241
- `vocabulary_size`: 1366
- `messages_in_window`: 95246
- `empty_documents_skipped`: 5
- `first_sent_at`: 2024-01-08T08:30:00Z
- `last_sent_at`: 2025-03-28T17:26:58Z
- `fit_sent_at_end_exclusive`: 2025-03-31T00:00:00Z
- `warmup_included`: True
- `validation_and_test_excluded`: True

## Populations

### `train`

3000 drafts, 3955 recipient rows, 19 senders.

| Feature | Min | Mean | Max | Unique | Undefined |
| --- | --- | --- | --- | --- | --- |
| `address_similarity_max` | 0.2000 | 0.6404 | 0.8889 | 22 | 0.0000 |
| `addressed_recipient_count` | 1.0000 | 2.0240 | 7.0000 | 7 | 0.0000 |
| `co_focus_conditional_fraction` | 0.0000 | 0.6796 | 1.0000 | 769 | 0.6690 |
| `co_focus_history_available` | 0.0000 | 0.9823 | 1.0000 | 2 | 0.0000 |
| `co_joint_message_count` | 0.0000 | 406.2657 | 2859.0000 | 536 | 0.0000 |
| `co_partner_fraction` | 0.0000 | 0.8002 | 1.0000 | 7 | 0.6640 |
| `co_support_applicable` | 0.0000 | 0.3360 | 1.0000 | 2 | 0.0000 |
| `contact_similarity_observed` | 1.0000 | 1.0000 | 1.0000 | 1 | 0.0000 |
| `content_cosine` | 0.0000 | 0.4138 | 0.8245 | 3870 | 0.0190 |
| `content_similarity_observed` | 0.0000 | 0.9810 | 1.0000 | 2 | 0.0000 |
| `domain_novel_to_sender` | 0.0000 | 0.0076 | 1.0000 | 2 | 0.0000 |
| `domain_outbound_count` | 0.0000 | 26079.5686 | 42807.0000 | 3025 | 0.0000 |
| `domain_seen_in_history` | 0.0000 | 0.9975 | 1.0000 | 2 | 0.0000 |
| `draft_body_blank` | 0.0000 | 0.0038 | 1.0000 | 2 | 0.0000 |
| `draft_raw_token_count` | 0.0000 | 19.6071 | 28.0000 | 19 | 0.0000 |
| `draft_subject_blank` | 0.0000 | 0.0013 | 1.0000 | 2 | 0.0000 |
| `draft_text_empty` | 0.0000 | 0.0000 | 0.0000 | 1 | 0.0000 |
| `draft_text_oov` | 0.0000 | 0.0013 | 1.0000 | 2 | 0.0000 |
| `draft_text_short` | 0.0000 | 0.0051 | 1.0000 | 2 | 0.0000 |
| `name_similarity_max` | 0.2727 | 0.6342 | 0.8889 | 26 | 0.0000 |
| `near_name_count` | 0.0000 | 0.1965 | 1.0000 | 2 | 0.0000 |
| `pair_inbound_count` | 0.0000 | 485.4033 | 3049.0000 | 1124 | 0.0000 |
| `pair_inbound_count_28d` | 0.0000 | 43.7057 | 192.0000 | 15 | 0.0000 |
| `pair_outbound_count` | 0.0000 | 821.2683 | 3631.0000 | 1517 | 0.0000 |
| `pair_outbound_count_28d` | 0.0000 | 74.0673 | 230.0000 | 18 | 0.0000 |
| `pair_outbound_rate_per_day` | 0.0000 | 2.6678 | 8.2474 | 3670 | 0.0051 |
| `pair_recency_days` | 0.0021 | 0.8187 | 4.7895 | 815 | 0.0177 |
| `pair_recency_observed` | 0.0000 | 0.9823 | 1.0000 | 2 | 0.0000 |
| `pair_text_message_count` | 0.0000 | 1306.4862 | 6675.0000 | 1684 | 0.0000 |
| `recipient_is_internal` | 0.0000 | 0.9350 | 1.0000 | 2 | 0.0000 |
| `recipient_novel_to_sender` | 0.0000 | 0.0177 | 1.0000 | 2 | 0.0000 |
| `sender_history_available` | 0.0000 | 0.9949 | 1.0000 | 2 | 0.0000 |
| `sender_history_span_days` | 175.0000 | 309.7582 | 445.3480 | 2991 | 0.0051 |
| `sender_outbound_count` | 0.0000 | 29755.0260 | 45505.0000 | 2987 | 0.0000 |

Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.

| scenario_id | drafts | recipient_rows | recipient_novel_to_sender | domain_novel_to_sender | pair_outbound_count | content_similarity_observed | content_cosine | name_similarity_max | draft_text_empty | draft_text_oov | co_support_applicable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 70 | 70 | 0.0000 | 0.0000 | 888.7429 | 1.0000 | 0.2208 | 0.8291 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 70 | 152 | 0.0000 | 0.0000 | 625.0263 | 1.0000 | 0.1903 | 0.6339 | 0.0000 | 0.0000 | 1.0000 |
| S03 | 10 | 10 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.7029 | 0.0000 | 0.0000 | 0.0000 |
| S04 | 60 | 60 | 0.0000 | 0.0000 | 220.7167 | 1.0000 | 0.0361 | 0.7762 | 0.0000 | 0.0000 | 0.0000 |
| S05 | 219 | 587 | 0.0000 | 0.0000 | 1880.8330 | 1.0000 | 0.6330 | 0.4489 | 0.0000 | 0.0000 | 0.8211 |
| S06 | 10 | 10 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |  | 0.7117 | 0.0000 | 0.0000 | 0.0000 |
| S07 | 36 | 36 | 0.0000 | 0.0000 | 222.9167 | 1.0000 | 0.2732 | 0.7478 | 0.0000 | 0.0000 | 0.0000 |
| S08 | 60 | 333 | 0.0000 | 0.0000 | 1797.4955 | 1.0000 | 0.5720 | 0.4725 | 0.0000 | 0.0000 | 1.0000 |
| S09 | 30 | 40 | 0.5000 | 0.5000 | 817.8500 | 0.3750 | 0.0535 | 0.4919 | 0.0000 | 0.1250 | 0.5000 |
| S11 | 30 | 30 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.7386 | 0.0000 | 0.0000 | 0.0000 |
| routine | 2405 | 2627 | 0.0000 | 0.0000 | 507.9189 | 1.0000 | 0.3755 | 0.6866 | 0.0000 | 0.0000 | 0.1302 |

Constant features in this subset: `contact_similarity_observed`, `draft_text_empty`.

Intended and unintended means use the stipulated label after scoring. They are not a precision or recall result, and the training mix is enriched.

| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |
| --- | --- | --- | --- | --- | --- |
| intended | 3640 | 842.1948 | 0.0110 | 0.4356 | 0.6266 |
| unintended | 315 | 579.4508 | 0.0952 | 0.1397 | 0.7226 |

### `validation_product_like`

4000 drafts, 4970 recipient rows, 14 senders.

| Feature | Min | Mean | Max | Unique | Undefined |
| --- | --- | --- | --- | --- | --- |
| `address_similarity_max` | 0.2000 | 0.6423 | 0.8889 | 22 | 0.0000 |
| `addressed_recipient_count` | 1.0000 | 1.7453 | 6.0000 | 6 | 0.0000 |
| `co_focus_conditional_fraction` | 0.0000 | 0.7849 | 1.0000 | 896 | 0.7264 |
| `co_focus_history_available` | 0.0000 | 0.9936 | 1.0000 | 2 | 0.0000 |
| `co_joint_message_count` | 0.0000 | 607.3738 | 3860.0000 | 614 | 0.0000 |
| `co_partner_fraction` | 0.0000 | 0.9799 | 1.0000 | 5 | 0.7243 |
| `co_support_applicable` | 0.0000 | 0.2757 | 1.0000 | 2 | 0.0000 |
| `contact_similarity_observed` | 1.0000 | 1.0000 | 1.0000 | 1 | 0.0000 |
| `content_cosine` | 0.0011 | 0.4265 | 0.8181 | 4913 | 0.0070 |
| `content_similarity_observed` | 0.0000 | 0.9930 | 1.0000 | 2 | 0.0000 |
| `domain_novel_to_sender` | 0.0000 | 0.0040 | 1.0000 | 2 | 0.0000 |
| `domain_outbound_count` | 0.0000 | 44336.8089 | 57579.0000 | 3963 | 0.0000 |
| `domain_seen_in_history` | 0.0000 | 0.9980 | 1.0000 | 2 | 0.0000 |
| `draft_body_blank` | 0.0000 | 0.0006 | 1.0000 | 2 | 0.0000 |
| `draft_raw_token_count` | 0.0000 | 19.4610 | 28.0000 | 19 | 0.0000 |
| `draft_subject_blank` | 0.0000 | 0.0006 | 1.0000 | 2 | 0.0000 |
| `draft_text_empty` | 0.0000 | 0.0000 | 0.0000 | 1 | 0.0000 |
| `draft_text_oov` | 0.0000 | 0.0006 | 1.0000 | 2 | 0.0000 |
| `draft_text_short` | 0.0000 | 0.0012 | 1.0000 | 2 | 0.0000 |
| `name_similarity_max` | 0.2727 | 0.6368 | 0.8889 | 25 | 0.0000 |
| `near_name_count` | 0.0000 | 0.1930 | 1.0000 | 2 | 0.0000 |
| `pair_inbound_count` | 0.0000 | 780.3811 | 4118.0000 | 1295 | 0.0000 |
| `pair_inbound_count_28d` | 0.0000 | 41.7853 | 192.0000 | 15 | 0.0000 |
| `pair_outbound_count` | 0.0000 | 1297.4879 | 4914.0000 | 1784 | 0.0000 |
| `pair_outbound_count_28d` | 0.0000 | 69.6594 | 232.0000 | 20 | 0.0000 |
| `pair_outbound_rate_per_day` | 0.0000 | 2.4948 | 8.2179 | 4656 | 0.0020 |
| `pair_recency_days` | 0.0021 | 0.9040 | 4.7895 | 688 | 0.0064 |
| `pair_recency_observed` | 0.0000 | 0.9936 | 1.0000 | 2 | 0.0000 |
| `pair_text_message_count` | 0.0000 | 2077.3270 | 9019.0000 | 2094 | 0.0000 |
| `recipient_is_internal` | 0.0000 | 0.9523 | 1.0000 | 2 | 0.0000 |
| `recipient_novel_to_sender` | 0.0000 | 0.0064 | 1.0000 | 2 | 0.0000 |
| `sender_history_available` | 0.0000 | 0.9980 | 1.0000 | 2 | 0.0000 |
| `sender_history_span_days` | 448.0000 | 522.5153 | 599.3627 | 3996 | 0.0020 |
| `sender_outbound_count` | 0.0000 | 49606.2473 | 61221.0000 | 3991 | 0.0000 |

Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.

| scenario_id | drafts | recipient_rows | recipient_novel_to_sender | domain_novel_to_sender | pair_outbound_count | content_similarity_observed | content_cosine | name_similarity_max | draft_text_empty | draft_text_oov | co_support_applicable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 4 | 4 | 0.0000 | 0.0000 | 1369.2500 | 1.0000 | 0.2250 | 0.8434 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 4 | 11 | 0.0000 | 0.0000 | 1431.3636 | 1.0000 | 0.2360 | 0.5465 | 0.0000 | 0.0000 | 1.0000 |
| S03 | 10 | 10 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.7025 | 0.0000 | 0.0000 | 0.0000 |
| S04 | 4 | 4 | 0.0000 | 0.0000 | 332.0000 | 1.0000 | 0.0165 | 0.7548 | 0.0000 | 0.0000 | 0.0000 |
| S05 | 319 | 886 | 0.0000 | 0.0000 | 3232.6027 | 1.0000 | 0.6387 | 0.4445 | 0.0000 | 0.0000 | 0.8420 |
| S06 | 10 | 10 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |  | 0.6961 | 0.0000 | 0.0000 | 0.0000 |
| S07 | 10 | 10 | 0.0000 | 0.0000 | 350.4000 | 1.0000 | 0.2849 | 0.7665 | 0.0000 | 0.0000 | 0.0000 |
| S08 | 5 | 28 | 0.0000 | 0.0000 | 2887.9643 | 1.0000 | 0.5700 | 0.4769 | 0.0000 | 0.0000 | 1.0000 |
| S09 | 11 | 16 | 0.6250 | 0.6250 | 1307.1250 | 0.1875 | 0.0285 | 0.4097 | 0.0000 | 0.1875 | 0.6250 |
| S11 | 2 | 2 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.6818 | 0.0000 | 0.0000 | 0.0000 |
| routine | 3621 | 3989 | 0.0000 | 0.0000 | 866.5325 | 1.0000 | 0.3801 | 0.6808 | 0.0000 | 0.0000 | 0.1441 |

Constant features in this subset: `contact_similarity_observed`, `draft_text_empty`.

Intended and unintended means use the stipulated label after scoring. They are not a precision or recall result, and the training mix is enriched.

| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |
| --- | --- | --- | --- | --- | --- |
| intended | 4948 | 1299.2148 | 0.0061 | 0.4275 | 0.6365 |
| unintended | 22 | 909.0909 | 0.0909 | 0.1578 | 0.7097 |

### `validation_diagnostic`

240 drafts, 582 recipient rows, 11 senders.

| Feature | Min | Mean | Max | Unique | Undefined |
| --- | --- | --- | --- | --- | --- |
| `address_similarity_max` | 0.2000 | 0.5290 | 0.8889 | 17 | 0.0000 |
| `addressed_recipient_count` | 1.0000 | 3.7320 | 6.0000 | 5 | 0.0000 |
| `co_focus_conditional_fraction` | 0.0000 | 0.7235 | 0.8827 | 208 | 0.2560 |
| `co_focus_history_available` | 0.0000 | 0.9141 | 1.0000 | 2 | 0.0000 |
| `co_joint_message_count` | 0.0000 | 1896.2509 | 3841.0000 | 144 | 0.0000 |
| `co_partner_fraction` | 0.0000 | 0.7969 | 1.0000 | 5 | 0.2216 |
| `co_support_applicable` | 0.0000 | 0.7784 | 1.0000 | 2 | 0.0000 |
| `contact_similarity_observed` | 1.0000 | 1.0000 | 1.0000 | 1 | 0.0000 |
| `content_cosine` | 0.0014 | 0.5416 | 0.7586 | 390 | 0.0945 |
| `content_similarity_observed` | 0.0000 | 0.9055 | 1.0000 | 2 | 0.0000 |
| `domain_novel_to_sender` | 0.0000 | 0.0515 | 1.0000 | 2 | 0.0000 |
| `domain_outbound_count` | 0.0000 | 44840.2526 | 57160.0000 | 162 | 0.0000 |
| `domain_seen_in_history` | 0.0000 | 0.9828 | 1.0000 | 2 | 0.0000 |
| `draft_body_blank` | 0.0000 | 0.0258 | 1.0000 | 2 | 0.0000 |
| `draft_raw_token_count` | 0.0000 | 18.6907 | 28.0000 | 18 | 0.0000 |
| `draft_subject_blank` | 0.0000 | 0.0086 | 1.0000 | 2 | 0.0000 |
| `draft_text_empty` | 0.0000 | 0.0000 | 0.0000 | 1 | 0.0000 |
| `draft_text_oov` | 0.0000 | 0.0086 | 1.0000 | 2 | 0.0000 |
| `draft_text_short` | 0.0000 | 0.0344 | 1.0000 | 2 | 0.0000 |
| `name_similarity_max` | 0.2727 | 0.4984 | 0.8889 | 22 | 0.0000 |
| `near_name_count` | 0.0000 | 0.0773 | 1.0000 | 2 | 0.0000 |
| `pair_inbound_count` | 0.0000 | 1143.1942 | 4099.0000 | 287 | 0.0000 |
| `pair_inbound_count_28d` | 0.0000 | 60.7285 | 192.0000 | 12 | 0.0000 |
| `pair_outbound_count` | 0.0000 | 2577.7766 | 4892.0000 | 324 | 0.0000 |
| `pair_outbound_count_28d` | 0.0000 | 137.5636 | 232.0000 | 16 | 0.0000 |
| `pair_outbound_rate_per_day` | 0.0000 | 5.0900 | 8.2171 | 348 | 0.0344 |
| `pair_recency_days` | 0.0021 | 0.3498 | 4.7650 | 192 | 0.0859 |
| `pair_recency_observed` | 0.0000 | 0.9141 | 1.0000 | 2 | 0.0000 |
| `pair_text_message_count` | 0.0000 | 3719.4880 | 8978.0000 | 376 | 0.0000 |
| `recipient_is_internal` | 0.0000 | 0.9227 | 1.0000 | 2 | 0.0000 |
| `recipient_novel_to_sender` | 0.0000 | 0.0859 | 1.0000 | 2 | 0.0000 |
| `sender_history_available` | 0.0000 | 0.9656 | 1.0000 | 2 | 0.0000 |
| `sender_history_span_days` | 448.0288 | 527.5396 | 596.3129 | 151 | 0.0344 |
| `sender_outbound_count` | 0.0000 | 51902.2234 | 60775.0000 | 151 | 0.0000 |

Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.

| scenario_id | drafts | recipient_rows | recipient_novel_to_sender | domain_novel_to_sender | pair_outbound_count | content_similarity_observed | content_cosine | name_similarity_max | draft_text_empty | draft_text_oov | co_support_applicable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 20 | 20 | 0.0000 | 0.0000 | 1483.4000 | 1.0000 | 0.2983 | 0.8232 | 0.0000 | 0.0000 | 0.0000 |
| S02 | 20 | 36 | 0.0000 | 0.0000 | 1213.0833 | 1.0000 | 0.2439 | 0.5969 | 0.0000 | 0.0000 | 0.7500 |
| S03 | 10 | 10 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |  | 0.7505 | 0.0000 | 0.0000 | 0.0000 |
| S04 | 20 | 27 | 0.0000 | 0.0000 | 514.5926 | 1.0000 | 0.3753 | 0.5081 | 0.0000 | 0.0000 | 0.5185 |
| S05 | 20 | 50 | 0.0000 | 0.0000 | 3183.3200 | 1.0000 | 0.6346 | 0.4299 | 0.0000 | 0.0000 | 0.8000 |
| S06 | 10 | 10 | 1.0000 | 1.0000 | 0.0000 | 0.0000 |  | 0.7386 | 0.0000 | 0.0000 | 0.0000 |
| S07 | 10 | 10 | 0.0000 | 0.0000 | 400.4000 | 1.0000 | 0.2719 | 0.7240 | 0.0000 | 0.0000 | 0.0000 |
| S08 | 70 | 340 | 0.0000 | 0.0000 | 3298.4853 | 1.0000 | 0.6189 | 0.4407 | 0.0000 | 0.0000 | 1.0000 |
| S09 | 40 | 50 | 0.4000 | 0.4000 | 1470.4000 | 0.5000 | 0.1832 | 0.5560 | 0.0000 | 0.1000 | 0.4000 |
| S11 | 20 | 29 | 0.3448 | 0.0000 | 1891.6552 | 0.6552 | 0.5840 | 0.5902 | 0.0000 | 0.0000 | 0.4138 |

Constant features in this subset: `contact_similarity_observed`, `draft_text_empty`.

Intended and unintended means use the stipulated label after scoring. They are not a precision or recall result, and the training mix is enriched.

| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |
| --- | --- | --- | --- | --- | --- |
| intended | 492 | 2863.0488 | 0.0813 | 0.6079 | 0.4610 |
| unintended | 90 | 1018.2889 | 0.1111 | 0.1713 | 0.7030 |

## Train-only shortcut checks

On 3955 train recipient rows (315 unintended), each feature's AUC for an unintended row is computed on its raw value. A feature is flagged when its AUC is above 0.95 or below 0.05. Flags are warnings to investigate; they do not decide intent. Separation is the larger of AUC and 1 − AUC.

| Feature | AUC | Separation | Flagged |
| --- | --- | --- | --- |
| `content_cosine` | 0.068 | 0.932 | no |
| `name_similarity_max` | 0.690 | 0.690 | no |
| `recipient_is_internal` | 0.371 | 0.629 | no |
| `co_focus_conditional_fraction` | 0.373 | 0.627 | no |
| `co_joint_message_count` | 0.374 | 0.626 | no |
| `co_partner_fraction` | 0.381 | 0.619 | no |
| `pair_inbound_count_28d` | 0.616 | 0.616 | no |
| `pair_inbound_count` | 0.614 | 0.614 | no |
| `domain_outbound_count` | 0.387 | 0.613 | no |
| `address_similarity_max` | 0.608 | 0.608 | no |
| `addressed_recipient_count` | 0.568 | 0.568 | no |
| `co_support_applicable` | 0.568 | 0.568 | no |
| `near_name_count` | 0.566 | 0.566 | no |
| `pair_recency_days` | 0.441 | 0.559 | no |
| `pair_recency_observed` | 0.458 | 0.542 | no |
| `recipient_novel_to_sender` | 0.542 | 0.542 | no |
| `co_focus_history_available` | 0.458 | 0.542 | no |
| `content_similarity_observed` | 0.459 | 0.541 | no |
| `sender_outbound_count` | 0.535 | 0.535 | no |
| `draft_raw_token_count` | 0.532 | 0.532 | no |
| `pair_text_message_count` | 0.525 | 0.525 | no |
| `pair_outbound_rate_per_day` | 0.519 | 0.519 | no |
| `draft_body_blank` | 0.515 | 0.515 | no |
| `draft_text_short` | 0.514 | 0.514 | no |
| `pair_outbound_count_28d` | 0.514 | 0.514 | no |
| `pair_outbound_count` | 0.510 | 0.510 | no |
| `sender_history_span_days` | 0.506 | 0.506 | no |
| `domain_novel_to_sender` | 0.496 | 0.504 | no |
| `sender_history_available` | 0.503 | 0.503 | no |
| `domain_seen_in_history` | 0.501 | 0.501 | no |
| `draft_text_oov` | 0.499 | 0.501 | no |
| `draft_subject_blank` | 0.499 | 0.501 | no |
| `contact_similarity_observed` | 0.500 | 0.500 | no |
| `draft_text_empty` | 0.500 | 0.500 | no |

Flagged features: none.

Five-minute recency: 0 of 3640 intended train rows (0.00%) and 6 of 315 unintended rows (1.90%) had earlier mail between the sender and that recipient, in either direction, less than five minutes before the draft (the `pair_recency_days` feature). Dataset check Q31 counts mail to the recipient from any sender and reports its own shares.

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

- Training S03 (10 drafts) has recipient novelty 1.0000; S06 (10 drafts) has recipient novelty 1.0000; S11 (30 drafts) has recipient novelty 1.0000. S03 and S06 are legitimate first contacts and S11 is a mistaken one, so novelty alone does not set the label.
- Mean observed content cosine on train by scenario: S01 0.221, S02 0.190, S04 0.036, S05 0.633, S07 0.273, S08 0.572, routine 0.376. Scenarios without pair text have no observed cosine.
- Training S01 name similarity averages 0.8291 against the 0.8 near-name threshold.
- `validation_product_like` has 22 unintended recipient rows; its intended-versus-unintended means are descriptive only.
- `validation_diagnostic` has 90 unintended recipient rows; its intended-versus-unintended means are descriptive only.
- The strongest single train separator is `content_cosine` (AUC 0.068, separation 0.932). No feature is outside [0.05, 0.95].

## Limitations

- No classifier was trained. No risk score, threshold, precision, recall, or false-warning rate is claimed.
- Content cosine is a real but imperfect train signal: AUC 0.068 (separation 0.932). Off-topic mistakes (S02, S04) sit low by their scenario definitions, while on-topic S08 mistakes, S01 lookalikes, and S11 first contacts are not separable by text. A later model comparison must still report a behavior-only model beside any content model.
- Novel recipients in train: 40 intended and 30 unintended rows. Novelty is evidence, not a label.
- IDF is frozen on sent mail before the validation window. It is not re-estimated at each earlier training draft. Historical counts and text centroids still stop at that draft's cutoff.
- Template sentences repeat across weeks. Stripping reference, ticket, and date slots removes unique generator tokens. It does not remove shared topic wording.
- Group-topic profiles are not implemented. A recipient with no direct pair history has no content centroid even if a broader group has discussed the topic.
- Diagnostic rows that share a family are dependent. Product-like families contain one draft. Scenario means pool variants, including clean twins, and are not one story. Do not read a diagnostic rate as the 0.5% prevalence result.
- The fictional history is dense weekly mail, so outbound counts and per-day rates are large. That scale is a property of the generator, not a real-world volume.
- Contact similarity is always observed on the exported subsets, because other directory entries are already visible. The unobserved-similarity and both-fields-empty fallbacks remain part of the contract and are covered by fixture tests.
- The frozen test subsets were not profiled here.
- Department is a directory field and is not a feature. Communication role is stored on the draft and is not a feature.
