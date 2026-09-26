# Project status

Last updated: 2026-09-26.

This file is the handoff for the next session. Standing rules are in [AGENTS.md](AGENTS.md).

## Completed phases

| Phase | State | What exists |
| --- | --- | --- |
| 1 — Product definition | Complete | Public requirements only. No implementation and no measured product metrics. |
| 2 — Data, labels, and splits | Complete | Fictional dataset `med-synth-v2`, generator `1.1.0`, seed `20260926`. |
| 3 — Behavioral and text features | Complete | `med-features-v1`: shared transform, frozen TF-IDF, train/validation matrices. No model. |
| 4 through 10 | Not started | No models, thresholds, API, UI, monitoring, or deployment. |

Phase 2 includes a follow-up correction on the same version line: manifest rows are checked against drafts, ordinary mail includes intended Bcc recipients, and published row counts are parsed CSV records. That correction changed generation rules, so the published dataset is v2 rather than a silent rewrite of v1.

## Active work

No implementation is in progress.

| Item | Owner |
| --- | --- |
| Active phase | None |
| Owner | Unassigned |

The next session should not start Phase 4 unless the user asks for it.

## Delivered artifacts

Phase 1:

- [docs/phase_1/PRODUCT_BRIEF.md](docs/phase_1/PRODUCT_BRIEF.md)
- [docs/phase_1/SCENARIOS.md](docs/phase_1/SCENARIOS.md)
- [docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md](docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md)
- [docs/phase_1/ACCEPTANCE_CRITERIA.md](docs/phase_1/ACCEPTANCE_CRITERIA.md)

Phase 2:

- [docs/phase_2/DATA_DICTIONARY.md](docs/phase_2/DATA_DICTIONARY.md)
- [docs/phase_2/LABELING_GUIDE.md](docs/phase_2/LABELING_GUIDE.md)
- [docs/phase_2/DATASET_SPECIFICATION.md](docs/phase_2/DATASET_SPECIFICATION.md)
- [docs/phase_2/DATA_QUALITY_AND_LEAKAGE.md](docs/phase_2/DATA_QUALITY_AND_LEAKAGE.md)
- Package `src/med_data/` (`generate`, `scoring_view`, `validate`, `build` / `validate` CLI)
- Tests in `tests/test_phase2.py`
- Published tables in `data/med-synth-v2/`

Phase 3:

- [docs/phase_3/FEATURE_CATALOG.md](docs/phase_3/FEATURE_CATALOG.md)
- [docs/phase_3/PROFILE_AND_TRANSFORM.md](docs/phase_3/PROFILE_AND_TRANSFORM.md)
- [docs/phase_3/FEATURE_QUALITY_REPORT.md](docs/phase_3/FEATURE_QUALITY_REPORT.md)
- [docs/phase_3/TRAINING_SERVING_PARITY.md](docs/phase_3/TRAINING_SERVING_PARITY.md)
- Package `src/med_features/` (shared batch and single-draft transform, train-only TF-IDF)
- Tests in `tests/test_phase3.py`
- Artifacts in `artifacts/med-features-v1/` (`text_transformer.joblib`, schema, fit metadata, quality report, three feature matrices)

Exported recipient rows, train and validation only:

| Subset | Drafts | Recipient rows |
| --- | --- | --- |
| `train` | 1000 | 2320 |
| `validation_product_like` | 1000 | 2265 |
| `validation_diagnostic` | 64 | 192 |

Text fit: 17,954 sent documents before `2025-03-31T00:00:00Z`, vocabulary size 600. Two empty documents in that window were skipped. Warmup is included. Validation and test text is not. Group-topic profiles were not built.

Published subset counts:

| Subset | Drafts | Misdirected | Legitimate | Frozen |
| --- | --- | --- | --- | --- |
| `train` | 1000 | 100 | 900 | No |
| `validation_product_like` | 1000 | 5 | 995 | No |
| `validation_diagnostic` | 64 | 28 | 36 | No |
| `test_product_like` | 2000 | 10 | 1990 | Yes |
| `test_diagnostic` | 79 | 35 | 44 | Yes |

Sent messages: 29,246 records. Drafts: 4,143 records. Product-like misdirection is exactly 0.5%. Train enrichment is exactly 10%. Intended Bcc recipients in the checked subsets: train 34, validation product-like 36, validation diagnostic 1, test product-like 54. Train still has unintended Bcc recipients from S08.

`data/med-synth-v1/` has been removed. Do not regenerate it.

## Verified results

Verified on 2026-09-26 from the repository root with the project virtualenv:

| Command | Result |
| --- | --- |
| `pytest` | 29 passed in 133.15s |
| `python -m med_data validate --data data/med-synth-v2` | 30 checks passed |
| `python -m med_features build --data data/med-synth-v2 --output artifacts/med-features-v1 --quality-markdown docs/phase_3/FEATURE_QUALITY_REPORT.md` | Wrote `med-features-v1` |

The 29 tests cover the Phase 2 data contract and the Phase 3 feature contract: hand-checked counts, cutoff and family and copied-body exclusions, train-only vocabulary fitting, contact self-exclusion, cold starts, empty and out-of-vocabulary text, metadata isolation, batch/single-draft parity, artifact reload, and refusal of frozen subsets. `pytest` also checks that the published transformer and one training draft match `artifacts/med-features-v1`.

No detection, calibration, threshold, or latency metric has been measured. Acceptance criteria AC01–AC09 remain unimplemented as product behavior. AC10's documentation boundary is in force for public files.

## Known gaps

- Template sentences repeat across weeks. Unique `Ref` tokens stop exact body copies across splits. They do not stop a model from memorizing topic phrasing.
- The product-like test has 10 misdirected emails. Recall on that set will be coarse. Use `test_diagnostic` to inspect scenarios, and do not quote its rate as the 0.5% prevalence result.
- Real-world prevalence is unknown. 0.5% is a simulation assumption. Reporting precision at the 10% training mix would overstate the operating point.
- Replies are one sentence and do not quote the parent. Threads are a message plus that reply.
- Department and directory dates are visible to a future scorer as directory facts. They are not intent labels.
- S10 invalid fixtures are described and excluded from training. Nothing scores them yet.
- No model, threshold policy, API, or UI exists. `FeatureError` is in-process only. A later API should map it to `unable_to_assess`.
- IDF is frozen on mail before the validation window. It is not re-estimated at each earlier training draft. Counts and centroids still stop at the draft cutoff.
- Group-topic profiles are deferred.
- Exported matrices always observe at least one other directory contact. Train never blanks both subject and body. Those fallbacks are specified and covered by fixtures.
- Outbound counts are large because the generator writes dense weekly mail. That scale is not a real-world volume.

## Next steps

When the user asks for Phase 4, and only then:

1. Read the Phase 4 section of `project_context/PROJECT_PLAN.md` and the feature catalog.
2. Train on `train` using `FEATURE_COLUMNS` only. Do not train on key columns, split, subset, scenario, label, family, or role.
3. Compare an always-allow baseline, a simple rules baseline, logistic regression, and one small tree. Keep the recorded comparison small.
4. Use validation for model selection. Leave `test_product_like` and `test_diagnostic` untouched.
5. Do not select thresholds or cite paper metrics as results for this dataset.

The feature build command refuses the frozen subsets. A later one-time evaluation may call the same transform on them. Keep public documents free of private planning context.
