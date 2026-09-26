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
| 5 — Evaluation and threshold policy | Complete | `med-policy-v1`: one warning cutoff on the risk score, blocking disabled, calibration not fit, one frozen test pass. |
| 6 through 10 | Not started | No API, UI, monitoring, or deployment. |

Phase 2 includes a follow-up correction on the same version line: manifest rows are checked against drafts, ordinary mail includes intended Bcc recipients, and published row counts are parsed CSV records. That correction changed generation rules, so the published dataset is v2 rather than a silent rewrite of v1.

## Active work

No implementation is in progress.

| Item | Owner |
| --- | --- |
| Active phase | None |
| Owner | Unassigned |

The next session should not start Phase 6 unless the user asks for it.

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

Phase 5:

- [docs/phase_5/EVALUATION_REPORT.md](docs/phase_5/EVALUATION_REPORT.md)
- [docs/phase_5/THRESHOLD_POLICY.md](docs/phase_5/THRESHOLD_POLICY.md)
- [docs/phase_5/ERROR_ANALYSIS.md](docs/phase_5/ERROR_ANALYSIS.md)
- [docs/phase_5/UNCERTAINTY_AND_PREVALENCE.md](docs/phase_5/UNCERTAINTY_AND_PREVALENCE.md)
- [docs/phase_5/MODEL_CARD.md](docs/phase_5/MODEL_CARD.md)
- Package `src/med_policy/` (`select`, `evaluate-test`, `latency`, `report`)
- Tests in `tests/test_phase5.py`
- Artifact `artifacts/med-policy-v1/` (`policy.json`, `validation_scores.csv`, `validation_evaluation.json`, `test_evaluation.json`, `latency.json`)

Policy: `T_warn = 0.13455666515724893` on the email risk score (maximum recipient risk score), chosen on `validation_product_like` only by the rule "0 false interventions, then maximum email recall, then highest cutoff". Equality warns. Blocking is disabled and `T_block` is null. `calibration: not_fit`. The highest legitimate validation email risk score is 0.132046, just below the cutoff. The rules baseline under the same rule gets cutoff 2/3.

| Subset | Warned mistakes | False interventions | Exact 95% upper, per 1,000 | Scored |
| --- | --- | --- | --- | --- |
| `validation_product_like` | 4 / 5 | 0 / 995 | 3.70 | selection |
| `validation_diagnostic` | 20 / 28 | 0 / 36 | not valid (shared families) | inspection |
| `test_product_like` | 5 / 10 | 0 / 1990 | 1.85 | once |
| `test_diagnostic` | 25 / 35 | 0 / 44 | not valid (shared families) | once |

The rules policy under the same validation rule warned 2 of 10 on `test_product_like` with 3 false interventions (1.51 per 1,000, outside the budget). Email precision of 1.000 at the policy cutoff is forced by zero observed false warnings; at the exact upper false-positive rate and 0.5% prevalence it would be 0.576 on the test pass. The frozen policy missed every S01 (lookalike) and S04 (familiar recipient, unusual topic) mistake in both test subsets, and warned on every S02, S08, and S09 mistake there. No S03, S05, S06, or S07 email was warned. Acceptance status: AC01 insufficient evidence (point 0 per 1,000, exact upper 1.85), AC02 met only for added-recipient mistakes (S02, S08) and not met for S01 and S04, AC03 met, AC04 met (disabled, 0 blocks). AC05, AC07, AC08, and AC09 are not met. AC06 is partial.

The test pass ran once, after `policy.json` was written. `test_evaluation.json` stores the SHA-256 of `policy.json`. Test features were computed in memory and no test feature file was written. Before that pass, in-memory scoring was checked against the published `validation_diagnostic` matrix (192 rows, maximum score difference below 1e-39).

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
| `pytest` | 65 passed in 186.01s |
| `python -m med_data validate --data data/med-synth-v2` | 30 checks passed |
| `python -m med_features build --data data/med-synth-v2 --output artifacts/med-features-v1 --quality-markdown docs/phase_3/FEATURE_QUALITY_REPORT.md` | Wrote `med-features-v1` |
| `python -m med_models run --features artifacts/med-features-v1 --data data/med-synth-v2 --output artifacts/med-model-v1 --docs docs/phase_4` | Wrote `med-model-v1`; selected `logistic_behavior_only_unweighted` |
| `python -m med_policy select` | Wrote `med-policy-v1`; `T_warn = 0.13455666515724893`; validation 4/5 warned, 0/995 false |
| `python -m med_policy evaluate-test` (run once) | `test_product_like` 5/10 warned, 0/1990 false; `test_diagnostic` 25/35 warned, 0/44 false; 0 scoring failures |
| `python -m med_policy latency` | In-process preliminary: p50 24.63 ms, p95 333.35 ms over 1000 calls; cold start 1.2 s. Not a backend measurement |
| `python -m med_policy refresh-validation-scores` | Rewrote `validation_scores.csv` with a `warned` column; `policy.json` SHA-256 unchanged; 1000 rows, 4 warned |
| `python -m med_policy report` | Wrote `docs/phase_5/` (regenerated after the Phase 5 review fixes) |

