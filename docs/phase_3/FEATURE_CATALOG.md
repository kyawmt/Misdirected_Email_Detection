# Phase 3 — Feature catalog

Feature specification: `med-features-v1`. Dataset: `med-synth-v2`.

Each addressed recipient of a draft becomes one row. The model matrix is the feature columns below, in this order. `draft_id`, `contact_id`, and `recipient_order` are join keys and are not features. A later model must not join scenario, label, split, subset, family, withheld contact, or role onto that matrix.

Communication role is stored on the draft and is not a feature. A Bcc address is not evidence of a mistake. The same history produces the same features whether the address is To, Cc, or Bcc.

No feature by itself decides that a recipient was unintended. Counts, novelty, similarity, and content cosine are signals for a later model. This phase does not combine them into a score.

Group-topic profiles are not in this version. A recipient with no direct pair history has no content centroid, even if other people have exchanged similar text.

## Where the numbers come from

History is sent mail strictly earlier than the draft, after the Phase 2 family and copied-body exclusions. The sender's outbound mail is a message whose sender is the draft sender. Inbound mail is a message whose sender is the recipient and whose recipients include the draft sender. A person who is only a co-recipient, with neither side as the author, does not count as pair mail.

The recent window is the half-open interval `[cutoff - 28 days, cutoff)`. Lifetime counts use the same cutoff and no start bound. Rates use days. The lifetime rate divides the pair's outbound count by the sender's observed span: the time from the sender's earliest kept outbound message to the cutoff, with a floor of one day. The 28-day counts are counts, not rates. A zero in a 28-day count is a measured zero. The calendar window exists even when it contains no mail.

Directory facts use `directory_visible_from <= cutoff`. A contact who appears in the directory only after the cutoff is not a similarity candidate. `recipient_is_internal` is the directory flag, not a label.

## Missing evidence

Unavailable evidence uses a fixed fallback plus an indicator. A measured zero keeps the indicator on and stores 0. Numeric features are finite. There are no missing cells in the matrix.

| Situation | What is stored |
| --- | --- |
| Sender has no earlier outbound mail | `sender_history_available = 0`, span `0`, rate `0`. Pair counts stay `0`. |
| No earlier inbound or outbound pair message | `pair_recency_observed = 0`, `pair_recency_days = 3650`. 3650 is not an age. |
| Sender has never written to this recipient | `recipient_novel_to_sender = 1`. This stays 1 when the recipient has written to the sender and the sender has not written back. |
| Sender has never written to this domain | `domain_novel_to_sender = 1`. `domain_seen_in_history` can still be 1 when someone else's earlier mail touches the domain. |
| One addressed recipient | `co_support_applicable = 0`. Partner fraction, conditional fraction, and joint count stay `0` and are not a measured lack of support. |
| Two or more recipients, but none of the sender's earlier mail to this recipient also includes another current addressee | `co_support_applicable = 1` and the fractions are measured zeros when the focus history exists. |
| No other contact is visible at the cutoff | `contact_similarity_observed = 0`. Both similarity maxima and `near_name_count` are `0`. |
| Draft text is empty, out of vocabulary, or the pair has no in-vocabulary history text | `content_similarity_observed = 0`, cosine `0`. `pair_text_message_count` still counts in-vocabulary pair messages when the draft itself cannot be compared. |
| Both sides have in-vocabulary text and share no terms | `content_similarity_observed = 1`, cosine `0`. That zero is measured. |

`draft_text_empty` is 1 only when the subject and the body are both blank. `draft_subject_blank` and `draft_body_blank` record the two fields separately. `draft_text_short` is 1 when content unigrams after preprocessing are fewer than 8. An empty draft is short and is not marked out of vocabulary. Out-of-vocabulary means the text is non-empty and the fitted vectorizer produces an empty vector.

## Relationship features

Research basis: communication frequency from Carvalho and Cohen (2007), recency from Balasubramanyan, Carvalho, and Cohen (2008). Internal and external status is directory context for later error analysis, not a finding from those papers.

| Feature | Definition |
| --- | --- |
| `sender_outbound_count` | Kept outbound messages from the draft sender. |
| `sender_history_available` | 1 when that count is positive. |
| `sender_history_span_days` | Days from the earliest of those messages to the cutoff, floored at 1. Fallback 0. |
| `pair_outbound_count` | Kept outbound messages that address this recipient in any role. |
| `pair_inbound_count` | Kept messages from this recipient that address the draft sender. |
| `pair_outbound_count_28d` | Outbound pair messages in the 28-day window. |
| `pair_inbound_count_28d` | Inbound pair messages in the 28-day window. |
| `pair_outbound_rate_per_day` | `pair_outbound_count / sender_history_span_days` when the sender span exists, else 0. |
| `pair_recency_days` | Days since the latest kept pair message in either direction. Fallback 3650. |
| `pair_recency_observed` | 1 when at least one kept pair message exists. |
| `recipient_novel_to_sender` | 1 when `pair_outbound_count` is 0. |
| `domain_outbound_count` | Kept outbound messages that address at least one recipient at this domain. A message counts once per domain. |
| `domain_novel_to_sender` | 1 when `domain_outbound_count` is 0. |
| `domain_seen_in_history` | 1 when any kept message has this domain as its sender domain or as a recipient domain. |
| `recipient_is_internal` | 1 when the directory marks the recipient internal. |

## Recipient-group features

