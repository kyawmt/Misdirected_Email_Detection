# Project status

Last updated: 2026-09-27.

This file is the handoff for the next session. Standing rules are in [AGENTS.md](AGENTS.md).

## Completed phases

| Phase | State | What exists |
| --- | --- | --- |
| 1 — Product definition | Complete | Public requirements only. S11 added to the scenario list. The contract was not otherwise changed. |
| 2 — Data, labels, and splits | Complete | Fictional dataset `med-synth-v4`, generator `1.3.0`, seed `20260926`. 31 validation checks passed. |
| 3 — Behavioral and text features | Complete (v4) | `med-features-v2` on `med-synth-v4` train: shared transform, frozen TF-IDF, lossless train/validation matrices, A6 train-only shortcut checks in the quality report. |
| 4 — Baselines and model comparison | Complete (v4) | `med-model-v2`: always-allow, rules, logistic regression, one tree, ablations (incl. drop-content), C3 eligibility checks, S11 diagnostics. Selected `logistic_all_balanced`. No threshold. |
| 5 — Evaluation and threshold policy | Complete (v4) | `med-policy-v2`: one warning cutoff on the risk score, blocking disabled, calibration not fit, scoring-path parity proven on all 4,000 selection drafts, one frozen test pass. AC01 insufficient evidence (independence not established). |
| 6 — Backend and scoring API | Complete (v4) | Contract `med-api-v1` serving the v4 bundle and snapshot `med-synth-v4`. Emits `CONTENT_RELATIONSHIP_MISMATCH` on content-sensitive warnings. AC05 measured once: met. |
| 7 — Simulated draft-review UI | Complete (v4) | Streamlit client `src/med_ui/` of `med-api-v1`, package version 0.7.0 with a `ui` extra. Curated validation examples chosen by rule, stale-result hiding, feedback, what-if exploration on stored validation scores. Walkthrough generated from the live API. No API, model, policy, or artifact change. |
| 8 through 10 | Not started | No monitoring or deployment. |

Phase 2 dataset revision `med-synth-v4` (generator `1.3.0`, seed `20260926`) replaces `med-synth-v2`. An intermediate `med-synth-v3` (generator `1.2.0`, commit `6ff7aa6`) was reviewed and superseded before anything was built on it; its test subsets were never evaluated and `data/med-synth-v3` was removed from the working tree (it stays in git history). What v4 changes relative to v2:
- Each topic has one template whose wording overlaps a neighbouring topic, so text similarity is a partial signal.
- Half of the single-recipient S08 Cc and Bcc mistakes add an on-topic colleague who regularly receives the sender's project updates. Lookalike pairs share some topics.
- Routine sends are spread over working hours and scenario sends carry seeded jitter.
- Scenario S11 (mistaken first contact) is in every split and subset.
- S07 has 36 train drafts across several topics.
- 3,000 train drafts (300 misdirected), 4,000 product-like validation drafts (20 misdirected), 6,000 product-like test drafts (30 misdirected), and at least 10 families per scenario in both diagnostic subsets (240 validation diagnostic, 256 test diagnostic).
- Frozen test subsets: `test_product_like` and `test_diagnostic` of `med-synth-v4`.

The cross-phase revision (`project_context/fixes_before_phase7.md`, Sections A, B, C) is complete. Section A produced `med-synth-v4`. Section B (code hygiene) and Section C (rerun of Phases 3–6) were done in this session; see the verified results below.

## Active work

| Item | Owner |
| --- | --- |
| Active phase | Phase 8 — monitoring, reviewed feedback, and rollback notes, on branch `phase-8-monitoring` (created from `main` at `90d0fdf`, 2026-09-30). In progress; nothing below describes Phase 8 results until this row says otherwise. |
| Owner | Claude Code session started 2026-09-30 (Phase 8). Not committed. |

