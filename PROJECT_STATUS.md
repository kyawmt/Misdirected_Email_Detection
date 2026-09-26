# Project status

Last updated: 2026-09-26.

This file is the handoff for the next session. Standing rules are in [AGENTS.md](AGENTS.md).

## Completed phases

| Phase | State | What exists |
| --- | --- | --- |
| 1 — Product definition | Complete | Public requirements only. No implementation and no measured product metrics. S11 added to scenario list. |
| 2 — Data, labels, and splits | Complete | Fictional dataset `med-synth-v4`, generator `1.3.0`, seed `20260926`. 31 validation checks passed. |
| 3 — Behavioral and text features | Complete (v1 baseline on v2 data) | `med-features-v1`: shared transform, frozen TF-IDF, train/validation matrices. (v2 rebuild pending Phase 3). |
| 4 — Baselines and model comparison | Complete (v1 baseline on v2 data) | `med-model-v1`: always-allow, rules, logistic regression, one tree, ablations. No threshold. (v2 rebuild pending Phase 4). |
| 5 — Evaluation and threshold policy | Complete (v1 baseline on v2 data) | `med-policy-v1`: one warning cutoff on the risk score, blocking disabled, calibration not fit, one frozen test pass. (v2 rebuild pending Phase 5). |
| 6 — Backend and scoring API | Complete (v1 baseline on v2 data) | `med-api-v1`: FastAPI service over the frozen bundle, A7 normalizer, `unable_to_assess` failures, feedback file, AC05 measured (not met). |
| 7 through 10 | Not started | No UI, monitoring, or deployment. |

Phase 2 dataset revision `med-synth-v4` (generator `1.3.0`, seed `20260926`) replaces `med-synth-v2`. An intermediate `med-synth-v3` (generator `1.2.0`, commit `6ff7aa6`) was reviewed and superseded before anything was built on it; its test subsets were never evaluated and `data/med-synth-v3` was removed from the working tree (it stays in git history). What v4 changes relative to v2:
- Each topic has one template whose wording overlaps a neighbouring topic, so text similarity is a partial signal.
- Half of the single-recipient S08 Cc and Bcc mistakes add an on-topic colleague who regularly receives the sender's project updates. Lookalike pairs share some topics.
- Routine sends are spread over working hours and scenario sends carry seeded jitter.
- Scenario S11 (mistaken first contact) is in every split and subset.
- S07 has 36 train drafts across several topics.
- 3,000 train drafts (300 misdirected), 4,000 product-like validation drafts (20 misdirected), 6,000 product-like test drafts (30 misdirected), and at least 10 families per scenario in both diagnostic subsets (240 validation diagnostic, 256 test diagnostic).
- Frozen test subsets: `test_product_like` and `test_diagnostic` of `med-synth-v4`.

Train-only shortcut audit on v4 (Phase 3 transform, computed in a scratch directory; no artifact written): content cosine alone has AUC 0.932 for misdirected recipient rows (v2: 0.991; v3: 0.98). Every other feature is between 0.31 and 0.69. Same-recipient mail in the five minutes before a draft: 1.37% of intended and 1.90% of unintended train rows (v2: 66.5% and 0%). First contacts in train: 40 legitimate and 30 misdirected (v2: 16 and 0). S02 and S04 remain low on content by their scenario definitions; on-topic S08 mistakes reach cosine 0.605 and S11 has no pair text.

## Active work

| Item | Owner |
| --- | --- |
| Active phase | None. Next: Section B of `project_context/fixes_before_phase7.md` |
| Owner | Unassigned |

The next session should continue `project_context/fixes_before_phase7.md` at **Section B** (code hygiene), then Section C. Section A is done.

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
- Published tables in `data/med-synth-v4/` (and preserved historical baseline in `data/med-synth-v2/`)

Published subset counts (`med-synth-v4`):

| Subset | Drafts | Misdirected | Legitimate | Frozen |
| --- | --- | --- | --- | --- |
| `train` | 3000 | 300 | 2700 | No |
| `validation_product_like` | 4000 | 20 | 3980 | No |
| `validation_diagnostic` | 240 | 80 | 160 | No |
| `test_product_like` | 6000 | 30 | 5970 | Yes |
| `test_diagnostic` | 256 | 88 | 168 | Yes |

