# Phase 2 — Dataset specification

Version: `med-synth-v4`. Generator: `1.3.0`. Seed: `20260926`.

The published tables are in `data/med-synth-v4/`. Regenerating with this seed and generator version reproduces those files, including checksums in `dataset_manifest.json`. Changing the seed, the quotas, or the generation rules requires a new dataset version. The frozen test subsets belong to this version only.

`med-synth-v4` supersedes `med-synth-v2`. An intermediate `med-synth-v3` was built with the same quotas but left content cosine as a near-perfect separator on train (AUC 0.98 for misdirected rows); its test subsets were never evaluated, and it was replaced before any feature, model, or policy was built on it. Relative to `med-synth-v2`:
- Each topic has one template whose wording overlaps a neighbouring topic (budget with purchase orders, compensation with headcount and cost centers, facilities with equipment and kickoffs), so text similarity is a partial signal rather than a topic fingerprint.
- Half of the single-recipient S08 Cc and Bcc mistakes add an on-topic colleague: someone who regularly receives the sender's project updates but was not meant for that thread. Text similarity cannot separate those mistakes. The other half keep the lookalike or vendor addition.
- Lookalike pairs share some topics, so S01 wrong recipients have partial topic history.
- Send scheduling spreads routine mail across working hours, and scenario sends carry seeded jitter in hour, minute, and second. On train, 1.37% of intended and 1.90% of unintended recipient rows have same-recipient mail in the five minutes before the draft (Q31).
- Scenario S11 (mistaken first contact) adds unintended autocomplete selections from directory contacts who have never been emailed.
- S07 (legitimate topic change) training coverage is increased to 36 drafts across diverse topics.
- Sample sizes are expanded to support evaluation of the 1 per 1,000 false-intervention warning budget: 3,000 train drafts (300 misdirected), 4,000 product-like validation drafts (20 misdirected), and 6,000 product-like test drafts (30 misdirected). Diagnostic subsets contain at least 10 families per applicable scenario.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m med_data build --output data/med-synth-v4
python -m med_data validate --data data/med-synth-v4
pytest tests/test_phase2.py
```

`build` runs the quality checks before it writes. `validate` reloads the tables, checks the SHA-256 manifest, and runs the same checks.

## What the generator builds

One fictional organization, `demo.example`, exchanges plain-text mail with internal contacts and with external parties on other `.example` domains. Maya Okonkwo (`maya@demo.example`) is the main sender. The record also includes mail among teammates so relationships are not a single outbox.

Each composed message has a short reply 30 seconds later. Reply text does not quote the parent body. Sent messages are the communication record. A counterfactual mistake is stored only as a draft, so later mail does not observe the mistake as if it had been sent.

Topics are staffing, office equipment, facilities, purchase scheduling, budget, compensation, project status, kickoff, and introductions. Relationships still have characteristic topics, and the Q17 allow-lists keep scenario stories intact (a vendor normally handles purchase scheduling; an S04 recipient has no earlier compensation mail). Shared vocabulary across topics, lookalike teammates with overlapping topics, and on-topic S08 mistakes keep content from being a perfect separator.

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
| S11 mistaken first contact | `blake.mendoza@demo.example` instead of `noah@demo.example` |

Parallel lookalike pairs, vendors, facilities contacts, and one-shot collaborators supply the same situations in train and validation without reusing Jordan, Rina, Elliot, or Blake before their test drafts.

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
| `train` | 3000 | 300 | Learning mix. 10% misdirected by construction. |
| `validation_product_like` | 4000 | 20 | Same 0.5% rate as the product-like test. Used for threshold selection. |
| `validation_diagnostic` | 240 | 80 | Paired challenge cases (10 per scenario) for error analysis. |
| `test_product_like` | 6000 | 30 | Frozen rare-event set. Evaluates the product-like false-intervention rate. |
| `test_diagnostic` | 256 | 88 | Frozen challenge set, including the walkthrough (10 per scenario + walkthroughs). |

Diagnostic misdirected fractions are approximately 0.33 to 0.35. Each corrupted diagnostic draft has a clean twin in the same family, which is why legitimate rows outnumber misdirected rows even though every core mistake type is present. The 0.5% product-like sets are the prevalence-sensitive evaluation. The diagnostic sets exist so each scenario can be inspected.

Clean twins and the S08 walkthrough variants share a family. Product-like families contain one draft. A later report that treats two rows from one family as two independent emails overstates the evidence.

## Prevalence assumption

Real-world misdirection prevalence is unknown. This dataset **assumes 0.5%** of product-like emails are misdirected (5 per 1,000; exactly 20/4000 on validation and 30/6000 on test). That number is a simulation choice. It is not a measured rate and not a precision target.

The training subset is enriched to 10% (300/3000) so later fitting can see each mistake type. Training prevalence is not the product operating point and must not be copied into a precision claim.

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

Train, both validation subsets, and both test subsets include legitimate first contacts (S03, S06), topic changes (S07), cold starts (S09), little-text mail (S09), and mistaken first contacts (S11). Misdirected lookalike (S01), added-external (S02), topic-mismatch (S04), multi-recipient (S08), little-text (S09), and mistaken first contact (S11) cases are in train and in both diagnostic subsets. The product-like test includes 30 misdirected drafts spread across these scenarios, on top of 5,970 legitimate drafts.

Sent mail from warmup through test includes project updates with an intended Bcc recipient. Those messages also appear as legitimate drafts in train, validation product-like, validation diagnostic, and test product-like. S08 Bcc additions remain unintended. Each of those drafts stays in the family and split of its source message.

Template wording still repeats across weeks. Exact bodies stay unique because each one carries its own reference token, and a non-empty body is not copied into another split.

S10 (malformed input, no recipients, unknown history reference, too many recipients) is represented only by `invalid_fixtures.csv`. Those rows expect `unable_to_assess`. They are not labels and not model-training rows.

## Reproducibility

`numpy.random.default_rng(20260926)` chooses template variants. Contact lists, lanes, quotas, and timestamps are fixed. Two builds write byte-identical CSV and JSON. The manifest stores SHA-256 checksums and parsed record counts so a hand edit is detectable with `python -m med_data validate`. A quoted newline inside a body is part of that record, not an extra row.
