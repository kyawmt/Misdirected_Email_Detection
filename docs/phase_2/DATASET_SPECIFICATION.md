# Phase 2 — Dataset specification

Version: `med-synth-v2`. Generator: `1.1.0`. Seed: `20260926`.

The published tables are in `data/med-synth-v2/`. Regenerating with this seed and generator version reproduces those files, including checksums in `dataset_manifest.json`. Changing the seed, the quotas, or the generation rules requires a new dataset version. The frozen test subsets belong to this version only.

`med-synth-v2` replaces `med-synth-v1` because generation changed: ordinary project mail now includes an intended Bcc recipient in history and in the labeled subsets. Prevalence quotas are unchanged (100/1000 enriched train, 5/1000 validation product-like, 10/2000 test product-like). The v1 test files are not a frozen evaluation set for this generator. `test_product_like` and `test_diagnostic` in v2 are the frozen subsets.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m med_data build --output data/med-synth-v2
python -m med_data validate --data data/med-synth-v2
pytest
```

`build` runs the quality checks before it writes. `validate` reloads the tables, checks the SHA-256 manifest, and runs the same checks.

## What the generator builds

One fictional organization, `demo.example`, exchanges plain-text mail with internal contacts and with external parties on other `.example` domains. Maya Okonkwo (`maya@demo.example`) is the main sender. The record also includes mail among teammates so relationships are not a single outbox.

Each composed message has a short reply 30 seconds later. Reply text does not quote the parent body. Sent messages are the communication record. A counterfactual mistake is stored only as a draft, so later mail does not observe the mistake as if it had been sent.

Topics are staffing, office equipment, facilities, purchase scheduling, budget, compensation, project status, kickoff, and introductions. Lookalike pairs keep those histories separate in sent mail: Alex Chan receives staffing, and Alex Chen receives equipment. Lee Park (`lee@vendor.example`) receives purchase scheduling. Sam Rivera receives facilities, plus one stipulated kickoff. Compensation mail in the sent record goes to people partners.

The canonical walkthrough drafts use the addresses from the scenario list and live in `test_diagnostic` with `is_walkthrough = true`:

| Case | Address used |
| --- | --- |
| S01 lookalike replacement | `alex.chen@demo.example` instead of `alex.chan@demo.example` |
| S02 added external | `lee@vendor.example` added to an internal budget draft |
| S03 new collaborator | `jordan@demo.example` |
| S04 and S07 | `sam@demo.example`, same cutoff, compensation versus an intended kickoff |
| S05 | internal project group, and `lee@vendor.example` on purchase scheduling |
| S06 new domain | `rina@newpartner.example` |
| S08 | one all-intended group, plus Cc, Bcc, and two-unintended variants in one family |
| Routine Bcc | project updates Bcc `lena@demo.example`, who is intended |
| S09 | `elliot.berg@demo.example` with no earlier mail, plus empty-text drafts |

Parallel lookalike pairs, vendors, facilities contacts, and one-shot collaborators supply the same situations in train and validation without reusing Jordan, Rina, or Elliot before their test drafts.

## Splits

Windows are half-open. A week belongs to one split. Warmup has sent mail and no assessment drafts.

| Split | Start (inclusive) | End (exclusive) | Role |
| --- | --- | --- | --- |
| warmup | 2024-01-08 | 2024-07-01 | History only |
| train | 2024-07-01 | 2025-03-31 | Enriched training drafts |
| validation | 2025-03-31 | 2025-09-01 | Product-like and diagnostic drafts |
| test | 2025-09-01 | 2026-01-05 | Frozen product-like and diagnostic drafts |

Subsets:

| Subset | Drafts | Misdirected | Role |
| --- | --- | --- | --- |
| `train` | 1000 | 100 | Learning mix. 10% misdirected by construction. |
| `validation_product_like` | 1000 | 5 | Same 0.5% rate as the product-like test. Available for later checks that are not the frozen test. |
| `validation_diagnostic` | 64 | 28 | Paired challenge cases for later error analysis. |
| `test_product_like` | 2000 | 10 | Frozen rare-event set. This is the denominator for a product-like false-intervention rate. |
| `test_diagnostic` | 79 | 35 | Frozen challenge set, including the walkthrough. Not a substitute for the product-like rate. |

Diagnostic misdirected fractions are about 0.44. Each corrupted diagnostic draft has a clean twin in the same family, which is why legitimate rows outnumber misdirected rows even though every core mistake type is present. The 0.5% product-like sets are the prevalence-sensitive evaluation. The diagnostic sets exist so each scenario can be inspected.

Clean twins and the four S08 walkthrough variants share a family. Product-like families contain one draft. A later report that treats two rows from one family as two independent emails overstates the evidence.

## Prevalence assumption

Real-world misdirection prevalence is unknown. This dataset **assumes 0.5%** of product-like emails are misdirected (5 per 1,000; exactly 5/1000 on validation and 10/2000 on test). That number is a simulation choice. It is not a measured rate and not a precision target.

The training subset is enriched to 10% (100/1000) so later fitting can see each mistake type. Training prevalence is not the product operating point and must not be copied into a precision claim.

If a later detector has recall `r` on misdirected emails and false-intervention rate `f` on legitimate emails, email precision at prevalence `p` is:

```text
precision(p) = (r * p) / (r * p + f * (1 - p))
```

The next table holds `r = 0.5` and `f = 0.001` fixed. Both numbers are hypothetical. `f = 0.001` matches the provisional budget of one false intervention per 1,000 legitimate emails. The recall is not a result from this project. The table only shows that precision moves when the assumed prevalence moves.

| Assumed prevalence | Illustrative precision |
| --- | --- |
| 0.1% | 0.3336 |
| 0.5% (this dataset's product-like assumption) | 0.7153 |
| 1% | 0.8347 |
| 2% | 0.9107 |

A result computed on the balanced diagnostic subset cannot be quoted as performance at 0.5% prevalence.

## Freeze

`test_product_like` and `test_diagnostic` are frozen. Feature work, model comparison, calibration, and threshold selection stay on train and validation. The frozen subsets are for a later one-time evaluation and for leakage tests. Rebuilding them in place after that evaluation has started is a new dataset version, not a silent refresh.

## Scenario coverage

Train, both validation subsets, and both test subsets include legitimate first contacts, new domains, topic changes, cold starts, and little-text mail. Misdirected lookalike, added-external, topic-mismatch, multi-recipient, and little-text cases are in train and in both diagnostic subsets. The product-like test includes 10 misdirected drafts spread across lookalike, added-external, topic-mismatch, and multi-recipient cases, on top of 1,990 legitimate drafts.

Sent mail from warmup through test includes project updates with an intended Bcc recipient. Those messages also appear as legitimate drafts in train, validation product-like, validation diagnostic, and test product-like. S08 Bcc additions remain unintended. Each of those drafts stays in the family and split of its source message.

Template wording still repeats across weeks. Exact bodies stay unique because each one carries its own reference token, and a non-empty body is not copied into another split. The product-like test still has only 10 misdirected emails, so a later recall number on that set will be coarse. The diagnostic set is for scenario inspection. Its misdirected fraction is not the 0.5% product-like prevalence.

S10 (malformed input, no recipients, unknown history reference, too many recipients) is represented only by `invalid_fixtures.csv`. Those rows expect `unable_to_assess`. They are not labels and not model-training rows.

## Reproducibility

`numpy.random.default_rng(20260926)` chooses template variants. Contact lists, lanes, quotas, and timestamps are fixed. Two builds write byte-identical CSV and JSON. The manifest stores SHA-256 checksums and parsed record counts so a hand edit is detectable with `python -m med_data validate`. A quoted newline inside a body is part of that record, not an extra row.
