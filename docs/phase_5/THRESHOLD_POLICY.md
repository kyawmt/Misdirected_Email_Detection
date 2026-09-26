# Phase 5 — Threshold policy

Policy `med-policy-v1` applies to model `med-model-v1` (run `logistic_behavior_only_unweighted`), features `med-features-v1`, and dataset `med-synth-v2`. It lives in `artifacts/med-policy-v1/policy.json`.

## Decision rule

| Item | Rule |
| --- | --- |
| email_risk | maximum recipient risk score |
| allow | email_risk < T_warn |
| warn | email_risk >= T_warn (equality warns) |
| block | disabled |
| flagged_recipients | every recipient with risk score >= T_warn |

`T_warn = 0.13455666515724893`. `blocking_enabled: false`. `T_block: null`. The decision function never returns `block`. Scores are **risk scores**; `calibration: not_fit`.

## Selection

Candidates are the distinct email risk scores on the subset plus one cutoff above every score. Keep candidates with 0 false interventions, maximize email recall, break ties with the highest cutoff.

| Item | Value |
| --- | --- |
| Selection subset | `validation_product_like`, email level |
| Candidates | 1000 |
| Candidates with 0 false interventions | 5 |
| Chosen recall | 4 / 5 = 0.800 |
| Chosen false interventions | 0 / 995 |
| Tied candidates | 1 |
| Highest legitimate email risk score | 0.132046 |

`T_warn` equals the risk score of the lowest-scoring warned mistake on validation. The highest legitimate email sits just below it, at 0.132046. The margin is thin: a small shift in legitimate scores on new data would add false warnings.

## Budget

| Item | Definition |
| --- | --- |
| intervention | a warn or a simulated block, counted once per email |
| rate | false interventions per 1,000 legitimate emails |
| denominator | all legitimate emails in the evaluation subset |
| recall_denominator | all misdirected emails in the evaluation subset; an unassessed positive is not a detection |
| budget_per_1000 | 1.0 |

`validation_product_like` has 995 legitimate emails, so one false warning is already 1.005 per 1,000. Zero false warnings is the only point estimate within the budget there.

## Validation confusion at the cutoff

| Level | n | Positives | TP | FP | FN | TN |
| --- | --- | --- | --- | --- | --- | --- |
| email | 1000 | 5 | 4 | 0 | 1 | 995 |
| recipient | 2265 | 6 | 5 | 0 | 1 | 2259 |

Warnings: 4. Blocks: 0.

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
| model.joblib | `a7c79c91e0ba19ed18b166884229bef23d6c8e73cb4e530b54ce9788c1c7822c` |
| artifact_manifest.json | `4103b22d8da5a53b8608a22d1dda829c0bc3a2f8f97cc4fd36321b883892328f` |

Selected on validation_product_like only. test_product_like and test_diagnostic were not read.

`validation_scores.csv` stores email risk scores with 17 significant digits. Read it with round-trip float parsing (for pandas, `float_precision="round_trip"`). One warned validation mistake scores exactly `T_warn`, and a lossy parse moves it below the cutoff.
