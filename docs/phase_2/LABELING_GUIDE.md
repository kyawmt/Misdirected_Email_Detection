# Phase 2 — Labeling guide

Labels answer one question: **did the sender intend to address this recipient?** They do not answer whether the recipient looks unusual, new, external, or off-topic. Those facts are evidence a later model may use. They are not the target.

The unit of a label is one addressed recipient on one assessment draft. The unit of an email label is the draft. A draft is misdirected when at least one addressed recipient was unintended. A legitimate draft has none. Failing to include someone who was intended, while every addressed recipient was intended, is outside this task and is not a positive email.

## How synthetic labels are assigned

The generator stipulates the bit while it builds the draft. `label_source` is `synthetic_stipulated` and `label_confidence` is `certain`. The `stipulation` column records the rule in a sentence. Scenario ids record which story the row came from. None of those fields are model inputs.

| Situation | `intended` | Why |
| --- | --- | --- |
| Routine sent mail, including ordinary project, facilities, staffing, equipment, budget, and purchase messages | true for every addressed recipient | The generator addressed the people who belong on that topic. |
| S05 internal project update and S05 purchase-scheduling mail | true | Named routine cases from the scenario list. |
| S01 lookalike replacement | false for the contact who replaced the intended person; true for anyone else still addressed | The generator swapped in a similar contact. The similar name is not what makes the bit false. The swap is. |
| S02 added external recipient | false for the added vendor; true for the original internal recipients | The vendor was added to a budget draft. Being external is not the label. |
| S04 compensation text sent to a facilities contact | false for that contact | The generator addressed a familiar person with content stipulated for a people partner. |
| S08 extra Cc or Bcc recipient | false for each added contact; true for the original group | A draft may have one or two unintended recipients. The other recipients stay intended. |
| S08 all-intended group | true for every role | Mixed To, Cc, and Bcc is not a mistake. |
| S03 first direct contact | true | No earlier sent mail involves that contact. Novelty is not a positive label. |
| S06 first contact at a new external domain | true | The domain has no earlier sent mail. A new domain is not a positive label. |
| S07 kickoff to a facilities contact | true | The contact has earlier facilities mail and no earlier kickoff. A topic change is not a positive label. |
| S09 cold start | true | The sender has no earlier sent mail. Missing history is not a positive label. |
| S09 little text, legitimate | true | Subject or body is empty. Emptiness is not the label. |
| S09 little text, unintended | false for the swapped contact | The generator still swapped a recipient. Empty text does not decide the bit. |
| Clean twin | true for every addressed recipient | Same text and recipients as the sent source, paired with a corrupted draft for review. |

Sent history itself is not a labeled training table. Every sent message was addressed to the recipients the generator meant. Later phases may use that mail as behavior. They should not treat it as a second set of supervised email labels.

`withheld_contact_id` records a person the generator removed in a replacement mistake (S01 and S04). That person is not an addressed recipient of the mistaken draft, so they do not get a negative row. The detection task does not score people who were left off the message.

## Hard negatives

Hard negatives are legitimate drafts that are easy to confuse with mistakes:

- a first direct collaborator (S03)
- a first contact at an uncommon external domain (S06)
- a real topic change with an established contact (S07)
- a cold sender (S09)
- a nearly empty but intended note (S09)
- ordinary internal and external mail (S05 and `routine`)

They sit inside the product-like subsets as well as the diagnostic subsets. Their labels stay `intended = true`. An intervention on one of them would be a false intervention under the product definition.

## Positive class and aggregation

- **Positive recipient:** `intended = false`.
- **Positive email:** at least one positive recipient.
- **Legitimate email:** zero positive recipients.

Email-level counts in `split_manifest.is_misdirected_email` use that definition. Recipient-level metrics later have to use the label rows, because flagging a legitimate recipient on a misdirected draft is not correct attribution.

## Variants that must stay together

A corrupted draft and its clean twin share `family_id`, `split`, `subset`, and timestamp. The twin is legitimate. The corrupted draft is misdirected. Product-like subsets contain only one draft from a family, so a product-like denominator does not contain both versions of the same mail. Diagnostic subsets keep the pair. Later metrics should cluster on `family_id`. The rows are dependent.

Walkthrough S08 keeps four drafts in one family: the all-intended group, an unintended Cc, an unintended Bcc, and two unintended recipients. They share a body and a cutoff. They are diagnostic, not product-like.

## Reviewer feedback and uncertain labels

Review notes live in `reviewer_feedback` and never enter a scoring view.

| `review_status` | `confidence` | Effect on the label in this version |
| --- | --- | --- |
| `pending_review` | `uncertain`, with `asserted_intended` empty | None. The synthetic label stands. The note is waiting. |
| `pending_review` | `certain`, with an asserted bit | None. A certain assertion still waits for acceptance. |
| `rejected` | `certain` | None. The assertion was declined. |
| `accepted` | `certain` | Not present. An accepted note would be required before any later workflow could supersede a synthetic label. This dataset does not apply that supersession. Automatic retraining from a click is out of scope. |

The three illustrative rows are attached to train drafts so the rule can be tested. They are not evidence about those drafts beyond the rule itself.

## What is withheld from model inputs

A scoring view may include the draft cutoff, sender directory fields, subject, body, addressed recipients, and earlier sent mail. It does not include `intended`, `stipulation`, `scenario_id`, `scenario_variant`, `family_id`, `generator_topic`, `withheld_contact_id`, `is_counterfactual`, `is_walkthrough`, split or subset names, feedback, or invalid-fixture reasons. The denylist is `MODEL_INPUT_DENYLIST` in `src/med_data/schema.py`.

Scenario ids on a draft are answers. A later model that receives them is reading the label.