The model run was repeated on 2026-09-26 after the Phase 4 review fixes. The feature build row is the earlier result from the same date. The Phase 5 rows and `pytest` are from the Phase 5 session on 2026-09-26.

The 44 tests cover the data contract, the feature contract, the public-doc scan, and the model contract: audit columns rejected, train-only scaling, chronological family-safe folds, email-level maximum aggregation, deterministic logistic coefficients, artifact reload, frozen-subset refusal, the hand-written rules score, the recency imputation, the training-fold selection tie-break, and single-draft scoring parity with the batch path and with a `scoring_view` history. The Phase 5 tests cover the validation-only cutoff search and frozen-subset refusal, threshold equality, disabled blocking, maximum aggregation with every recipient at or above the cutoff flagged, `unable_to_assess` for a missing policy or non-finite score, version and checksum refusal, the one-shot test command's refusals, the absence of a test feature writer, the published policy against its validation table, and a decision path with every `fit` patched to fail.

No calibration was fit. No backend latency has been measured. AC05, AC07, AC08, and AC09 are not met; AC06 is partial (duplicate merging is not implemented). AC10's documentation boundary is in force for public files. `tests/test_public_docs.py` scans `README.md` and `docs/` for private terms and for relative links that do not resolve.

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
- No API or UI exists. The policy decision function returns `unable_to_assess` for a missing or mismatched policy, a feature or model error, or a non-finite score. A later API must keep that mapping and must not turn it into allow.
- `T_warn` sits just above the highest legitimate validation risk score (0.132046 against 0.134557). Small score drift on new mail would add false warnings. The cutoff must not be moved on test results.
- The warning budget cannot be supported at its required confidence with 995 or 1,990 legitimate emails: the exact upper bound for zero false warnings is 3.70 and 1.85 per 1,000.
- The behavior-only scorer misses lookalike replacements (S01) and familiar-recipient topic mistakes (S04). A mistaken first contact scores near 0.
- The in-process p95 was above 300 ms on this machine. That is not the AC05 result, which needs a backend and assumption A10's timing boundary.
- One warned validation mistake scores exactly `T_warn`. `validation_scores.csv` carries a `warned` column computed from the in-memory floats; use it as the decision audit. Recomputing from `email_risk` needs round-trip float parsing.
- The selected model is a risk score, not a calibrated probability. Product-like validation has 5 positive emails, so the 0.891 average precision is unstable. Its `C` is 100, the least regularized point in the grid, and coefficients on overlapping counts are not separate effects.
- IDF is frozen on mail before the validation window. It is not re-estimated at each earlier training draft. Counts and centroids still stop at the draft cutoff.
- Group-topic profiles are deferred.
- Exported matrices always observe at least one other directory contact. Train never blanks both subject and body. Those fallbacks are specified and covered by fixtures.
- Outbound counts are large because the generator writes dense weekly mail. That scale is not a real-world volume.

## Next steps

When the user asks for Phase 6, and only then, follow `project_context/phase6.md`. That brief is the implementation prompt. In short:

1. Read the Phase 6 section of `project_context/PROJECT_PLAN.md`, `docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md`, and `docs/phase_5/THRESHOLD_POLICY.md`.
2. Wrap `med_policy.decision.assess_draft` and `load_bundle`. Do not reimplement the cutoff or the aggregation.
3. Add the request normalizer (duplicate-address merging, limits, malformed input) before the transform. Map every failure to `unable_to_assess`, never allow.
4. Do not move `T_warn`, enable blocking, calibrate, or rerun `python -m med_policy evaluate-test`. `test_evaluation.json` is the one test result for `med-policy-v1`.
5. Do not treat as solved: the warning budget at confidence, first-contact mistakes, S01/S04 detection, AC07, and backend latency.

Keep public documents free of private planning context.
