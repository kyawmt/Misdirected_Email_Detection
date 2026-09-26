# Project status

Last updated: 2026-09-26.

This file is the handoff for the next session. Standing rules are in [AGENTS.md](AGENTS.md).

## Completed phases

| Phase | State | What exists |
| --- | --- | --- |
| 1 — Product definition | Complete | Public requirements only. No implementation and no measured product metrics. |
| 2 — Data, labels, and splits | Complete | Fictional dataset `med-synth-v2`, generator `1.1.0`, seed `20260926`. |
| 3 through 10 | Not started | No features, models, thresholds, API, UI, monitoring, or deployment. |

Phase 2 includes a follow-up correction on the same version line: manifest rows are checked against drafts, ordinary mail includes intended Bcc recipients, and published row counts are parsed CSV records. That correction changed generation rules, so the published dataset is v2 rather than a silent rewrite of v1.

## Active work

No implementation is in progress.

| Item | Owner |
| --- | --- |
| Active phase | None |
| Owner | Unassigned |

The next session should not start Phase 3 unless the user asks for it.

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
| `pytest` | 12 passed in 68.12s |
| `python -m med_data validate --data data/med-synth-v2` | 30 checks passed |

The 12 tests include the original data contract plus negative tests for a swapped manifest assignment, a mismatched manifest timestamp and family, and CSV records that contain quoted newlines.

No detection, calibration, threshold, or latency metric has been measured. Acceptance criteria AC01–AC09 remain unimplemented as product behavior. AC10's documentation boundary is in force for public files.

## Known gaps

- Template sentences repeat across weeks. Unique `Ref` tokens stop exact body copies across splits. They do not stop a model from memorizing topic phrasing.
- The product-like test has 10 misdirected emails. Recall on that set will be coarse. Use `test_diagnostic` to inspect scenarios, and do not quote its rate as the 0.5% prevalence result.
- Real-world prevalence is unknown. 0.5% is a simulation assumption. Reporting precision at the 10% training mix would overstate the operating point.
- Replies are one sentence and do not quote the parent. Threads are a message plus that reply.
- Department and directory dates are visible to a future scorer as directory facts. They are not intent labels.
- S10 invalid fixtures are described and excluded from training. Nothing scores them yet.
- No feature code, model, threshold policy, API, or UI exists.

## Next steps

When the user asks for Phase 3, and only then:

1. Read the Phase 3 section of `project_context/PROJECT_PLAN.md` and the Phase 2 leakage rules.
2. Build features from `scoring_view` history, strictly before each draft.
3. Fit any text vocabulary on training data only.
4. Leave `test_product_like` and `test_diagnostic` untouched.
5. Add a feature catalog, profile design, quality report, and tests. Do not train a model in that phase.
6. Update this file with the new artifacts and the commands you actually ran.

Do not select thresholds or cite paper metrics as results for this dataset. Keep public documents free of private planning context.
