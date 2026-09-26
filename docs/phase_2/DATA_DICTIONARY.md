# Phase 2 — Data dictionary

Status: `med-synth-v3` schema. The tables describe fictional people and fictional mail. A later scoring step may read only the columns marked model-visible. Every other column is an audit field used to build labels, splits, or leakage checks.

Empty strings mean "absent" for optional ids and for `asserted_intended`. Timestamps are UTC instants written as `YYYY-MM-DDTHH:MM:SSZ`. Booleans are `true` or `false`.

## contacts

One row per fictional person or external party. Addresses use reserved `.example` domains. `is_internal` is true when `domain` is `demo.example`.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `contact_id` | yes | Stable directory id. |
| `display_name` | yes | Fictional display name. |
| `email_address` | yes | Lowercase fictional address. |
| `domain` | yes | Domain portion of the address. |
| `is_internal` | yes | Belongs to the fictional organization. |
| `department` | yes | Directory department. Context for a person, not a label. |
| `directory_visible_from` | yes | First time the directory lists this contact. |
| `dataset_version` | no | `med-synth-v3` on every row. |

## messages

Mail that was sent in the fictional record. Replies are included. Counterfactual mistakes are not.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `message_id` | yes | Stable id, `m` plus six digits. |
| `thread_id` | no | Links a composed message to its reply. Audit key for the split check. |
| `family_id` | no | Groups a sent message with assessment drafts made from it. |
| `sender_contact_id` | yes | Sender. External parties appear here only on replies. |
| `sent_at` | yes | Send time. History for a draft keeps rows strictly earlier than the draft. |
| `subject` | yes | Plain-text subject. May be empty only for little-text cases. |
| `body` | yes | Plain-text body. May be empty only for little-text cases. |
| `body_hash` | no | Hash of the normalized non-empty body. Empty bodies use an empty hash. |
| `message_kind` | no | `composed` or `reply`. |
| `generator_topic` | no | Topic assigned by the generator. Not a user-visible field and not a label. |
| `split` | no | `warmup`, `train`, `validation`, or `test`, derived from `sent_at`. |
| `dataset_version` | no | Dataset version. |

## message_recipients

One row per addressed recipient of a sent message. The same address is not repeated.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `message_id` | yes | Parent message. |
| `contact_id` | yes | Recipient. |
| `role` | yes | `to`, `cc`, or `bcc`. |
| `recipient_order` | yes | Zero-based order within the message. |

## drafts

Assessment candidates. A non-counterfactual draft matches one sent message. A counterfactual draft is an alternate addressing of a moment in time and is absent from `messages`.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `draft_id` | yes, as a join key only | Stable id, `d` plus six digits. Not a feature. |
| `family_id` | no | Same value for a source message, its clean twin, and its corrupted draft. |
| `source_message_id` | no | Sent message this draft was built from. Empty when the draft has no sent source. |
| `sender_contact_id` | yes | Internal sender. |
| `sent_at` | yes | Assessment cutoff. |
| `subject` | yes | Draft subject. |
| `body` | yes | Draft body. |
| `body_hash` | no | Same hash rule as messages. |
| `split` | no | Chronological split of `sent_at`. |
| `subset` | no | `train`, `validation_product_like`, `validation_diagnostic`, `test_product_like`, or `test_diagnostic`. |
| `scenario_id` | no | `S01`–`S11` or `routine`. Provenance only. |
| `scenario_variant` | no | Variant inside the scenario, including `clean_twin`. |
| `generator_topic` | no | Generator topic of the draft text. |
| `withheld_contact_id` | no | Contact the generator removed when it built a replacement mistake. Empty when nobody was removed. Missing an intended recipient is not itself a positive label. |
| `is_counterfactual` | no | True when this draft was not sent. |
| `is_walkthrough` | no | True for the curated cases that use the addresses in the scenario list. |
| `label_source` | no | `synthetic_stipulated` for every draft in this version. |
| `dataset_version` | no | Dataset version. |

## draft_recipients

One row per unique addressed recipient. Roles are preserved. This is the population that receives labels.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `draft_id` | yes, as a join key only | Parent draft. |
| `contact_id` | yes | Recipient. |
| `role` | yes | `to`, `cc`, or `bcc`. |
| `recipient_order` | yes | Zero-based order. |

## labels

One row per draft recipient. The target is whether that addressed recipient was intended.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `draft_id` | no | Draft being labeled. |
| `contact_id` | no | Addressed recipient. |
| `intended` | no | True when the generator stipulated that the sender meant to include this recipient. |
| `label_source` | no | `synthetic_stipulated`. |
| `label_confidence` | no | `certain` for every synthetic row in this version. |
| `scenario_id` | no | Copied from the draft for audit. |
| `stipulation` | no | Short explanation of why the generator assigned the bit. |
| `dataset_version` | no | Dataset version. |

A positive recipient is a row with `intended = false`. A positive email is a draft with at least one positive recipient. Unusual topic, a new contact, an external domain, or a similar name does not set this bit.

## reviewer_feedback

Illustrative review rows. They are not training labels. This version has no `accepted` row, so the effective label of every draft remains the synthetic stipulation.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `feedback_id` | no | Feedback id. |
| `draft_id` | no | Draft under review. |
| `contact_id` | no | Recipient the note is about. |
| `reviewer_id` | no | Fictional reviewer contact. |
| `submitted_at` | no | Time of the note. This is not a sent message and is not history. |
| `asserted_intended` | no | `true`, `false`, or empty when the reviewer did not assert a bit. |
| `confidence` | no | `certain` or `uncertain`. |
| `review_status` | no | `pending_review`, `accepted`, or `rejected`. |
| `notes` | no | Short review note. |
| `dataset_version` | no | Dataset version. |

## split_manifest

One row per draft. Later metrics should cluster rows that share `family_id` instead of treating those rows as independent emails.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `dataset_version` | no | Dataset version. |
| `draft_id` | no | Draft. |
| `family_id` | no | Dependence group. |
| `split` | no | Chronological split. |
| `subset` | no | Evaluation subset. |
| `sent_at` | no | Draft cutoff. |
| `scenario_id` | no | Scenario provenance. |
| `scenario_variant` | no | Variant provenance. |
| `is_misdirected_email` | no | True when any recipient label is unintended. |
| `is_walkthrough` | no | Curated scenario-list case. |
| `frozen` | no | True for `test_product_like` and `test_diagnostic`. Must agree with the draft's subset. |

## invalid_fixtures

Inputs that a future scorer should refuse. They are not drafts, not labeled, and not part of a split.

| Column | Model-visible | Meaning |
| --- | --- | --- |
| `fixture_id` | no | Fixture id. |
| `category` | no | `invalid_input` or `unavailable`. |
| `reason` | no | `no_recipients`, `malformed_address`, `unknown_snapshot`, or `too_many_recipients`. |
| `detail` | no | What is wrong with the example. |
| `expected_status` | no | `unable_to_assess`. |
| `dataset_version` | no | Dataset version. |

## Files

The published build is `data/med-synth-v3/`. `dataset_manifest.json` records the seed, row counts, freeze policy, and SHA-256 checksum of each table and of `quality_report.json`. Each `rows` value is the number of parsed CSV records, excluding the header. Newlines inside a quoted body do not add records. Split, subset, timestamp, family, scenario fields, and the frozen flag in `split_manifest` are copies of the draft row and are checked against it.