Sections B and C are committed as `d760de7`, and the fixes for the review of that commit (RB-01, RC-01 to RC-06 in `project_context/comments.md`) as `b8092e7`. Both are on `main` (with the handoff commit `2e62761`). Phase 7 work is on branch `phase-7-ui`, created from `main` at `2e62761` (which contains all of `v4-rerun-phases-3-6`), and was committed there as `04e2146`. The fixes for its review (P7-01 to P7-06 in `project_context/comments.md`) are the next commit on that branch, and `phase-7-ui` was merged into `main` by fast-forward on 2026-09-27. Nothing is pushed. A Phase 7 UI refinement (the action message below) is committed on branch `phase-7-ux` (created from `main` at `62b682d`) as `1c33892` ("Improve the review screen for senders") and merged into `main` by fast-forward on 2026-09-30. Nothing is pushed. The Phase 8 brief is `project_context/phase8.md`. The Phase 7 brief is `project_context/phase7.md`.

## Phase 7 — what was built

- **Package** `src/med_ui/`: `config.py` (all UI settings and the example rules; versions and paths from `med_api.version` / `med_policy.version`), `client.py` (HTTP only: `GET /ready`, `POST /assess`, `POST /feedback`; refuses any non-Phase-1 request field), `presentation.py` and `exploration.py` (pure display functions), `examples.py` (directory and curated examples), `walkthrough.py` (doc generator), `app.py` (Streamlit script), `cli.py` (`python -m med_ui` serve, `python -m med_ui walkthrough`). No `med_ui` module imports `med_policy.decision`, `med_models`, `med_features.transform`, or the API app/service (AST check plus a subprocess `sys.modules` check).
- **Screen:** readiness banner (disables assessment unless `/ready` reports this contract and snapshot and exactly the local policy file's model, feature, and policy versions and `T_warn`), compose form (directory filtered to contacts visible at the timestamp, typed addresses allowed), curated-example selector with an "About this example" panel (story, stipulated intent, desired outcome, recorded validation outcome, rule), result (API decision labeled simulated, email risk score, `T_warn`, per-recipient table and cards with the API's codes and texts, explanation, provenance), stale-result hiding on any edit, feedback buttons, collapsed threshold exploration on `validation_scores.csv`. `?example=<key>&assess=1` deep links load and assess an example.
- **Curated examples** (all `validation_product_like`, chosen by rule from the stored validation decisions): routine S05 median allowed (`d003390`); S02 warned, fewest recipients then highest score (`d003027`); S03/S06 allowed, highest score (`d003216`); S01 allowed, highest (`d003002`); S04 allowed, highest (`d003049`); S11 allowed, highest (`d003074`); S07 allowed, highest (`d003251`); S09 cold start median allowed (`d003272`). Failure demos derive from the routine example by rule. Validation ids come from the split manifest first; `drafts.csv`, `draft_recipients.csv`, and `labels.csv` are streamed record by record and only validation records are kept, so no frozen record (and no `is_walkthrough` draft) enters memory as a table. The CSV parser still reads past frozen records to find record boundaries and drops them at once. A frozen-subset draft id raises `FrozenSubsetError`.
- **Docs:** `docs/phase_7/UI_GUIDE.md`, `docs/phase_7/WALKTHROUGH.md` (generated by `python -m med_ui walkthrough` against the running API; a test regenerates it through the FastAPI test client and requires an exact match), screenshots for steps 1, 2, 4 in `docs/phase_7/screenshots/` (headless Chrome over the DevTools protocol). README points at them.
- **Tests:** `tests/test_phase7.py`, 23 tests (after the review fixes), including four Streamlit `AppTest` runs of the real script (no browser). `tests/conftest.py` now pins pandas to Python string storage (see the pyarrow note below).

### Phase 7 UI refinement: action message (branch `phase-7-ux`, 2026-09-27)