Research basis: recipient co-occurrence from Carvalho and Cohen (2007). Stolfo et al. (2006) motivate treating an unusual combination as a supporting signal. Pairwise co-occurrence on the sender's own outbound mail is the substitute used here, not a full communication-group model.

The current addressee set is the draft's unique recipients. For the focus recipient, a joint message is an earlier outbound message that includes the focus recipient and at least one other current addressee.

| Feature | Definition |
| --- | --- |
| `addressed_recipient_count` | Unique recipients on the draft. |
| `co_support_applicable` | 1 when that count is at least 2. |
| `co_joint_message_count` | Joint messages. Forced to 0 when co-support does not apply. |
| `co_partner_fraction` | Share of the other current recipients who appear with the focus recipient in at least one kept outbound message. Defined only when co-support applies. |
| `co_focus_conditional_fraction` | Joint messages divided by outbound messages to the focus recipient. Defined only when co-support applies and `co_focus_history_available` is 1. |
| `co_focus_history_available` | 1 when the sender has at least one kept outbound message to this recipient. |

An unseen combination is `co_support_applicable = 1` and `co_partner_fraction = 0`. A single recipient is `co_support_applicable = 0`, which is a different state.

## Contact similarity

Display names and address local-parts are compared with normalized Levenshtein similarity: `1 - edit_distance / max(length)`. Names are casefolded with collapsed whitespace. The local-part is the text before `@`, casefolded.

Candidates are other contacts already visible at the cutoff. The recipient is excluded by contact id and by email address. The withheld-contact field is not read, and the nearest contact's id is not a feature. `near_name_count` counts candidates whose display-name similarity is at least 0.8. That threshold is part of the specification. It was not chosen by looking at the frozen test.

| Feature | Definition |
| --- | --- |
| `name_similarity_max` | Highest display-name similarity among candidates. Fallback 0. |
| `address_similarity_max` | Highest local-part similarity among candidates. Fallback 0. |
| `contact_similarity_observed` | 1 when at least one candidate exists. |
| `near_name_count` | Candidates at or above name similarity 0.8. Fallback 0. |

A high name similarity is context for a possible lookalike. It is not a finding that the sender selected the wrong person. Carvalho and Cohen (2007) discuss address confusion; the similarity function itself is a project choice.

## Content compatibility

Research basis: TF-IDF cosine between a message and prior sender–recipient text, from Carvalho and Cohen (2007). The vectorizer is scikit-learn `TfidfVectorizer` with L2 normalization, smoothed IDF, and no sublinear TF. The analyzer emits unigrams and adjacent bigrams after the preprocessor below. A term must appear in at least two fit documents.

The fit corpus is every sent message with `sent_at` strictly before the validation window (`2025-03-31T00:00:00Z`), after dropping documents that have no content tokens. Warmup mail is included. Validation and test text is not. IDF is frozen for the whole specification. It is not re-estimated at each earlier training draft. The centroid for a draft still uses only that draft's kept pair messages.

The pair profile is the mean of the L2-normalized TF-IDF vectors of kept inbound and outbound pair messages that contain at least one in-vocabulary token, renormalized to unit length. Cosine is the dot product with the draft vector. Values are clipped into `[0, 1]` only for floating-point noise within `1e-9`.

| Feature | Definition |
| --- | --- |
| `content_cosine` | Cosine similarity. Fallback 0 when it was not measured. |
| `content_similarity_observed` | 1 when the draft vector is non-empty and at least one pair message contributed to the centroid. |
| `pair_text_message_count` | Pair messages that contributed a non-empty vector, including when the draft itself could not be compared. |
| `draft_raw_token_count` | Content unigrams in the draft. |
| `draft_text_empty` | 1 when subject and body are both blank. |
| `draft_text_short` | 1 when `draft_raw_token_count < 8`. |
| `draft_text_oov` | 1 when the draft is non-empty and the vector is empty. |
| `draft_subject_blank` | 1 when the subject is blank. |
| `draft_body_blank` | 1 when the body is blank. |

Zilberman et al. (2013) motivate comparing content beyond direct pair frequency. A group-topic centroid would be a later optional experiment. It is not part of `med-features-v1`, so no feature claims that kind of support.

## Preprocessing and generator slots

Bodies carry a unique `Ref:` token, replies carry `Ack` plus an id, and templates carry `Ticket T-#####` plus an ISO date. Those strings are generator slots. Before tokenization the preprocessor:

- casefolds the text
- deletes message and draft ids of the form `m` or `d` plus six digits
- deletes ticket ids `t-` plus digits
- deletes ISO dates `YYYY-MM-DD`
- drops the exact tokens `ref` and `ack`, a fixed English stop list, and tokens shorter than two characters
- drops pure digit tokens

The same analyzer fits the vocabulary and transforms every later message. A unique reference cannot become a high-IDF shortcut if a copied body were ever left in history. Shared template wording remains. The hash exclusion stops exact body copies. It does not stop a model from recognizing repeated topic phrases. Date removal stops the week stamp from acting as an identifier. It does not remove words such as "headcount" or "salary band".

Department is a visible directory field and is not a v1 feature.

## What this catalog does not claim

Paper results, including injected-recipient ranking scores, are not performance claims for this dataset. No risk score, threshold, precision, recall, or latency number is produced here. The descriptive distributions are in the [feature quality report](FEATURE_QUALITY_REPORT.md). Profile lookup and the batch/single-draft contract are in [profile and transform](PROFILE_AND_TRANSFORM.md). Parity checks are in [training and serving parity](TRAINING_SERVING_PARITY.md).
