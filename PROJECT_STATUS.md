# Project status

Last updated: 2026-09-26.

This file is the handoff for the next session. Standing rules are in [AGENTS.md](AGENTS.md).

## Completed phases

| Phase | State | What exists |
| --- | --- | --- |
| 1 — Product definition | Complete | Public requirements only. No implementation and no measured product metrics. S11 added to scenario list. |
| 2 — Data, labels, and splits | Complete | Fictional dataset `med-synth-v3`, generator `1.2.0`, seed `20260926`. 31 validation checks passed. |
| 3 — Behavioral and text features | Complete (v1 baseline on v2 data) | `med-features-v1`: shared transform, frozen TF-IDF, train/validation matrices. (v2 rebuild pending Phase 3). |
| 4 — Baselines and model comparison | Complete (v1 baseline on v2 data) | `med-model-v1`: always-allow, rules, logistic regression, one tree, ablations. No threshold. (v2 rebuild pending Phase 4). |
| 5 — Evaluation and threshold policy | Complete (v1 baseline on v2 data) | `med-policy-v1`: one warning cutoff on the risk score, blocking disabled, calibration not fit, one frozen test pass. (v2 rebuild pending Phase 5). |
| 6 — Backend and scoring API | Complete (v1 baseline on v2 data) | `med-api-v1`: FastAPI service over the frozen bundle, A7 normalizer, `unable_to_assess` failures, feedback file, AC05 measured (not met). |
| 7 through 10 | Not started | No UI, monitoring, or deployment. |

Phase 2 dataset revision `med-synth-v3` (generator `1.2.0`, seed `20260926`) replaces `med-synth-v2` to address artificial shortcuts and provide adequate sample sizes for reliable evaluation:
- Shared topics across relationships (cross-team communication, lookalike teammates sharing topics, S04 topic overlap).
- Balanced send scheduling eliminating fixed-minute bursts (same-recipient mail < 5 min is ~1.4% intended and ~0.6% unintended).
- Scenario S11 (mistaken first contact) added across all splits.
- S07 legitimate topic-change training quota increased to 36 drafts across diverse operational topics.
- Expanded sample sizes: 3,000 train drafts (300 misdirected), 4,000 product-like validation drafts (20 misdirected), 6,000 product-like test drafts (30 misdirected), and diagnostic subsets with at least 10 families per applicable scenario (240 validation diagnostic, 256 test diagnostic).
- Frozen test subsets: `test_product_like` (6,000 drafts) and `test_diagnostic` (256 drafts) of `med-synth-v3`.

## Active work

| Item | Owner |
| --- | --- |
| Active phase | Phase 3 (Feature re-engineering on v3) — not yet started |
| Owner | Unassigned |

The next session should proceed with Phase 3 on `med-synth-v3` as specified in Section C of `project_context/fixes_before_phase7.md`.

## Delivered artifacts

Phase 1:

- [docs/phase_1/PRODUCT_BRIEF.md](docs/phase_1/PRODUCT_BRIEF.md)
- [docs/phase_1/SCENARIOS.md](docs/phase_1/SCENARIOS.md) (includes S11)
- [docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md](docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md)
- [docs/phase_1/ACCEPTANCE_CRITERIA.md](docs/phase_1/ACCEPTANCE_CRITERIA.md)

Phase 2:

- [docs/phase_2/DATA_DICTIONARY.md](docs/phase_2/DATA_DICTIONARY.md)
- [docs/phase_2/LABELING_GUIDE.md](docs/phase_2/LABELING_GUIDE.md)
- [docs/phase_2/DATASET_SPECIFICATION.md](docs/phase_2/DATASET_SPECIFICATION.md)
- [docs/phase_2/DATA_QUALITY_AND_LEAKAGE.md](docs/phase_2/DATA_QUALITY_AND_LEAKAGE.md)
- Package `src/med_data/` (`generate`, `scoring_view`, `validate`, `build` / `validate` CLI)
- Tests in `tests/test_phase2.py`
- Published tables in `data/med-synth-v3/` (and preserved historical baseline in `data/med-synth-v2/`)

Published subset counts (`med-synth-v3`):