- **What:** a plain-language action message directly under "Assess draft", built by `presentation.action_message` from the result view (that is, from the API response only, never from the example story). Warn: "Pause and review before sending." with every flagged recipient in API order, its field (To, Cc, Bcc from the API's roles), a link to its recipient card, and the API's codes and text; plus "A warning asks you to check these addresses. It is not proof of a mistake." Allow: "No warning from this policy." with a reminder that it is not a check of every recipient; recipients with API evidence limitations are listed under "Less evidence for:". Unable to assess (invalid input, unavailable, unexpected response, unreachable service): "Assessment unavailable. Check recipients manually before sending." with the category and the service message, no decision, no score. Stale: the earlier message is replaced by "The draft changed after the last assessment. Assess the edited draft again; the earlier result no longer applies."
- **End-user layout:** the main area is now the sender's view: the message (From, To, Cc, Bcc, Subject, Body) on the left and a "Review before sending" panel on the right with the **Assess draft** button and the action message, both visible on a 1440×900 window without scrolling. Reviewer details (scores, table, recipient cards with feedback, explanation, provenance, exploration, service status) sit below under "Assessment details". The sidebar keeps the curated examples and the story, and now holds the simulated send time under "Simulation settings".
- The three "Other To/Cc/Bcc addresses" text fields were removed. Each recipient box accepts a typed address ("Add: …", sent as written, so unknown and malformed addresses still reach the API's `unavailable` / `invalid_input`). The boxes set `select_all=False` and substring filtering: with Streamlit's default "select all", one Enter after typing added a whole fuzzy-filtered list (22 recipients) and the API rejected the draft. The action message shows the API's plain-language text per code; code names stay in the recipient cards. Streamlit's toolbar runs in minimal mode (no Deploy button).
- When the service is ready, the readiness banner no longer sits above the compose form: its status and versions moved to a collapsed "Service status and versions" section at the bottom. A not-ready service still shows a red banner at the top and disables assessment. New AppTest `test_app_keeps_ready_status_out_of_the_way`.
- Recipient cards now have an anchored heading with the address as code text (Streamlit otherwise turned it into a `mailto:` link). The result section no longer repeats the unable/stale text.
- No model, policy, `T_warn`, API contract, data, artifact, or walkthrough change (the walkthrough generator's output is unchanged; its reproducibility test passes). Step 1, 2, and 4 screenshots recaptured; `docs/phase_7/UI_GUIDE.md` has an "Action message" section.
- Tests: `tests/test_phase7.py` now has 34 tests (including `test_app_shows_the_review_panel_beside_the_message`): 6 new presentation tests (warn fields, codes, and API order even when a later recipient scores lower; allow with and without limitations; invalid_input, unavailable, unexpected, and transport; stale and empty) and 3 new AppTests (warn message sits above "Result" and links each flagged recipient; allow with and without limitations; invalid_input and unavailable). A mutation that sorted flagged recipients by score failed the order test.

### Walkthrough, measured on 2026-09-27 (live API, v4 bundle)

| Step | Example | Desired | Measured |
| --- | --- | --- | --- |
| 1 | S05 routine | allow | allow, 8.216e-12 |
| 2a | S02 added vendor | warn on the added recipient | warn, 0.9997260; `ren@logistics.example` flagged: EXTERNAL_RECIPIENT, UNUSUAL_RECIPIENT_COMBINATION, CONTENT_RELATIONSHIP_MISMATCH |
| 2b | same, flagged recipient removed | new request; may still warn | allow, 0.0023813 |
| 3a | S03 first contact | allow, limitation shown | allow, 0.9973707 (2.31e-03 below `T_warn`), LIMITED_RELATIONSHIP_HISTORY |
| 3b / 3c | S07 topic change / S09 cold start | allow / allow with limitation | allow 0.5193083 / allow 7.126e-35 with LIMITED_RELATIONSHIP_HISTORY |
| 4a–c | S01 / S04 / S11 | warn | allow 0.9818357 / 0.9943188 / 0.9814677 — known misses (0 warned in every validation and test subset) |
| 5 | exploration | simulation, distinct from policy | at `T_warn` 8/20 mistakes, 0/3,980 false; at 0.9973707 8/20 and 1 false; at 0.9949507 9/20 and 1 false; at 0.9943188 10/20 and 1 false |
| 6a / 6b | unknown address / malformed address | non-assessed, no score | `unavailable` / `invalid_input`, no decision or score |
| 7 | feedback on 2a | not a label until reviewed | HTTP 200 `recorded`; same draft reassessed: warn, same score |

### pyarrow and runtime

The `ui` extra installs Streamlit, which requires pyarrow. With pyarrow importable, pandas 3.0.6 stores strings in Arrow by default. Results are unchanged (full `pytest` passed under Arrow strings: 121 passed in 1018.53 s; `med_data validate` 31 checks passed in 159.8 s), but the pipeline is about three times slower (`validate` 49.1 s with pyarrow blocked). `tests/conftest.py` sets `mode.string_storage = "python"`, restoring the test runtime. The CLIs are not pinned; the UI guide suggests a separate virtual environment for the UI. Phase 9 packaging should decide whether to pin the storage in the packages or split environments.

## Section B (code hygiene) — what changed

- **B1.** Each package has one version module with its versions and default paths: `med_data.version` (dataset), `med_features.version` (feature spec and the dataset it is fit on), `med_models.version`, `med_policy.version`, `med_api.version` (snapshot id and bundle paths follow the policy package). Every CLI and the API read from them. No `med-synth-v2` or `-v1` default remains in `src/`.
- **B2.** Tests assert rules, not v2 numbers: quotas come from `med_data.version`, artifact row counts from `fit_metadata.json`, example drafts from `med_api.fixtures.example_draft_ids` (lowest warned mistake, median allowed routine draft, a legitimate first contact), and a late-listed contact is found by query. Leakage and frozen-subset tests stay.
- **B3.** Feature CSVs are written with 17 significant digits and read with round-trip parsing (`med_features.build.write_features` / `read_features`). The published-artifact test now requires bit-identical rows. The v2 drift came from the default pandas parser, not the writer. `med-policy-v2` selection proves both scoring paths agree on the whole selection subset before writing the policy (see results). Tests: CSV round trip, cutoff-adjacent parity (bound 1e-12, identical decisions), full-subset record.
- **B4.** `_content_cosine` slices the history matrix once per recipient. On 304 sampled v2 drafts the frames are bit-identical to the old per-row code; in-process transform p95 went from 317.6 ms to 26.3 ms (v2 data), and is 54.8 ms on v4.
- **B5.** `docs/phase_4/MODEL_ARTIFACT.md` states the unobserved-recency fill from the stored model metadata (v4: 0.234375 days, 337.5 minutes).
- **B6.** API latency is written to `artifacts/med-api-latency/<policy version>/latency.json` and the command refuses to overwrite. `artifacts/med-api-v1/latency.json` is the untouched v2 record.
- **B7.** The latency workload is every `validation_product_like` draft (4,000 on v4) in a permutation fixed with seed `20260926`, after 20 warm-ups; recipient-count, month, and sender-history mix are recorded.

Section B gate (before C1, against the v2 bundle): `pytest` 100 passed, 0 failed, 510.44 s.

## Delivered artifacts

Phase 1:

- [docs/phase_1/PRODUCT_BRIEF.md](docs/phase_1/PRODUCT_BRIEF.md)
- [docs/phase_1/SCENARIOS.md](docs/phase_1/SCENARIOS.md) (includes S11)
- [docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md](docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md)
- [docs/phase_1/ACCEPTANCE_CRITERIA.md](docs/phase_1/ACCEPTANCE_CRITERIA.md)

Phase 2:

- [docs/phase_2/](docs/phase_2/) (data dictionary, labeling guide, dataset specification, quality and leakage checklist)
- Package `src/med_data/`, tests in `tests/test_phase2.py`
- Published tables in `data/med-synth-v4/` (and the preserved baseline in `data/med-synth-v2/`)

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

Phases 3–6 (v4):

- `artifacts/med-features-v2/`, [docs/phase_3/](docs/phase_3/) (quality report regenerated with the A6 checks)
- `artifacts/med-model-v2/`, [docs/phase_4/](docs/phase_4/)
- `artifacts/med-policy-v2/` (`policy.json`, `validation_scores.csv`, `validation_evaluation.json`, `test_evaluation.json`), [docs/phase_5/](docs/phase_5/)
- `artifacts/med-api-latency/med-policy-v2/latency.json`, [docs/phase_6/](docs/phase_6/)

Historical v2 baseline (preserved on disk, verified unchanged by SHA-256 at the end of this session, 28 files): `data/med-synth-v2/`, `artifacts/med-features-v1/`, `artifacts/med-model-v1/`, `artifacts/med-policy-v1/` (including `test_evaluation.json`), `artifacts/med-api-v1/latency.json`. Current code cannot load the v1 bundle (version checks refuse it); it is a record, not a served bundle.

## Verified results

Verified on 2026-09-26 and 2026-09-27 from the repository root with the project virtualenv (Apple M1 Pro, 10 CPUs, macOS, Python 3.11.14, scikit-learn 1.9.1, NumPy 2.4.6), in this order:

| Command | Result |
| --- | --- |
| `pytest` (Section B gate, v2 bundle) | 100 passed, 0 failed in 510.44 s |
| `python -m med_features build --quality-markdown docs/phase_3/FEATURE_QUALITY_REPORT.md` | Wrote `med-features-v2` on `med-synth-v4` in 3m30s. Rows: train 3,955, validation_product_like 4,970, validation_diagnostic 582. A6: no feature flagged; content cosine AUC 0.068 (separation 0.932) |
| `python -m med_models run` | Wrote `med-model-v2` in 4m49s. Selected `logistic_all_balanced` (C = 1000, top of grid) |
| `python -m med_policy select` | Wrote `med-policy-v2` in 2m32s: `T_warn = 0.9996767050340489`, validation recall 8/20, 0 false interventions on 3,980. Scoring-path parity: 4,000/4,000 identical decisions, max difference 3.9e-15 (an earlier attempt failed on a code error before writing anything) |
| `python -m med_policy evaluate-test` (run once) | `test_product_like`: warned 9/30 misdirected, 0/5,970 legitimate. `test_diagnostic`: warned 37/88, 0/168. No scoring failures |
| `python -m med_api latency` (run once) | 4,000 calls: client p50 26.84 ms, p95 57.04 ms, p99 74.43 ms; AC05 met; 4,000/4,000 decisions match `validation_scores.csv` |
| `python -m med_api report`, `python -m med_policy report` | Regenerated `docs/phase_6` and `docs/phase_5` from stored results |
| `python -m med_data validate --data data/med-synth-v4` | 31 checks passed (Q01–Q31) in 54.6 s |
| `pytest` (final, v4 bundle) | 100 passed, 0 failed in 525.10 s (8m45s) |
| `pytest` (2026-09-27, after the review fixes RB-01, RC-01 to RC-06) | 104 passed, 0 failed in 522.22 s (8m42s) |
| `python -m med_data validate` (2026-09-27) | 31 checks passed |
| `python -m med_policy report`, `python -m med_api report`, Phase 4 docs from stored results (2026-09-27) | Regenerated; only `artifacts/med-model-v2/experiments.json` changed (eligibility block recomputed, outcomes unchanged). v2 baseline: 28/28 files unchanged |
| `pytest` (2026-09-27, Phase 7, with pyarrow from the `ui` extra, before the conftest pin) | 121 passed, 0 failed in 1018.53 s |
| `python -m med_data validate --data data/med-synth-v4` (2026-09-27, Phase 7, pyarrow installed) | 31 checks passed, 159.8 s (49.1 s with pyarrow blocked) |
| `python -m med_api serve` + `python -m med_ui walkthrough` (2026-09-27) | Wrote `docs/phase_7/WALKTHROUGH.md` from the live API (`/ready`: med-api-v1, med-model-v2, med-features-v2, med-policy-v2, med-synth-v4, `T_warn` 0.9996767050340489, blocking false) |
| `python -m med_ui` against the live API (2026-09-27) | All 8 curated examples loaded and assessed in headless Chrome (1 warn, 7 allow, matching the walkthrough); edit-to-stale and reassess checked in the browser; screenshots for steps 1, 2, 4 written |
| `pytest` (2026-09-27, Phase 7 final, conftest pin) | 121 passed, 0 failed in 479.16 s (7m59s) |
| `pytest` (2026-09-27, after the Phase 7 review fixes P7-01 to P7-06) | 127 passed, 0 failed in 519.66 s (8m39s) |
| `python -m med_data validate --data data/med-synth-v4` (2026-09-27, after the review fixes, pyarrow installed) | 31 checks passed, 164.4 s |
| `python -m med_api serve` + `python -m med_ui walkthrough` (2026-09-27, after the review fixes) | Regenerated `docs/phase_7/WALKTHROUGH.md`; only the two header sentences changed, every measured value identical |
| `pytest tests/test_phase7.py tests/test_public_docs.py` (2026-09-27, action message) | 33 passed in 12.10 s |
| `python -m med_api serve` + `python -m med_ui` (2026-09-27, action message) | Warn, allow, and known-miss screens checked in headless Chrome; the recipient link scrolls to its card (browser check); screenshots for steps 1, 2, 4 recaptured |
| `pytest` (2026-09-27, action message) | 136 passed, 0 failed in 525.90 s (8m46s) |
| `pytest` (2026-09-27, readiness moved to the bottom when ready) | 137 passed, 0 failed in 535.40 s (8m55s) |
| `python -m med_api serve` + `python -m med_ui` (2026-09-27, end-user layout) | Warn and allow checked at 1440×900 in headless Chrome (Assess button and message visible on landing); an unknown address typed into Bcc in the browser gave `unavailable` with the directory sentence; screenshots for steps 1, 2, 4 recaptured |
| `pytest` (2026-09-27, end-user layout) | 138 passed, 0 failed in 539.94 s (9m00s) |
| `pytest tests/test_phase7.py tests/test_public_docs.py` (2026-09-30, after removing dead code: unused `re` import, `FORM_KEYS`, and the unused `known` argument) | 35 passed in 14.27 s |

### v4 results (current)

| Item | Value |
| --- | --- |
| C3 eligibility | Audit: no content feature flagged (content cosine separation 0.932). Fold stability (all-features over behavior-only, min per-fold margin): logistic unweighted +0.229, balanced +0.234, tree +0.191. Not content alone (over content-only): +0.040, +0.117, +0.015. All families eligible. |
| Selected model | `logistic_all_balanced`, product-like validation email AP 0.831 [0.676, 0.954] (20 positives); best behavior-only 0.494 |
| S11 threshold-free (validation_diagnostic) | S11 vs legitimate first contacts AUC 0.880 (10 vs 20 rows) |
| Validation operating point | 8/20 warned (recall 0.40, exact [0.191, 0.639]); 0/3,980 false; exact upper 0.93 per 1,000 (not independent: selection subset) |
| Test operating point | 9/30 warned (recall 0.30, exact [0.147, 0.494]); 0/5,970 false; exact upper 0.62 per 1,000 |
| Scenario recall at the cutoff | S01, S04, S11 0 warned in every validation and test subset; test product-like S02 2/6, S08 5/8, S09 2/2 |
| AC01 | Insufficient evidence. 0/5,970 is a descriptive pass on this corpus; the exact bound 0.62 per 1,000 assumes independent emails, and 5,682 of 6,000 test drafts come from one sender (review item RC-01) |
| AC02 | Met for S09; partly met for S02, S08; not met for S01, S04, S11 |
| AC03 / AC04 | Met / met (blocking disabled, 0 blocks) |
| AC05 | Met: API client p95 57.04 ms < 300 ms, this machine only |
| AC07 | Insufficient evidence: 0 wrong interventions on S03/S05/S06/S07 (desired allows); every S11 mistaken first contact was missed (a detection miss, under AC02); legitimate first contacts score up to 0.99737 against `T_warn` 0.99968 |

### v2 historical baseline

| Item | Value |
| --- | --- |
| Bundle | `med-synth-v2`, `med-features-v1`, `med-model-v1` (`logistic_behavior_only_unweighted`, C = 100), `med-policy-v1` (`T_warn` 0.13455666515724893) |
| Content cosine train AUC | 0.991; behavior-only selection forced |
| Legitimate train rows under five minutes | 66.5% (misdirected 0%) |
| Validation operating point | 4/5 warned; 0/995 false; exact upper 3.70 per 1,000 |
| Test operating point | 5/10 warned; 0/1,990 false; exact upper 1.85 per 1,000 |
| S01 / S04 | S01 0 warned everywhere; S04 1/1 on validation product-like (the cutoff draft), 0 elsewhere |
| AC01–AC05 | Insufficient evidence; met only for S02, S08; met; met; not met (API p95 345.84 ms) |

## Known gaps and handoff

- **Phase 7 UI** shows the API's result and adds nothing: no reason codes, no scoring. It makes the S01, S04, and S11 misses visible; it does not reduce them. What Phase 8 should monitor: per-bundle assessment volume, `unable_to_assess` counts by category and message (unknown addresses in particular, since typos are `unavailable`), warning rate against the validation rate (8 of 4,000), email risk scores near `T_warn` (the legitimate first-contact margin is 2.3e-3), `LIMITED_RELATIONSHIP_HISTORY` and `LIMITED_TEXT` rates, API latency, and feedback volume and label mix (feedback on warned drafts only is biased; sampled allowed drafts need review too). Feedback lands in `var/feedback.jsonl` (gitignored); it is not a label until reviewed.
- **S01, S04, S11 are still missed.** At the zero-false-warning cutoff the policy warns only on added recipients (S02, S08) and cold senders (S09). Legitimate first contacts (S03, S06) score just below `T_warn`, so the cutoff sits above every lookalike, familiar-recipient topic mistake, and mistaken first contact. Any lower cutoff produces validation false warnings.
- **Content is a strong signal.** Content cosine separation 0.932 is inside the 0.05–0.95 audit bounds but not far inside. S02 and S04 are off-topic by scenario definition. The C3 checks passed by clear margins for the logistic families; the tree's content-only margin was thin (+0.015) and it was not selected.
- **C = 1000 is the top of the extended grid**; coefficients are not separate effects.
- **AC01 is insufficient evidence.** 0 of 5,970 false warnings is a descriptive pass on this corpus. The exact bound (0.62 per 1,000) assumes independent emails; 95% of product-like drafts come from one sender, and a sender-clustered interval has no bound for a zero count. A confidence-supported claim needs an independence argument or a more independent evaluation, which would need a new frozen dataset version. The margin between `T_warn` and the highest legitimate validation score is 2.3e-3 (0.99968 against 0.99737).
- **Unknown addresses** in a well-formed request stay `unavailable` (Phase 1 contract). Changing that is a contract decision.
- **`CONTENT_RELATIONSHIP_MISMATCH`** is emitted on a flagged recipient when its observed content cosine is below the train mean (0.414, from the feature quality report) and raising only that value to the mean drops its risk below `T_warn`. On validation every warning meets that test. The check was added after the latency measurement and runs only for flagged recipients; the latency record was not remeasured.
- **Five-minute timing:** 0.0% of legitimate and 1.9% of misdirected train rows by the pair-recency feature; Q31 (mail to the recipient from any sender) reports 1.37% and 1.90%.
- **Prevalence** 0.5% is a simulation assumption; train is enriched to 10%.
- **Published datasets are write-once.** `python -m med_data build` refuses a directory that already holds a dataset; reproduce into a new directory.
- **Frozen test subsets** of `med-synth-v4` have now been evaluated once for `med-policy-v2`. Do not rerun `evaluate-test` or move the cutoff. A new policy needs a new version and a new frozen dataset version.
