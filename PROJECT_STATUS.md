# Project status

Last updated: 2026-09-26.

This file is the handoff for the next session. Standing rules are in [AGENTS.md](AGENTS.md).

## Completed phases

| Phase | State | What exists |
| --- | --- | --- |
| 1 — Product definition | Complete | Public requirements only. No implementation and no measured product metrics. |
| 2 — Data, labels, and splits | Complete | Fictional dataset `med-synth-v2`, generator `1.1.0`, seed `20260926`. |
| 3 — Behavioral and text features | Complete | `med-features-v1`: shared transform, frozen TF-IDF, train/validation matrices. |
| 4 — Baselines and model comparison | Complete | `med-model-v1`: always-allow, rules, logistic regression, one tree, ablations. No threshold. |
| 5 through 10 | Not started | No threshold policy, API, UI, monitoring, or deployment. |

Phase 2 includes a follow-up correction on the same version line: manifest rows are checked against drafts, ordinary mail includes intended Bcc recipients, and published row counts are parsed CSV records. That correction changed generation rules, so the published dataset is v2 rather than a silent rewrite of v1.

## Active work

No implementation is in progress.

| Item | Owner |
| --- | --- |
| Active phase | None |
| Owner | Unassigned |

The next session should not start Phase 5 unless the user asks for it.

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

Phase 4:

- [docs/phase_4/EXPERIMENT_TABLE.md](docs/phase_4/EXPERIMENT_TABLE.md)
- [docs/phase_4/COMPARISON.md](docs/phase_4/COMPARISON.md)
- [docs/phase_4/ABLATIONS.md](docs/phase_4/ABLATIONS.md)
- [docs/phase_4/MODEL_ARTIFACT.md](docs/phase_4/MODEL_ARTIFACT.md)
- [docs/phase_4/DECISION_RECORD.md](docs/phase_4/DECISION_RECORD.md)
- Package `src/med_models/` and `python -m med_models run`
- Tests in `tests/test_phase4.py`
- Artifact `artifacts/med-model-v1/` (`model.joblib`, `experiments.json`, `model_metadata.json`)

Selected scorer: `logistic_behavior_only_unweighted` (`C = 100`, no class weight). It does not use content cosine. On `validation_product_like` its email average precision is 0.891 with a family-bootstrap interval of 0.583 to 1.000 (5 positive emails out of 1,000). The all-features logistic reaches 1.000 on those same 5 emails. That gap is the generator topic shortcut. The behavior-only tree's product-like email average precision is 0.029, and the rules score is 0.410. Diagnostic email average precision for the selected model is 0.977 on 28 positive emails out of 64, which is not a 0.5% prevalence result. No threshold was chosen. Unobserved recency is filled with the training median of observed recency (one minute on this training set) and then log-transformed. Rewriting the product-like mistakes as first contacts moves their median risk from 0.9998 to about 0. A one-day recency-floor diagnostic (product-like email average precision 0.731) and a dropped-rate diagnostic (0.826) are recorded and are not selection candidates. `C = 100` is the top of the training grid.

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
| `pytest` | 44 passed in 174.22s |
| `python -m med_data validate --data data/med-synth-v2` | 30 checks passed |
| `python -m med_features build --data data/med-synth-v2 --output artifacts/med-features-v1 --quality-markdown docs/phase_3/FEATURE_QUALITY_REPORT.md` | Wrote `med-features-v1` |
| `python -m med_models run --features artifacts/med-features-v1 --data data/med-synth-v2 --output artifacts/med-model-v1 --docs docs/phase_4` | Wrote `med-model-v1`; selected `logistic_behavior_only_unweighted` |

The model run and `pytest` were repeated on 2026-09-26 after the Phase 4 review fixes (recency imputation, the two diagnostics, and the training-fold tie-break). The feature build row is the earlier result from the same date.

The 44 tests cover the data contract, the feature contract, the public-doc scan, and the model contract: audit columns rejected, train-only scaling, chronological family-safe folds, email-level maximum aggregation, deterministic logistic coefficients, artifact reload, frozen-subset refusal, the hand-written rules score, the recency imputation, the training-fold selection tie-break, and single-draft scoring parity with the batch path and with a `scoring_view` history. `pytest` also reloads `artifacts/med-model-v1` and checks that repeated scores match.

No detection, calibration, threshold, or latency metric has been measured. Acceptance criteria AC01–AC09 remain unimplemented as product behavior. AC10's documentation boundary is in force for public files. `tests/test_public_docs.py` scans `README.md` and `docs/` for private terms and for relative links that do not resolve.

## Known gaps

- Template sentences repeat across weeks. Unique `Ref` tokens stop exact body copies across splits. They do not stop a model from memorizing topic phrasing.
- Content cosine on the training rows separates stipulated mistakes from ordinary repeat mail almost completely, because restricted relationships keep separate topics. Misdirected rows are at or below about 0.06 cosine. The legitimate rows in that band are cold starts and first contacts. The four S07 topic-change rows sit just above the misdirected rows. Phase 4 must report a behavior-only model. A content-only score would restate the generator.
- No misdirected training row is a first contact. All 16 novel training recipients are legitimate (S03, S06, S09). On the refit model, rewriting a product-like mistake as a first contact still drops its median risk from 0.9998 to about 0. The training median of observed recency is one minute, so a missing history is filled with a recent gap. A mistaken first contact is not in `med-synth-v2`.
- Legitimate rows often have another message to the same recipient less than five minutes earlier (66.5% of 2,212 training rows, 68.3% of 2,259 product-like validation rows). No misdirected row does. Part of the behavior-only score is that generator timing.
- The product-like test has 10 misdirected emails. Recall on that set will be coarse. Use `test_diagnostic` to inspect scenarios, and do not quote its rate as the 0.5% prevalence result.
- Real-world prevalence is unknown. 0.5% is a simulation assumption. Reporting precision at the 10% training mix would overstate the operating point.
- Replies are one sentence and do not quote the parent. Threads are a message plus that reply.
- Department and directory dates are visible to a future scorer as directory facts. They are not intent labels.
- S10 invalid fixtures are described and excluded from training. Nothing scores them yet.
- No threshold policy, API, or UI exists. `FeatureError` is in-process only. A later API should map it to `unable_to_assess`.
- The selected model is a risk score, not a calibrated probability. Product-like validation has 5 positive emails, so the 0.891 average precision is unstable. Its `C` is 100, the least regularized point in the grid, and coefficients on overlapping counts are not separate effects.
- IDF is frozen on mail before the validation window. It is not re-estimated at each earlier training draft. Counts and centroids still stop at the draft cutoff.
- Group-topic profiles are deferred.
- Exported matrices always observe at least one other directory contact. Train never blanks both subject and body. Those fallbacks are specified and covered by fixtures.
- Outbound counts are large because the generator writes dense weekly mail. That scale is not a real-world volume.

## Next steps

When the user asks for Phase 5, and only then:

1. Read the Phase 5 section of `project_context/PROJECT_PLAN.md` and `docs/phase_4/DECISION_RECORD.md`.
2. Choose thresholds on validation only. Keep blocking disabled unless a separate check justifies it.
3. Score `test_product_like` and `test_diagnostic` once, after the policy is frozen. Cluster intervals on `family_id`.
4. Do not retune the model on those test scores, and do not quote diagnostic rates as the 0.5% prevalence result.
5. Leave the content-shortcut and novelty findings in the report next to any all-features number.

The feature build and the model runner both refuse the frozen subsets until that one-time evaluation. Keep public documents free of private planning context.