| Subset | Drafts | Misdirected | Legitimate | Frozen |
| --- | --- | --- | --- | --- |
| `train` | 3000 | 300 | 2700 | No |
| `validation_product_like` | 4000 | 20 | 3980 | No |
| `validation_diagnostic` | 240 | 80 | 160 | No |
| `test_product_like` | 6000 | 30 | 5970 | Yes |
| `test_diagnostic` | 256 | 88 | 168 | Yes |

Total records: 155,076 sent messages, 13,496 drafts, 17,598 draft recipients / labels, 350 contacts. Product-like misdirection is exactly 0.5%. Train enrichment is exactly 10%. Intended Bcc recipients: train 44, validation product-like 31, validation diagnostic 20, test product-like 42. Train still has unintended Bcc recipients from S08.

Frozen test subset checksums (`med-synth-v3` manifest SHA-256):
- `contacts.csv`: `371caa03e3551e7aac44de398d2196c11789130071fea42b9a51edc32c8e22f9`
- `messages.csv`: `b06cbce58f0c8f32bf4db9cae5612599ce0170b2deb1b14854d84c2e80bc02aa`
- `message_recipients.csv`: `3a6bdb85977800d29eea54eb45da6bd481c428cc07e1e26d793aa038ca4b3d14`
- `drafts.csv`: `d0e6cf02de8cbf7082a9a65f143c4da944445cfda43a6d4f43a576c130065ae6`
- `draft_recipients.csv`: `ec447bde364bc123ac80c38d861a759ea01da2dc3ce1b63de7448d518d8110cc`
- `labels.csv`: `e2b113320acbc027b3629ff55983efc99d11c13b12e8e0589edb3116ff918505`
- `reviewer_feedback.csv`: `666c4fb89ada6205122d4a128d665f58e4153e4de76ee23dbb1b4224baaf5a2a`
- `split_manifest.csv`: `6fc67cae6bc7fd39f5a4d28067f8e066b8f21345c9aae3593b23356f88b596ab`
- `invalid_fixtures.csv`: `547a187b11651af05190d33b96655f66d5b612d6d3b2c9d625164621ba5f480d`
- `quality_report.json`: `940f76c1e16cfed7e0ea7e3dead5c15bda111ee8a39f0b9f48bdb20802f96972`

Historical v2 baseline (preserved on disk):
- Published tables in `data/med-synth-v2/`
- `artifacts/med-features-v1/`
- `artifacts/med-model-v1/`
- `artifacts/med-policy-v1/`
- `artifacts/med-api-v1/`

## Verified results

Verified on 2026-09-26 from the repository root with the project virtualenv:

| Command | Result |
| --- | --- |
| `python -m med_data build --output data/med-synth-v3` | Wrote `med-synth-v3` (155,076 messages, 13,496 drafts) |
| `python -m med_data validate --data data/med-synth-v3` | 31 checks passed (Q01 through Q31) |
| `pytest tests/test_phase2.py tests/test_public_docs.py` | 13 passed in ~13m52s |

Phase 2 v3 dataset generation, validation, and test suites are completely verified. Downstream feature/model/policy/API test files (`tests/test_phase3.py`, `tests/test_phase4.py`, `tests/test_phase5.py`, `tests/test_phase6.py`) test against v1 artifacts on v2 data and will be rerun in Phases 3–6.

## Known gaps and handoff to Phase 3

- **Phase 3 Handoff:** Feature extraction (`med-features-v2`) must be re-run on `data/med-synth-v3` train split only. The A6 generator shortcut checks (evaluating single-feature AUCs on training data) will be executed during Phase 3. No features were built or inspected in Phase 2.
- **Timing diagnostic (Q31):** Verified that in the training split, same-recipient mail under 5 minutes earlier is ~1.40% on intended recipient rows (51/3640) and ~0.63% on unintended recipient rows (2/315), confirming the removal of deterministic timing bursts.
- **Scenario S11:** Mistaken first contacts are present in all splits and subsets. Autocomplete selections of uncontacted directory contacts are labeled unintended (`intended = false`).
- **Template phrasing:** Template language repeats across weeks. Unique reference tokens stop exact body copies across splits.
- **Prevalence assumption:** 0.5% product-like prevalence remains a simulation assumption for evaluation. Training enrichment is 10%.
- **Frozen test subsets:** `test_product_like` (6,000 drafts) and `test_diagnostic` (256 drafts) of `med-synth-v3` are frozen and must not be used for tuning or selection.