Total records: 155,076 sent messages, 13,496 drafts, 17,598 recipient labels, 350 contacts. Product-like misdirection is exactly 0.5%. Train enrichment is exactly 10%. Intended Bcc recipients: train 44, validation_product_like 31, validation_diagnostic 20, test_product_like 42. Train still has unintended Bcc recipients from S08.

`med-synth-v4` manifest SHA-256:
- `contacts.csv`: `a4770802579ded45d5852dc6f3d2b0fa0a50e8d8a0432ef197cfb096c186b480`
- `messages.csv`: `3fd61c7afb8d1ffeaae523a72ae850c187837a5a83bb2cbc2c33007450bb2492`
- `message_recipients.csv`: `3a6bdb85977800d29eea54eb45da6bd481c428cc07e1e26d793aa038ca4b3d14`
- `drafts.csv`: `0ac162ef401649400e26e853da4e3c84b79ed4c6c6af5fcba98d0f08e26400e0`
- `draft_recipients.csv`: `8fa99a3dff8dceac765f3cecc8c42b58da1f005aebc807903e79959309ccac0f`
- `labels.csv`: `96a991dd6d4503ac8a0880fa6a87fb0c9ca23b1a3747e9f7f311392240e49021`
- `reviewer_feedback.csv`: `07db14105a5a9027de302b0ed6168379011439d46c1eabdf60eaa799393c2a64`
- `split_manifest.csv`: `831b3553e99e34c3bc5ced094eb44934c18db7ab70b171db8dac32086e3fc184`
- `invalid_fixtures.csv`: `8cb601a0e07ce51971bad4e1da750115be70042ecd927f0e9a25c29d323fc13d`
- `quality_report.json`: `85695561792d6ac6fad6a08836ebad7f22aef7364f34d4b7924f2b4cee7d8f6a`

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
| `python -m med_data build --output data/med-synth-v4` | Wrote `med-synth-v4` (155,076 messages, 13,496 drafts) in 67 s |
| `python -m med_data validate --data data/med-synth-v4` | 31 checks passed (Q01 through Q31) in 54 s |
| `pytest` | 94 passed, 1 failed in 519.34s (8m39s). The failure is `tests/test_phase3.py::test_published_artifact_matches_training_fit`, expected until B2 and C1: it compares the v2-fitted transformer with a fit on the generated v4 dataset |
| Train-only feature audit on `data/med-synth-v4` (scratch script, Phase 3 transform) | Content-cosine AUC 0.932; all other features 0.31–0.69 |

The v4 correction also sped up validation without changing its output: Q31 uses per-recipient sorted times (68.3 s to 0.2 s), `scoring_view` builds each contact payload once and groups only visible messages (identical output), and the Phase 2 walkthrough test uses one vectorized lookup (198 s to under 1 s). Downstream Phase 3–6 tests still read the published v2 artifacts and will be reworked in Section B.

## Known gaps and handoff

- **Next:** Section B of `project_context/fixes_before_phase7.md` (version config, tests that assume v2, lossless feature CSVs, vectorized centroid, latency path and workload), then Section C on `med-synth-v4`.
- **Content is still strong.** Content cosine alone has train AUC 0.932. S02 and S04 are off-topic by their scenario definitions, so content catches them. On-topic S08 mistakes, S01 lookalikes, and S11 first contacts are not separable by text. C3's eligibility checks decide whether content models may be selected.
- **Timing (Q31):** 1.37% of intended and 1.90% of unintended train rows have same-recipient mail in the five minutes before the draft.
- **Scenario S11:** mistaken first contacts are in every split and subset, labeled unintended. Train has 40 legitimate and 30 misdirected first-contact rows.
- **Template phrasing:** template language repeats across weeks. Unique reference tokens stop exact body copies across splits.
- **Prevalence assumption:** 0.5% product-like prevalence is a simulation assumption. Training enrichment is 10%.
- **Frozen test subsets:** `test_product_like` (6,000 drafts) and `test_diagnostic` (256 drafts) of `med-synth-v4` are frozen. Structural checks may touch them; no performance inspection until a v4 policy exists.
