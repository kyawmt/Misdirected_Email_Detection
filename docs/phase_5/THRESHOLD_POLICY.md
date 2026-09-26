# Phase 5 — Threshold policy

Policy `med-policy-v2` applies to model `med-model-v2` (run `logistic_all_balanced`), features `med-features-v2`, and dataset `med-synth-v4`. It lives in `artifacts/med-policy-v2/policy.json`.

## Decision rule

| Item | Rule |
| --- | --- |
| email_risk | maximum recipient risk score |
| allow | email_risk < T_warn |
| warn | email_risk >= T_warn (equality warns) |
| block | disabled |
| flagged_recipients | every recipient with risk score >= T_warn |

`T_warn = 0.9996767050340489`. `blocking_enabled: false`. `T_block: null`. The decision function never returns `block`. Scores are **risk scores**; `calibration: not_fit`.

## Selection

Candidates are the distinct email risk scores on the subset plus one cutoff above every score. Keep candidates with 0 false interventions, maximize email recall, break ties with the highest cutoff.

| Item | Value |
| --- | --- |
| Selection subset | `validation_product_like`, email level |
| Candidates | 3999 |
| Candidates with 0 false interventions | 9 |
| Chosen recall | 8 / 20 = 0.400 |
| Chosen false interventions | 0 / 3980 |
| Tied candidates | 1 |
| Highest legitimate email risk score | 0.997371 |

`T_warn` equals the risk score of the lowest-scoring warned mistake on validation. The highest legitimate email scores 0.997371, 2.31e-03 below it. A small shift in legitimate scores on new data would add false warnings.

## Budget

| Item | Definition |
| --- | --- |
| intervention | a warn or a simulated block, counted once per email |
| rate | false interventions per 1,000 legitimate emails |
| denominator | all legitimate emails in the evaluation subset |
| recall_denominator | all misdirected emails in the evaluation subset; an unassessed positive is not a detection |
| budget_per_1000 | 1.0 |

`validation_product_like` has 3980 legitimate emails, so one false warning is 0.251 per 1,000. Its confidence bound is not independent confirmation of the budget, because this subset selected the cutoff.

## Calibration

`calibration: not_fit`. validation_product_like has 20 misdirected emails. Separate chronological portions for calibration and threshold selection would leave about 10 positives in each, too few to fit a calibrator and still choose a cutoff. validation_diagnostic is not the operating mix and train fit the model. A reliability table on validation_diagnostic is a shape check only.

## Scoring-path parity

`T_warn` was selected on batch scores from the published feature CSV (lossless float round trip). Before `policy.json` was written, every `validation_product_like` draft was scored again with assess_draft on each draft with features computed in memory, the function the API calls.

| Item | Value |
| --- | --- |
| Drafts compared | 4000 |
| Identical decisions | 4000 / 4000 |
| Largest email risk score difference | 3.89e-15 (bound 1e-12) |
| Draft at `T_warn`: `d003028` | batch 0.9996767050340489, single-draft 0.9996767050340489, warn |

Scores are not required to be bit-identical across the two paths, because summation order can differ. Decisions are required to match on every draft, and they do.

## Validation confusion at the cutoff

| Level | n | Positives | TP | FP | FN | TN |
| --- | --- | --- | --- | --- | --- | --- |
| email | 4000 | 20 | 8 | 0 | 12 | 3980 |
| recipient | 4970 | 22 | 9 | 0 | 13 | 4948 |

Warnings: 8. Blocks: 0.

## Load checks

The decision function loads `policy.json` with the model bundle and refuses to decide when:

- the policy file is missing, unreadable, or lacks a required field
- the policy, model, or feature-spec version differs from the installed one, or the model run name differs
- the SHA-256 of `model.joblib` or of the feature `artifact_manifest.json` differs from the value in the policy
- blocking is enabled, `T_block` is set, `T_warn` is not a finite number, or the policy claims calibrated scores

Any of these, or a feature or model error while scoring, returns `unable_to_assess` with no decision and no risk score. It never returns allow.

## Checksums

| File | SHA-256 |
| --- | --- |
| model.joblib | `f698b69f7ff20fc9df9068ff06c1be44c9c6bc8ee6ce8cfacea851dbd7f9dfaa` |
| artifact_manifest.json | `b9ef336f22952042cb64c61b6080a2040bec9b232848f93729b645e2e4d5fff9` |

Selected on validation_product_like only. test_product_like and test_diagnostic were not read.

`validation_scores.csv` stores email risk scores with 17 significant digits and a `warned` column computed from the in-memory comparison. Read it with round-trip float parsing (for pandas, `float_precision="round_trip"`): the lowest warned validation mistake scores exactly `T_warn`, and a lossy parse can move it below the cutoff.
