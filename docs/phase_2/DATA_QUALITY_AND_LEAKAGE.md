# Phase 2 — Data quality and leakage checklist

The executable checks live in `src/med_data/validate.py`. `python -m med_data validate` runs them against `data/med-synth-v1` and compares file checksums with `dataset_manifest.json`. A generated `quality_report.json` records each check id, name, and result. The report below is the contract those checks enforce.

## Quality checks

| Id | Check |
| --- | --- |
| Q01 | Every published table has the columns in the data dictionary, in that order. |
| Q02 | Primary keys are unique, including the draft-recipient and label pairs. |
| Q03 | Senders, recipients, sources, withheld contacts, and feedback rows point at real parents. |
| Q04 | Addresses match a lowercase `.example` form. Draft senders are internal `@demo.example` contacts. |
| Q05 | Each message and draft timestamp falls in the window of its split. |
| Q06 | Warmup ends before train, train before validation, and validation before test. Warmup has no drafts. |
| Q07 | Every draft recipient has one label. Labels are `synthetic_stipulated` and `certain`. The manifest misdirected flag matches the labels. |
| Q08 | Each draft has 1–20 unique recipients, and roles are `to`, `cc`, or `bcc`. |
| Q09 | Product-like counts are exactly 100/1000 train, 5/1000 validation, and 10/2000 test. |
| Q10 | A family has one split and one subset. A product-like family has one draft. |
| Q11 | A non-empty body hash appears in only one split. |
| Q12 | A thread id appears in only one split. |
| Q13 | Every misdirected draft is counterfactual, and its recipient set was not sent under that family. |
| Q14 | Every non-counterfactual draft matches its sent message in sender, time, text, and recipients. |
| Q15 | No sent message in the draft's family, and no copy of its non-empty text, is strictly earlier than the draft. |
| Q16 | Nobody is addressed before `directory_visible_from`. |
| Q17 | Sent mail obeys the topic allow-lists for lookalike pairs, vendors, and facilities contacts. |
| Q18 | S01–S09 drafts match the structural rules in the labeling guide, including first-contact, new-domain, and cold-start history. |
| Q19 | The walkthrough drafts are in frozen `test_diagnostic` and use the canonical addresses. S04 and S07 for Sam share a cutoff. |
| Q20 | Feedback contains an uncertain pending row and a rejected row, and no accepted row. |
| Q21 | A scoring view of a train draft contains none of the denylisted names. |
| Q22 | `frozen` is true exactly on `test_product_like` and `test_diagnostic`. |
| Q23 | `dataset_version` is `med-synth-v1` and the seed is `20260926`. |
| Q24 | An empty subject or body occurs only on S09 little-text variants, and those variants are empty in one of the two fields. |
| Q25 | Invalid fixtures are separate from drafts and expect `unable_to_assess`. |
| Q26 | Product-like sets contain the legitimate hard negatives. Diagnostic sets contain S01–S09, the S08 role variants, clean twins, and a misdirected fraction between 0.35 and 0.70. |
| Q27 | Sent timestamps are unique. |
| Q28 | Non-empty bodies carry the marker phrase of their generator topic. |

## Leakage rules

History for a draft at time T is the set of **sent** messages with `sent_at` strictly earlier than T, minus:

- any message with the draft's `family_id`
- any message whose non-empty body hash equals the draft body or another non-empty body in that family

Empty bodies are not treated as copied text. Several little-text drafts are empty on purpose.

These exclusions are what `visible_history` implements. Q15 checks the same properties for every draft. The walkthrough S01 draft is also checked directly: its history is non-empty, earlier than the draft, and outside its family.

Why the family rule exists: a diagnostic pair shares text with the sent source at the same timestamp. The cutoff already hides that source, because the source is not *strictly* earlier. The family and hash rules still apply so a source stored even a minute earlier cannot show the clean recipients and the same body to the corrupted draft.

Counterfactual drafts are omitted from `messages`. A later draft therefore cannot treat a mistaken recipient as someone the sender has already written to.

Generator fields that would reveal the answer stay out of the scoring view: scenario id, variant, topic code, withheld contact, counterfactual flag, family id, split, subset, labels, stipulations, and feedback. `split` is especially unsafe as a feature because the training subset is enriched to 10% positives and the product-like subsets are at 0.5%.

Thread ids do not cross splits, and a non-empty body is not copied from one split into another. Recurring templates are expected. Exact bodies include a unique `Ref` token so the hash check can tell a copy from a shared pattern.

Warmup mail is visible to later drafts. That is history, not label leakage. The label columns are not on those messages.

## Known limits of this dataset

- Identities, mail, and labels are fictional. Quality checks show that the generator followed its own rules. They do not measure detection accuracy.
- Template language repeats across time. A later model can memorize phrases that travel with a topic. The hash check blocks exact copies across splits; it does not block a shared writing style.
- Replies are one sentence and do not quote earlier text. Threads are a message plus that reply, not a long conversation.
- Product-like test contains 10 misdirected emails. A later recall estimate on those 10 rows will be coarse. The diagnostic set is the place to inspect scenario behavior, and its rate is not the product prevalence.
- Training enrichment will inflate precision if a later report uses the train base rate as if it were the deployment mix.
- Department and directory dates are available in the scoring view because they are directory facts. They are not proof of intent.
- Invalid fixtures describe refusal cases. Nothing in this phase scores them.

Phase 2 stops at this versioned, validated dataset. Feature transforms and model training are later work, and they need to consume `scoring_view` or an equivalent column allow-list rather than the audit tables.
