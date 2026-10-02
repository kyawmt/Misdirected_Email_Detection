# Project status

Last updated: 2026-10-01 (record timestamps are UTC).

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
| 8 — Monitoring, reviewed feedback, and rollback notes | Complete (v4) | `src/med_monitor/` (`med-monitor-v1`), package version 0.8.0. Train-only input reference, a deterministic eight-window replay through the API, three separately reported findings (input drift, decision-rate change, confirmed performance change) each with a minimum sample size, a labeled simulated review workflow, bundle-refusal evidence, and five generated documents in `docs/phase_8/`. No API, model, policy, `T_warn`, dataset, or contract change. Detection did not improve and is not claimed to. |
| 9 — Testing and deployment | Complete (v4); review items P9-01 to P9-03 addressed | `src/med_deploy/` (`med-deploy-v1`), package version 0.9.0. Compact scenario regression over 20 recorded validation fixtures (three known misses kept), pinned dependencies (`constraints.txt`, Python 3.11.14), two local images (API without pyarrow, review screen separately), compose file bound to `127.0.0.1`, a CI workflow, a warm-latency record, a rehearsed rollback, and four generated documents in `docs/phase_9/`. No model, feature, policy, `T_warn`, dataset, or API contract change. |
| 10 — Documentation | Complete (v4); documentation only | `src/med_docs/` (`med-docs-v1`), package version 0.10.0. A rewritten README; `docs/ARCHITECTURE.md`, `docs/RESULTS.md` (generated), `docs/MODEL_CARD.md`, `docs/USAGE_GUIDE.md`, `docs/DEMO_WALKTHROUGH.md`, `docs/LIMITATIONS_AND_FUTURE_WORK.md`, and a documentation index `docs/README.md`. Numbers come from stored records through a stdlib-only generator that reads only allow-listed aggregate fields of the frozen test record. Final status of AC01 to AC10 recorded. No model, feature, policy, `T_warn`, dataset, API contract, UI, monitoring, deployment, artifact, or record change. Detection did not improve and is not claimed to. |
| Whole-project review fixes | WP-01 to WP-09 fixed, committed on `whole-project-fixes`, merged into `main` (2026-10-02), not pushed | Runtime policy guards, a fail-closed API boundary, a narrower startup read, AC02 as insufficient evidence, corrected build commands and project records, a faster full `pytest`. No model, feature, `T_warn`, dataset, API contract, or stored record changed. See the section below. |

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
| Active phase | None. All ten phases are complete and merged into `main`. `main` is pushed: `origin/main` is `ce46634` ("Address Phase 10 review (P10-01 to P10-04)"), and GitHub Actions run [36852075499](https://github.com/kyawmt/Misdirected_Email_Detection/actions/runs/36852075499) on that commit is green (push event, `ubuntu-24.04`, started 2026-10-01 10:54:57 UTC; every step of the `checks` job succeeded; confirmed through the public GitHub API on 2026-10-01). The whole-project review (WP-01 to WP-09 in `project_context/comments.md`; brief `project_context/all_phases.md`) was fixed on branch `whole-project-fixes` (created from `main` at `ce46634`), committed as "Fix the whole-project review (WP-01 to WP-09)", and merged into `main` by fast-forward on 2026-10-02. That commit is **not pushed**, so `origin/main` is still `ce46634` and the green run above does not cover the fixes; a push needs a new CI run. Open after it: rebuild the Phase 9 images and run the smoke check against them (see the section below), and push. The Phase briefs are `project_context/phase2.md` to `phase10.md`. |
| Owner | Unassigned |

Branch history (dated; every branch below is merged into `main` by fast-forward, and `main` is pushed): Sections B and C are `d760de7` and the review fixes `b8092e7`, with the handoff commit `2e62761`. Phase 7 was built on `phase-7-ui` (`04e2146`, then its review fixes `62b682d`, merged 2026-09-27) and refined on `phase-7-ux` (`1c33892`, merged 2026-09-30). Phase 8 was built on `phase-8-monitoring` (`1dbb9ce`, then `931fb5a`, merged 2026-09-30). Phase 9 was built on `phase-9-deploy` (`89e593a`, with the status commit `980f2d1`, merged 2026-10-01). Phase 10 was built on `phase-10-docs` (`412ad25`), followed on `main` by the CI fix `c2204c1` and the status commit `50b82bd` (pushed; CI run 36811479847, green), then by `phase-10-review-fixes` (`ce46634`, merged 2026-10-01 and pushed; CI run 36852075499, green). The whole-project fixes are on `whole-project-fixes`, merged into `main` by fast-forward on 2026-10-02 and not pushed. The older statements elsewhere in this file that something "is not pushed" or "uncommitted" were true when written and are superseded by this paragraph. Leftover local topic branches, all fully merged into `main` and safe to delete: `check_work_done`, `ci-linux-fix`, `phase-10-docs`, `whole-project-fixes`, `phase-10-review-fixes`, `phase-7-ui`, `phase-7-ux`, `phase-8-monitoring`, `phase-9-deploy`, `v4-rerun-phases-3-6`. `origin/phase-8-monitoring` is an older commit.

## Whole-project review fixes (WP-01 to WP-09, branch `whole-project-fixes`, 2026-10-01 to 2026-10-02; merged into `main`, not pushed)

Source: the "Whole-project review" section of `project_context/comments.md` (brief `project_context/all_phases.md`). Fix pass only: no refit, no new `T_warn`, no change to the model, features, policy selection, blocking, the Phase 1 documents, the API request or response contract, or any stored record or artifact. `policy.json` is byte-identical (SHA-256 `be39929a3c92…`).

| ID | What changed | Test |
| --- | --- | --- |
| WP-01 | `med_policy.decision.load_bundle` refuses a `T_warn` outside 0 to 1 (inclusive; equality warns, so 1.0 stays valid) and a `policy.json` whose SHA-256 is not `POLICY_SHA256` in `med_policy.version` (hashed from the bytes it parsed; checked after the structural checks, so every earlier message is unchanged). No new artifact file. A refusal leaves `/ready` 503 and `/assess` `unable_to_assess` / `unavailable`. | `tests/test_phase5.py` (loader) and `tests/test_phase6.py` (real API with disposable policy copies: cutoff 2.0, -0.5, an in-range edited cutoff, one appended byte, and the unchanged control) |
| WP-02 | `AssessmentService.assess` turns any unexpected exception in scoring or response construction (and in reading the request) into the existing 503 `unable_to_assess` / `unavailable` body with a request id and the fixed message `Scoring could not complete`: no draft text, no error text, no decision, no score; the log line keeps its allow-listed fields. | `tests/test_phase6.py`: injected `RuntimeError` and `KeyError` in the scorer, in `transform_draft`, and in response mapping; the service keeps serving afterwards |
| WP-03 | `med_ui.walkthrough` reads the evaluation records through `med_docs.records.strip_members` with `SEALED_KEYS`, so the per-draft members are never parsed. The generated walkthrough is identical. | `tests/test_phase7.py`: a synthetic record whose sealed members are not valid JSON; the walkthrough reproducibility test |
| WP-04 | The API checks the SHA-256 of every dataset file and parses only `contacts.csv`, `messages.csv`, and `message_recipients.csv` (`med_data.io.read_serving_tables`); labels, drafts, splits, and feedback are never parsed. The bundle is loaded before the dataset read so a refused bundle fails fast. README, ARCHITECTURE, MODEL_CARD, the Phase 6 pages (and their generator), and the Phase 9 reads sentence state the offline and serving history rules separately. | `tests/test_phase6.py` (only three tables parsed; every file still checksummed; 49 validation drafts equal the stored table); scratch comparison of all 4,000 validation drafts (below) |
| WP-05 | AC02 is **insufficient evidence** (recall subject to AC01, which is insufficient evidence); it is met only if the baselines are beaten and AC01 is met, and not met if a baseline is not beaten or the budget is exceeded. Summary: 7 met, 3 insufficient evidence, 0 not met. | `tests/test_phase10.py` (status, summary, the flip when independence is assumed, two not-met cases) |
| WP-06 | `docs/phase_2/DATASET_SPECIFICATION.md` and `docs/phase_3/PROFILE_AND_TRANSFORM.md` print scratch-directory commands (`SCRATCH="$(mktemp -d)"`, quoted paths) and label the published paths as the historical outputs. `AGENTS.md` uses the same pattern. | Printed-command lint; the commands were run as printed (results below) |
| WP-07 | `AGENTS.md` names `med-synth-v4`, generator `1.3.0`, with a dated v2 note. This file no longer says "uncommitted" or "not pushed" for work that is merged and pushed; CI run 36852075499 on `ce46634` is recorded. | Public-document tests |
| WP-08 | The ten misplaced replies (P5-01 to P5-04, RA-01 to RA-06) are in their Updated cells, text unchanged. | Script: five cells per row, reply text equal to the old text |
| WP-09 | The full `pytest` runs the quality checks of the unmodified generated dataset once instead of twice (`validation_checks` in `tests/conftest.py`; `write_dataset` runs them even with `validate=False`). No test deleted, weakened, or deselected. | Timings below |

### Findings of this pass worth carrying forward

- **Phase 9 images predate the code change.** `med-api:phase9` and `med-ui:phase9` hold the earlier `med_api`, `med_policy`, `med_data`, and `med_ui` code. No bundle file changed, so the bundle check, the stored latency, rehearsal, smoke, and clean-checkout records stay true of those images, but a container built from them does not have WP-01, WP-02, or WP-04. **They need rebuilding** (`docker/build.sh`) to carry the new code, followed by `smoke` against the new containers; new records would need new names, because the Phase 9 records refuse to overwrite and were not touched. CI will rebuild nothing; it runs the fast selection and the spawned smoke test on push.
- **One earlier test changed on purpose.** `tests/test_phase9.py::test_a_file_changed_without_changing_its_shape_fails_the_digest_check` asserted that the API scope's structural policy check accepts a different finite cutoff (the P9-01 gap). The loader now refuses it, so the test expects that refusal plus the anchor failure; the UI-scope and anchor assertions are unchanged.
- **Cold start**, one process per run on this machine, app creation and startup as in the Phase 6 record: before 8.0 s (four runs 7.92 to 8.01 s; the Phase 6 record says 7.95 s), after 7.4 s (four runs 7.35 to 7.38 s). The saving comes from not parsing the draft, draft-recipient, label, split, and feedback tables and from not counting records of unparsed files; `messages.csv` still dominates. The stored latency record was not remeasured.
- **Parity.** In process, all 4,000 `validation_product_like` drafts through the API: 4,000 of 4,000 decisions equal `validation_scores.csv` (8 warned), largest score difference 3.9e-15 (the Phase 6 record says 3.9e-15). The same requests through the pre-change code (a detached worktree at `ce46634`) gave identical decisions, email scores, recipient scores, and flagged recipients for all 4,000. No latency was recorded.
- **Follow-up fixed (2026-10-02, after an independent re-check).** `python -m med_api report` parsed the whole `test_evaluation.json` through `med_policy.report.stored_results`, only to list the scenarios never warned. `stored_results` now cuts the sealed members out of the text first (`med_docs.records.strip_members`), and `med_api.report._limits` derives that list from the aggregate `email_by_scenario` slices; the result (S01, S04, S11) and `docs/phase_6/SCORING_FLOW.md` are unchanged, and a test shows the page equals the generator's output from aggregates only. **Left as it is (decided 2026-10-02: the question was dropped):** `python -m med_policy report` still parses the whole frozen record, because it writes `docs/phase_5/ERROR_ANALYSIS.md`, which lists every missed test mistake by draft id (the Phase 5 page is the originating writer of those rows); making it aggregate-only would mean dropping those published tables, which was not done. `python -m med_api report` also still reads every dataset table to pick its examples. Neither was run in this pass. A selection of the policy that picked the "above every score" cutoff when the top score is exactly 1.0 would now be refused at load, because that cutoff exceeds 1. The remaining full-suite cost is mostly two repeated 60 s validations of mutated manifests, one 125 s real-history comparison, and a 55 s published-table comparison; none repeats shareable work.

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

The `ui` extra installs Streamlit, which requires pyarrow. With pyarrow importable, pandas 3.0.6 stores strings in Arrow by default. Results are unchanged (full `pytest` passed under Arrow strings: 121 passed in 1018.53 s; `med_data validate` 31 checks passed in 159.8 s), but the pipeline is about three times slower (`validate` 49.1 s with pyarrow blocked). `tests/conftest.py` sets `mode.string_storage = "python"`, restoring the test runtime. The CLIs are not pinned; the UI guide suggests a separate virtual environment for the UI. Decided in Phase 9: split environments (the API image has no pyarrow).

## Phase 8 — what was built (branch `phase-8-monitoring`, 2026-09-30)

- **Package** `src/med_monitor/`: `version.py` (monitor version, paths, every threshold and minimum sample size; bundle versions come from `med_policy.version` and `med_api.version`), `data.py` (validation-only streaming; a frozen id raises `FrozenRowError`), `reference.py` (train-only input reference, checksum-verified against the feature manifest), `drift.py` (PSI, exact tests, the three findings), `observations.py` (per-response reduction and window aggregates), `stream.py` (deterministic replay plan), `replay.py` (drives the API; refuses a service that does not report the frozen bundle), `alerts.py` (pure checks over stored aggregates), `feedback.py` (click and dataset feedback, simulated review, efficacy), `bundles.py` (mismatched and corrupted bundles handed to the real API), `experiment.py` (sample-size arithmetic), `report.py` (generates `docs/phase_8`), `cli.py`. No module imports training code or calls `.fit`.
- **Commands** (`python -m med_monitor`): `build-reference`, `replay` (in process, or `--api URL`), `feedback`, `bundle-checks`, `report`. Each record command refuses to overwrite. Records are in `artifacts/med-monitor-v1/` (`reference.json`, `replay_plan.json`, `replay.json`, `feedback_review.json`, `bundle_checks.json`); the documents are `docs/phase_8/{MONITORING,DRIFT_REPLAY,FEEDBACK_REVIEW,EXPERIMENT_PROPOSAL,RUNBOOK}.md`, all generated from the records. A test regenerates them and requires an exact match.
- **What is stored:** window aggregates only (counts, histograms, percentiles, one highest-allowed score and one margin per window and slice), the plan's draft ids, and the simulated review queue (draft id, decision, coarse stratum, simulated label, delay). No address, name, subject, body, or per-email score. The API's log allow-list is unchanged.
- **Tests:** `tests/test_phase8.py`, 32 tests in about 22 s (one shared in-process API, small live replays). Sixteen mutations of the key rules (reference reads validation, gate removed, pending review applied, frozen id allowed, unreturned labels counted, a `.fit` call, and others) were each caught by a test. Two survived at first: one was aimed at the wrong test, and the other showed that the once-per-email counting function was only tested through the stored reference, so it now has a direct assertion. `tests/test_phase7.py::test_package_version_and_ui_extra` now accepts version 0.7.0 or later.

### Phase 8 review fixes (P8-01 to P8-03, 2026-09-30)

- **P8-01, A/B primary outcome.** Both arms run the same frozen policy, so recall is identical by construction and cannot be a treatment effect. The proposal's primary outcome is now the correction rate among policy-warned mistakes (a sender's behavior), with capture timing (snapshot at first assessment, reviewer labels on the snapshot, recipients at send, a fixed label cutoff) and correction logging as a precondition. Recall is descriptive. Sample sizes are on an assumption grid, since no correction data exists.
- **P8-02, frozen test file.** The monitor no longer parses `test_evaluation.json` (it holds per-draft test outcomes), even to quote the aggregate. `reference.json` lost `recorded_test_pass`; references come from the validation record in `policy.json`. The generated documents now say exactly what is and is not opened. `med_ui.walkthrough` (Phase 7) still parses that file for one sentence; that is unchanged and is flagged in `comments.md`.
- **P8-03, outage vs version.** A service answering without a loaded bundle returns a failure with no provenance. That is now an availability alert (`bundle_available`), and `served_versions` alerts only when a response names a different bundle.
- `reference.json` and `replay.json` were regenerated (schema and window fields changed); `replay_plan.json` and `feedback_review.json` regenerated byte-identical; `bundle_checks.json` is unchanged.

### Design findings worth carrying forward

- **Lifetime-count inputs are structural.** Seven features (`sender_outbound_count`, `sender_history_span_days`, `pair_outbound_count`, `pair_inbound_count`, `domain_outbound_count`, `co_joint_message_count`, `pair_text_message_count`) leave the train range as time passes (train-vs-validation PSI 0.7 to 8; about 95% to 100% of reference and current window emails above the train maximum for the two sender-level ones). A train-only PSI alert on them would fire on every future window, so the monitor counts them and never alerts on them. It cannot say when that extrapolation starts to matter. Fixing that means monitoring rates or windowed counts, or a rolling refit: model changes, outside this phase.
- **Unit of analysis.** Eleven features describe the sender or the draft, so a six-recipient email repeated its value six times and put unshifted reference windows in the alert band. They are now counted once per email, in the reference and in every window.
- **PSI is slow on rare states.** A 0/1 indicator moving from about 2% to about 13% reaches PSI 0.23, below 0.25. Indicators therefore also alert on a share shift of 0.10. That rule was added after seeing this on validation windows; the report says so.
- **The train reference is enriched.** Two features (`co_partner_fraction`, `pair_outbound_rate_per_day`) sit in the watch band on ordinary reference windows for that reason.
- **Reviewed evidence is nearly empty.** `reviewer_feedback.csv` has 3 rows, all train, none accepted. `var/feedback.jsonl` had 2 unreviewed clicks with no draft link and no assessment time, so label delay cannot be computed for them. Every coverage, delay, and efficacy figure comes from a *simulated* reviewer (stipulated labels, gamma delays, always right).
- **Confirmed performance cannot be stated.** The reference windows hold 18 of the 20 validation mistakes and the current windows 2, so no comparison reaches the 30 confirmed mistakes per side that the check requires.
- **The replay is built from 40 distinct first-contact drafts,** so counts of near-cutoff emails repeat drafts (window 8: 8 emails, 4 distinct drafts).

### Replay, measured 2026-09-30 (live API, in process, v4 bundle)

| Item | Result |
| --- | --- |
| Plan | 8 windows of 500 `validation_product_like` emails in send order; windows 1-4 reference, window 5 unshifted control, windows 6-8 replace 4%, 8%, 16% of routine drafts with copies of legitimate first-contact validation drafts. Plan checksum `a16f64569efd3729…` |
| Reference windows (2,000 emails) | 6 warned, 0 blocked, 0 unable to assess, 25 with limited relationship history, 2 in the near band, client p50 27.8 / p95 62.7 / p99 69.0 ms (regenerated after the review fixes; latency varies between runs) |
| Unshifted windows | No check alerts in window 5; no reference window has an input-drift alert |
| First alerts | Window 6 limited-relationship-history rate (20 of 500 against 25 of 2,000); window 7 input drift on one feature (`pair_outbound_rate_per_day`, low confidence); window 8 near-cutoff scores (8 of 500 against 2 of 2,000) and four first-contact inputs |
| Three findings, window 8 / pooled | Input drift: alert / watch. Decision rate: insufficient sample (window) / no change detected, 2 warned of 2,000 against 6 of 2,000 (p = 0.289). Confirmed performance: insufficient sample, 16 and 2 confirmed mistakes against a minimum of 30 |
| Simulated review | 192 emails queued: all 8 warned, all 133 allowed emails scoring at least 0.9, 6 of 69 scoring 0.5 to 0.9 (inclusion 0.10), 45 of 3,790 below 0.5 (inclusion 0.01); delay median 5.1 days, 90th percentile 11.9 days; in window 8, 40 reviewed allowed emails scoring at least 0.9 were all confirmed intended |
| Bundle checks | Control served; the 9 altered bundles (policy version, model run, model checksum, corrupted model, blocking on, non-numeric cutoff, missing policy, tampered feature file, previous bundle) were each refused: `/ready` 503, `/assess` `unavailable`, no decision, no score |
| Transport | The same replay over HTTP against `python -m med_api serve` gave an identical plan and identical aggregates apart from timing (checked in scratch, not stored) |
| Runtime | Replay 129.4 s; feedback 1.4 s; bundle checks about 20 s; report 1.5 s |

## Phase 9 — what was built (branch `phase-9-deploy`, 2026-09-30 to 2026-10-01, committed as `89e593a`)

- **Package** `src/med_deploy/` (`med-deploy-v1`, package version 0.9.0), commands `python -m med_deploy <command>`: `check-bundle` (API and UI scopes; `--image` demands the exact file set), `record-scenarios` and `regress` (scenario fixtures), `smoke`, `environment`, `reads` (file audit), `latency`, `rehearse`, `images`, `mutation-check`, `browser-check`, `platform-check`, `clean-checkout`, `rebuild-demo`, `record-run`, `report`. Every measurement record refuses to overwrite (`test_runs.json` keeps the latest run of each named command). The two images ship only six of its modules (`__init__`, `__main__`, `bundle`, `cli`, `environment`, `version`); the rest drive checks from the host, so editing one does not change an image.
- **Scenario regression** (`scenarios.py`, record `scenario_regression.json`): 14 fixtures chosen by rule from `validation_scores.csv` (validation_product_like only) plus 6 derived request variants (repeated address across roles, malformed address, no recipients, answer field in the request, unknown address, unknown snapshot). Each records source draft id, rule, desired outcome, recorded outcome. **Known misses S01, S04, S11 stay in as known misses.** The record holds ids, scores, and codes, no address, subject, or body. `compare` flags a changed decision, score (tolerance 1e-9, none for decisions), provenance, code, limitation, role, aggregation, cutoff semantics (equality warns), or a failure that carries a decision, score, recipients, or `allow`. `mutation-check` applies seven one-line mutations to a scratch copy of `src/` and requires the suite to catch each (all caught; the unmutated control passes).
- **Smoke** (`smoke.py`): the real Streamlit script under `AppTest` against a live API over HTTP; compares what the screen shows with the API for the same request (readiness and versions, allow, warn, edit then stale then reassess, `invalid_input`, `unavailable`, one feedback click to a disposable file, no local scoring). Run against a spawned process and against the containers.
- **Pins:** `constraints.txt` (third-party only; core, `dev`, `ui`, `monitor`), `.python-version` 3.11.14. The fresh-venv install and both images match every pin. The first Linux UI image build installed `watchdog` (a Streamlit dependency on non-macOS platforms) **unpinned**; it is pinned (`watchdog==6.0.0`) and a test evaluates dependency markers for macOS and Linux.
- **Images** (`docker/Dockerfile.api`, `docker/Dockerfile.ui`, default-deny `*.dockerignore` lists, `docker/build.sh`): base `python:3.11.14-slim-bookworm` pinned by tag and index digest; wheels only; non-root uid 10001; `/ready` health check; each build runs `check-bundle --image`, which fails on a missing, extra, altered, or frozen-outcome file. The API image (core only, **no pyarrow**) holds exactly the 21 files the API reads; the UI image (`ui` extra, pyarrow) holds the 8 files the screen reads, no model, no features, no `test_evaluation.json`. The lists come from a measured file audit (`reads.json`), not a guess. `compose.yaml`: ports on `127.0.0.1` only, read-only root filesystem, all capabilities dropped, `no-new-privileges`, limits (API 2 CPUs and 2 GiB, screen 1 CPU and 1 GiB), the feedback folder `var/demo` is the only writable mount.
- **Anchored digests (review item P9-01):** `artifacts/med-deploy-v1/bundle_digests.json` anchors the SHA-256 of `policy.json`, `validation_scores.csv`, and `validation_evaluation.json`, which no other checksum covers (a different finite `T_warn` passed the API scope before). Recorded once by `record-digests`, which refuses unless each digest equals the blob at `main`; `check-bundle` compares in both scopes and the image builds bind-mount the manifest for the check without copying it. The running services do not re-verify it (build and CI only).
- **CI** (`.github/workflows/ci.yml`): pinned install, `pip check`, `environment --check`, `check-bundle` for both scopes, `pytest -m "not slow"`, `smoke --spawn`. The steps are defined once in `ci.py`; a test requires the workflow to contain each. It never fits, retrains, selects a cutoff, or evaluates the frozen subsets. **GitHub Actions itself was not run from this machine**; the same steps ran in a clean copy with a fresh venv (`clean_checkout.json`).
- **Markers:** `slow` is registered in `pyproject.toml` and applied to seven existing tests (29 to 123 s each). No test was deleted or weakened. One existing assertion was relaxed for the required version bump: `tests/test_phase8.py::test_package_version_script_and_light_dependencies` had `version == "0.8.0"` and now requires `>= 0.8.0` (Phase 8 made the same change to the Phase 7 check).
- **Rollback rehearsal** (`rehearsal.py`; review item P9-02 fixed: the screen container must be healthy at every step and its in-network view of `/ready` is recorded; the failed-state screen observation is labeled as made by the screen script on the host, not in a browser): container level (known-good image id versus two thin candidate images, through compose) and process level (known-good paths versus disposable copies with one fault each: a flipped model byte, a missing policy). Each candidate: `/ready` 503 with the reason, `/assess` `unable_to_assess` with no decision, score, or versions, every assessed fixture flagged by the suite, the container health command fails, the review screen disables assessment. Each restore re-verifies readiness, exact versions and `T_warn`, an allow, a warning, all 20 fixtures, and feedback isolation.
- **Docs** `docs/phase_9/` (`TEST_REPORT.md`, `REPRODUCIBILITY.md`, `LOCAL_DEPLOYMENT.md`, `ROLLBACK_REHEARSAL.md`) are generated by `python -m med_deploy report` from the records; a test regenerates them and requires an exact match. README has a short quick start. `AGENTS.md` gained the pinned-install and fast-selection lines and the rule never to run `med_features build` or `med_models run` with default paths.

### Decisions and findings worth carrying forward

- **Split environments, no pandas pin in the packages** (the Phase 8 open item): the API image has no pyarrow (strings are held in `StringArray`), the screen image has it (`ArrowStringArray`). `tests/conftest.py` still pins Python string storage for the test run.
- **`python -m med_ui` listened on every network interface** (Streamlit's default). It now defaults to `127.0.0.1` with `--host` to change it (`src/med_ui/cli.py`, `config.py`, one sentence in `docs/phase_7/UI_GUIDE.md`). The container passes its own `--server.address`.
- **The Docker daemon was not running when Phase 9 started.** Docker Desktop was started with `open -a Docker` and stayed up; everything container-related below was run against Docker 29.4.0 (aarch64, 10 CPUs, 8 GiB VM).
- **Base image pin.** The digest first copied from `docker manifest inspect` was the amd64 image inside the index, which ran emulated on Apple silicon; the pin is the multi-architecture index digest.
- **`cli.py` is in the images.** Two CLI defects (an option swallowed by an argparse remainder, found late) forced image rebuilds; image ids in the records are the final ones.
- **Threshold fixture across architectures.** `T_warn` is the exact score of one validation draft, so a last-digit difference could flip it. On arm64 and on an emulated linux/amd64 image it scores exactly at `T_warn` and warns; all 20 fixtures pass there (largest score difference from the arm64 record 8.9e-16). One emulated amd64 check is not a guarantee for every machine.
- **Scratch rebuild** (`rebuild-demo`, every output in a scratch directory, published files hashed before and after): feature files, transformer, `model.joblib`, and model metadata are byte-identical; scores on 4,970 validation rows are identical. `experiments.json` differs only by the post-hoc `eligibility.recomputed` note; three Phase 4 tables differ only in the wall-clock "Fit seconds" columns.
- **Concurrency.** With four clients at once, one API process on 2 CPUs queues requests and its client p95 is close to the 300 ms target (above it in some runs). AC05 specifies one request in flight and is met; capacity planning is out of scope.
- **Privacy.** New records hold aggregates, decisions, ids, and scores of 20 curated fictional validation fixtures; no address, subject, or body. The API log allow-list is unchanged.

### Phase 9 verified results (UTC dates as stored in the records)

| Command | Result |
| --- | --- |
| `python -m med_deploy record-digests`, then `check-bundle --scope api` and `--scope ui` | Digests of `policy.json` and the two stored validation files anchored and verified against the blobs at `main` (`0f29ae02a152`); both scopes pass, including `anchored_digests` |
| `python -m med_deploy record-scenarios` | 20 fixtures recorded; three known misses kept |
| `python -m med_deploy mutation-check` | Control 20 of 20; 7 of 7 mutations caught |
| `python -m med_deploy reads` | API read 21 files, screen read 8; both equal the bundle check; nothing written under the repository root |
| `python -m med_deploy smoke --spawn`, and against the containers | Passed (11 and 12 checks) |
| Browser check of the UI container (`browser-check`, manual page text) | Decision, score, cutoff, flagged recipient, and codes equal the API's |
| `python -m med_deploy latency` (API container, final image) | 1,000 measured requests after 20 warm-up, one in flight: client p50 27.84 ms, p95 64.47 ms, p99 80.31 ms, 0 failures, 1,000 of 1,000 decisions match the stored validation table; AC05 met on this machine; pyarrow not importable in the measured process. The four-client probe had p95 320.1 ms (above 300 ms; not AC05) |
| `python -m med_deploy rehearse --mode container` and `--mode process` | Passed (7 steps each); known-good image id `sha256:85d67e46cbf709ac8fedb7d3fa0219929bba940f3f109a4c582714650707d8ee` unchanged. The screen container is required to be healthy at every step and sees `/ready` 200 / 503 / 200 / 503 / 200 from inside its network |
| `python -m med_deploy platform-check --platform linux/amd64` | 20 of 20 fixtures pass on an emulated x86_64 image |
| `python -m med_deploy rebuild-demo` | Published files unchanged; 12 of 16 compared files byte-identical, scores identical (see above) |
| `python -m med_deploy clean-checkout` (every CI step, scratch copy, fresh venv, Python 3.11.14) | Passed in 2m36s (256 files) |
| `python -m pytest tests/test_phase9.py tests/test_public_docs.py` (after every record existed) | 31 passed, 0 skipped, 28.1 s |
| `python -m pytest -m "not slow"` (CI selection) | 192 passed, 1 skipped (the clean-checkout record test, until that record exists), 7 deselected, 119.3 s |
| `python -m med_data validate --data data/med-synth-v4` (2026-09-30 UTC, before the review fixes; no data changed since, and the full `pytest` re-runs the quality checklist) | 31 checks passed, 151.7 s |
| `python -m pytest` (full release gate, after the review fixes, 2026-10-01 UTC) | 200 passed, 0 failed in 537.4 s (8m57s): 170 existing tests plus 30 new Phase 9 tests |

## Phase 10 — what was built (branch `phase-10-docs`, 2026-10-01; committed as `412ad25` and merged into `main`)

Documentation only. Package version 0.10.0 (`pyproject.toml`, with a `med-docs` script). No model, feature, policy, `T_warn`, blocking, dataset, API contract, UI behavior, monitoring, deployment configuration, artifact, or record was changed; `git status` shows nothing under `data/` or `artifacts/`, and `docs/phase_1/` is untouched.

- **Package** `src/med_docs/` (`med-docs-v1`), standard library only: `version.py` (record locations, the allow-list of key paths read from `test_evaluation.json`, the sealed keys, `INDEPENDENCE_ESTABLISHED = False`), `records.py` (parses a record once with an `object_pairs_hook` that drops `outcomes`, `examples`, and `examples_validation`, then takes explicit key paths), `facts.py` (derivations and the status rules for AC01 to AC10), `blocks.py` (generated blocks inside hand-written Markdown), `render.py`, `documents.py`, `fmt.py`, `cli.py`. Commands: `python -m med_docs report` and `python -m med_docs check` (both take `--root`).
- **Generated** (never edited by hand; `check` fails when stale): `docs/RESULTS.md` whole, and blocks in `README.md` (headline), `docs/ARCHITECTURE.md` (artifact and image tables), `docs/MODEL_CARD.md` (seven numeric blocks), `docs/DEMO_WALKTHROUGH.md` (six step blocks), `docs/LIMITATIONS_AND_FUTURE_WORK.md` (evidence block). **Hand-written:** `docs/USAGE_GUIDE.md`, `docs/README.md` (index), and the prose around the blocks, which carries no number of its own (a test enforces it, with narrow exemptions for code, link targets, citation rows, list markers, and phase and step labels). The README is 2,144 words, against 3,528 before.
- **Records read** (nothing else): `data/med-synth-v4/{dataset_manifest,quality_report}.json`; `artifacts/med-features-v2/{artifact_manifest,quality_report}.json`; `artifacts/med-model-v2/{model_metadata,experiments}.json`; `artifacts/med-policy-v2/{policy,validation_evaluation,test_evaluation}.json`; `artifacts/med-api-latency/med-policy-v2/latency.json`; `artifacts/med-monitor-v1/{replay,bundle_checks,feedback_review}.json`; twelve records under `artifacts/med-deploy-v1/`. From `test_evaluation.json`: the top-level `policy_version`, `policy_sha256`, `T_warn`, `blocking_enabled`, `evaluated_at`, and for each test subset `policy/{cutoff,email,recipient,attribution,interventions,coverage}` and `slices/email_by_scenario`. The test rows for the rules policy and always-allow were not read (the validation record supplies those comparators), and no draft table, feature file, or per-draft outcome was opened.

### Headline results, as generated

| | `validation_product_like` (chose the cutoff) | `test_product_like` (one frozen pass) |
| --- | --- | --- |
| Emails, misdirected | 4,000, 20 | 6,000, 30 |
| Mistakes warned, recall (exact 95% if independent) | 8 / 20, 0.400 [0.191, 0.639] | 9 / 30, 0.300 [0.147, 0.494] |
| Legitimate emails warned | 0 / 3,980 | 0 / 5,970 |
| Detections, interruptions per 1,000 emails | 2.00, 2.00 | 1.50, 1.50 |

Product-like mix 0.5% (a simulation assumption). Per-1,000 rates use every email in the subset as the denominator; the AC01 rate uses legitimate emails only. S01, S04, and S11 are not warned on any of the four subsets. Detection did not improve and is not claimed to.

### Final acceptance table (`docs/RESULTS.md` section 5)

| ID | Status | Measured |
| --- | --- | --- |
| AC01 | insufficient evidence | 0 / 5,970 legitimate emails warned (0.00 per 1,000); exact upper 0.62 only if emails were independent |
| AC02 | insufficient evidence (whole-project fix WP-05; Phase 10 first recorded a mixed status, then "met") | 9 / 30 mistakes warned, recall 0.300 [0.147, 0.494]; no mistake warned in S01, S04, S11. Phase 1 defines AC02 as recall subject to AC01, and AC01 is insufficient evidence. Per scenario (Phase 5 reading): met for S09; partly met for S02, S08; not met for S01, S04, S11 |
| AC03 | met | cutoff chosen on `validation_product_like`; policy written before the one test pass |
| AC04 | met | blocking disabled; 0 blocks |
| AC05 | met | client p95 57.04 ms (Phase 6) and 64.47 ms (Phase 9), one request in flight |
| AC06 | met | 15 of 15 assessed fixtures follow maximum aggregation; equality warns |
| AC07 | insufficient evidence | 0 of 541 legitimate novelty emails warned on `test_product_like`; S11 mistakes not warned |
| AC08 | met | 5 of 5 failure fixtures, 9 of 9 altered bundles, 4 of 4 failing candidates fail closed |
| AC09 | met | 5 of 5 flagged recipients carry codes; provenance compared |
| AC10 | met | 31 dataset checks passed; desired and recorded outcomes kept apart |

AC01 to AC05 and AC07 follow the rules `med_policy.report` applies and agree with the Phase 5 report (a test compares the statuses). **AC06, AC08, AC09, and AC10 had no stored status before Phase 10.** Their rules are in `med_docs.facts`, are printed beside each status in `RESULTS.md`, and turn a status to "not met" when a record stops satisfying them (a test alters records so that nine statuses turn to "not met", and one drifted record stops the generator). They are derived from the Phase 8 and Phase 9 records and are open to challenge; AC10 is a documentation criterion judged by dataset checks and tests, not a measurement.

### Decisions and findings worth carrying forward

- **Sender concentration was not re-derived.** The count behind AC01's independence limit (most test drafts from one sender) needs `drafts.csv`, which Phase 10 does not open. `RESULTS.md` links the Phase 5 independence table instead and states the limit in words; `INDEPENDENCE_ESTABLISHED = False` is a visible constant.
- **A statement that depends on a comparison is guarded.** `render._require` stops the generator if a record no longer supports a sentence (for example, that the recorded known misses score below the highest legitimate email).
- **Diagrams.** The two Mermaid diagrams (README, architecture) were parsed with Mermaid 10 in a scratch directory (both parse; a deliberately broken diagram fails). That check is not in the test suite, which verifies structure only (every package, module, and directory named exists).
- **The private handoff note** `project_context/handoff_notes.md` (gitignored) holds the evidence map, a talk track keyed to `docs/DEMO_WALKTHROUGH.md`, likely questions, and weak points. Its figures were formatted from the same facts.

### Edits to earlier documents (each stale or contradicted sentence; no link was broken)

1. `docs/phase_2/DATA_QUALITY_AND_LEAKAGE.md`: the Q31 row quoted v3 timing percentages (about 1.40% and 0.63%), now a pointer to the v4 quality report; and a known-limits bullet said the larger sample "supports rigorous exact binomial confidence bounds" for the budget, which contradicts the AC01 finding. It now says the bound is conditional on independence and that AC01 is insufficient evidence.
2. `docs/phase_8/RUNBOOK.md`, regenerated after editing two template strings in `src/med_monitor/report.py`: "no container, CI, or live switch ... exists yet, and those belong to the next phase" and "capabilities ... that do not exist yet: ... a rehearsed rollback". Phase 9 built containers, CI, and a rehearsed rollback (an image swap). The other four Phase 8 documents regenerate byte-identical.

### Observed and not edited

- `AGENTS.md` named `med-synth-v2`, generator `1.1.0`, and `data/med-synth-v2` in its dataset-identity line and its Testing commands (stale since v4). Fixed in the whole-project fix pass (WP-07), 2026-10-01: it now names `med-synth-v4`, generator `1.3.0`, with a dated note about the v2 baseline.
- `docs/phase_4/DECISION_RECORD.md` ("Tree scores") says the tree's positive rows share a score with 0 legitimate rows and calls the low average precision a tie penalty; with no legitimate row in that score there is no mixed leaf, so the sentence looks like template text from an earlier dataset version. It is generated by `med_models.report`, was not changed, and should be checked by whoever owns Phase 4. `docs/phase_5/ERROR_ANALYSIS.md` says "1 legitimate emails score above it" (a pluralization slip, generated by `med_policy.report`).
- A second worktree for branch `ci-linux-fix` (another session, under that session's scratchpad) appeared during this session at `980f2d1` with no difference from `main`. Phase 10 does not touch CI or Phase 9 records; if that branch changes either, the CI and Linux statements in `docs/LIMITATIONS_AND_FUTURE_WORK.md`, `docs/RESULTS.md` (from `clean_checkout.json`), and the README need regenerating or revising.

### Phase 10 tests

`tests/test_phase10.py`, 23 tests, about 1 s. Public-document scan and index coverage; README length (under the 3,500-word cap), citations and version; documents equal the generator output, and `report` and `check` round-trip on a scratch copy and detect a hand edit; key numbers (recall counts, false warnings, per-1,000 rates, intervals, AC statuses, latency p95s) read independently from the records and found in `RESULTS.md`; statuses and counts agree with the earlier generated Phase 5, 6, and 9 documents; AC01 insufficient evidence and S01, S04, and S11 shown as misses; nine statuses flip to "not met" when a record is altered, and a drifted record stops the generator; "probability", blocking, and unearned-claim lints; a numeric-literal lint on hand-written text; every printed command exists (module, subcommand, option, extra, file); the generator imports only the standard library and loads no scoring, fitting, or data code (subprocess `sys.modules` check); `outcomes` replaced by sentinels, removed, or nested leave the output byte-identical and no sentinel appears; a spy confirms both evaluation files are parsed with the sealed keys dropped; an allow-list touches nothing it does not name; record paths equal the version modules; the diagram names real components; the model card labels every technique. Fifteen deliberate mutations of the sources and documents (hand edit, a pandas import, an unsourced number, independence assumed, a score called a probability, an outcome added to the allow-list, sealed keys not dropped, a nonexistent command, blocking claimed, a private path, a dropped index entry, a `med_policy.report` import, an oversized README, and a weakened AC01 rule) were each caught by a test, and the unmutated control passed.

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
| `python -m med_monitor build-reference`, `replay`, `feedback`, `bundle-checks`, `report` (2026-09-30) | Wrote `artifacts/med-monitor-v1/` and `docs/phase_8/` from the final code, in that order; see the replay table above |
| `python -m pytest tests/test_phase8.py` (2026-09-30) | 30 passed in about 22 s |
| `python -m pytest` (2026-09-30, Phase 8 final) | 168 passed, 0 failed in 532.11 s (8m52s) |
| `python -m pytest` (2026-09-30, after the Phase 8 review fixes P8-01 to P8-03) | 170 passed, 0 failed in 521.49 s (8m41s). `med_data validate` was not rerun: no data, feature, or model file changed |
| `python -m med_data validate --data data/med-synth-v4` (2026-09-30, Phase 8 final, pyarrow installed) | 31 checks passed, 161.48 s |

| `python -m pytest tests/test_phase10.py tests/test_public_docs.py` (2026-10-01, Phase 10) | 24 passed in 1.10 s |
| `python -m med_docs report`, then `python -m med_docs check` (2026-10-01) | Wrote `docs/RESULTS.md` and the generated blocks of five documents; then "Generated documents match the stored records." |
| Mermaid 10 `parse` on both diagrams, in scratch (2026-10-01) | Both OK; a deliberately broken diagram fails. Not part of the suite |
| Fifteen deliberate mutations against `tests/test_phase10.py`, in scratch copies (2026-10-01) | 15 of 15 caught; the unmutated control passed. One mutation was first ineffective (the index links a page twice) and was redone |
| `python -m med_monitor report` into a scratch directory (2026-10-01) | Four of five Phase 8 documents byte-identical; `RUNBOOK.md` differs only by the two corrected sentences, then copied into `docs/phase_8` |
| `python -m pytest` (full release gate, 2026-10-01 UTC, Phase 10) | 223 passed, 0 failed, 1 dependency warning in 587.18 s (9m47s), 03:02:30 to 03:12:19: the 200 existing tests plus 23 in `tests/test_phase10.py`. Run once, after the last change to any public file or source (the 03:02 start followed the final wording fix to the generated architecture table; an earlier attempt was stopped after two minutes for that reason). Over the Phase 9 gate of about nine minutes by about 50 s; the Phase 10 tests take about 1 s of it |
| `python -m med_docs report` and `check` (2026-10-01, after the CI wording change in the Phase 10 docs) | Regenerated `docs/LIMITATIONS_AND_FUTURE_WORK.md` and `docs/RESULTS.md`; check: generated documents match the stored records |
| `python -m pytest tests/test_phase10.py tests/test_public_docs.py` (2026-10-01, after the CI wording change) | 24 passed in 1.14 s |
| `python -m pytest -m "not slow"` (2026-10-01, merged `main` at `c2204c1`, macOS) | 216 passed, 7 deselected in 126.9 s |
| `pytest -m "not slow"` in `python:3.11.14-slim-bookworm`, linux/amd64 emulated (2026-10-01, merged Phase 10 and CI fix) | 216 passed, 7 deselected in 205.3 s |
| GitHub Actions run 36811479847 (2026-10-01, `50b82bd`, `ubuntu-24.04`) | Success on every step: pinned install, `pip check`, environment, both bundle checks, `pytest -m "not slow"`, `smoke --spawn`; no annotations |
| `python -m med_docs report` and `check`; `python -m med_deploy report` (2026-10-01, Phase 10 review fixes) | Regenerated `RESULTS.md`, `MODEL_CARD.md`, `README.md` blocks, and `docs/phase_9/` from unchanged records; check passes |
| `python -m pytest tests/test_phase10.py tests/test_phase9.py tests/test_public_docs.py` (2026-10-01, Phase 10 review fixes) | 57 passed in 39.1 s |
| `python -m pytest` (full release gate, 2026-10-01, Phase 10 review fixes) | 226 passed, 0 failed in 593.07 s (9m53s): 200 earlier tests plus 26 in `tests/test_phase10.py`. At the edge of the 10-minute budget |
| `python -m med_data validate --data data/med-synth-v4` (Phase 10) | Not rerun: nothing under `data/` changed (`git status` shows no path under `data/`). Last result: 31 checks passed (2026-09-30, 151.7 s) |
| GitHub Actions run 36852075499 (2026-10-01, `ce46634`, `ubuntu-24.04`), read through the public GitHub API | Success on every step of the `checks` job; this is the last pushed commit and does not cover the whole-project fixes |
| `pytest` (full, unchanged tree at `ce46634`, detached worktree, 2026-10-01 11:23 to 11:33 UTC; the baseline for WP-09) | 226 passed in 577.40 s (9m37s), while the fixes were being edited (light CPU use) |
| API cold start before and after WP-04 (one process per run, app creation and startup, alternating old and new code, 2026-10-01) | Before 7.985, 7.933, 8.034, 8.016 s; after 7.395, 7.369, 7.382, 7.391 s |
| API parity after WP-04, in process, all 4,000 `validation_product_like` drafts (validation-only streaming loader; no latency recorded) | 4,000 of 4,000 decisions equal `validation_scores.csv`, 8 warned, largest score difference 3.886e-15; identical decisions, email scores, recipient scores, and flagged recipients to the pre-change code |
| Nine one-line mutations of the fixes, in a scratch copy (2026-10-01) | 9 of 9 caught by the new tests (no range check, no digest check, exclusive upper bound, no unexpected-error boundary, error text echoed, walkthrough parses sealed members, every table parsed, checksums skipped, AC02 met on utility alone) |
| Printed Phase 2 and Phase 3 build commands, run as printed with scratch paths (2026-10-01) | `med_data build` exit 0, `med_data validate` on the scratch dataset 31 checks and the same manifest as `data/med-synth-v4`, `med_features build` exit 0 with a feature artifact identical to the published one; the quality report has the same lines in a different table row order |
| `python -m med_docs report`, then `python -m med_docs check` (2026-10-01, whole-project fixes) | Regenerated `RESULTS.md`, the README headline, `MODEL_CARD.md`, and the `ARCHITECTURE.md` tables; "Generated documents match the stored records." `python -m med_deploy report` changed one sentence of `docs/phase_9/LOCAL_DEPLOYMENT.md`; no record changed |
| `python -m pytest -m "not slow"` (2026-10-01 12:45 to 12:47 UTC, whole-project fixes) | 248 passed, 7 deselected, 1 dependency warning in 138.86 s |
| `python -m pytest` (full release gate, 2026-10-01 12:47:28 to 12:56:25 UTC, whole-project fixes) | **255 passed, 0 failed, 1 dependency warning in 536.23 s (8m56s)**: the 226 earlier tests plus 29 new ones. Before: 577.40 s for 226 tests (recorded 593.07 s in the Phase 10 review). The saving is one 61 s validation of the unmodified dataset shared by two tests; the new tests cost about 20 s |
| `python -m med_data validate --data data/med-synth-v4` (2026-10-01 12:56 UTC, whole-project fixes, pyarrow installed) | 31 checks passed, 164.96 s. Nothing under `data/` or `artifacts/` changed (`git status` shows no path under either) |
| `python -m pytest` (full release gate, 2026-10-02 06:22:26 to 06:31:26 UTC, after the `med_api report` follow-up) | **257 passed, 0 failed, 1 dependency warning in 539.13 s (8m59s)**: the 255 of the first run plus two for the aggregate-only report path. Supersedes the 255-test run above as the current result; `med_docs check` passes, `med_data validate` was not rerun (nothing under `data/` or `artifacts/` changed). Two more mutations (`stored_results` parses the sealed members; `_limits` reads per-draft outcomes) were each caught |

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
| AC02 | Phase 5 per-scenario reading: met for S09; partly met for S02, S08; not met for S01, S04, S11. Final overall status (WP-05): insufficient evidence, because AC02 is recall subject to AC01 |
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

- **Phase 9 review (2026-10-01):** P9-01 (anchor the digests of `policy.json` and the stored validation files) and P9-03 (record commands that can be run as printed) were fixed as suggested (on re-check, P9-03 still had a small wording issue in the printed commands; it was fixed with P10-03 on 2026-10-01); P9-02 was fixed for the health defect and partly for the browser point (the failed-candidate screen observation is labeled as host-side; no failed-state browser check was added). Replies are in `project_context/comments.md`. The images, smoke, latency, rehearsal, amd64, clean-checkout, and test-run records were re-recorded after the fixes.
- **Phase 10 review fixes (2026-10-01, branch `phase-10-review-fixes`):** P10-01 (Medium): the generator removes `outcomes`, `examples`, and `examples_validation` from the evaluation records' text before parsing (`records.strip_members`), so no per-draft value is ever decoded; the tests no longer parse the real frozen file either. P10-02 (Medium): AC02 got one final status, first **met** (useful detections beyond always-allow and the rules baseline within the budget; no recall floor), with the Phase 5 per-scenario reading kept in its measured text, 8 met, 2 insufficient evidence, 0 not met. **Superseded by WP-05 (2026-10-01):** AC02 is **insufficient evidence** because Phase 1 defines it as recall subject to AC01 and AC01 is insufficient evidence; the summary is 7 met, 3 insufficient evidence, 0 not met. P10-03 (Low, and the P9-03 remainder): printed commands use `SCRATCH="$(mktemp -d)"` and quoted paths, with a shell-aware test. P10-04 (Low): CI status recorded from the green run. The full `pytest` (593 s) is now at the 10-minute budget; the next added test should come with a `slow` marker or a speed-up.
- **First GitHub CI run (2026-10-01, run 36804007794, commit `89e593a`): failed.** Every step before the tests passed: the pinned install, `pip check`, the environment check, and both bundle checks. `pytest -m "not slow"` failed one test, `tests/test_phase3.py::test_published_artifact_matches_training_fit`: it compared fresh features with the published ones bit for bit, and on Linux one `content_cosine` value differs by about 3e-17 from the macOS fit. Reproducing CI in `python:3.11.14-slim-bookworm` containers found a second failure on x86_64, `tests/test_phase7.py::test_walkthrough_document_is_reproducible_from_the_api`: the walkthrough printed a live score at full precision (a 2e-16 difference). No decision or count changed. Fix `c2204c1`: feature floats are compared within 1e-12 (keys, integers, and flags exactly; CSV storage is still tested bit for bit), that score is printed to 7 decimals with the walkthrough regenerated from a running API (only that number changed), and the workflow pins `ubuntu-24.04` and uses `actions/checkout@v6` and `actions/setup-python@v6` (Node 24). The CI selection then passed 193 tests on macOS arm64, Linux arm64, and Linux x86_64 (emulated), and `med_deploy smoke --spawn` passed on both Linux architectures. On the merged `main` (Phase 10 plus the fix) it passed 216 on macOS and on Linux x86_64. **The rerun passed:** run 36811479847 (https://github.com/kyawmt/Misdirected_Email_Detection/actions/runs/36811479847), push of `50b82bd`, 2026-10-01 03:38:59 UTC, `ubuntu-24.04`, success on every step with no annotations. CI runs only the fast selection; the full release gate and `med_data validate` run locally.
- **Phase 9 limits (not verified).** At the time of the Phase 9 record, GitHub Actions had not executed `.github/workflows/ci.yml` (its steps ran in a clean copy with a fresh venv; GitHub has since run it, see the runs above); no Linux host was used (bind-mount permissions for uid 10001 are documented, not tested; Docker Desktop on macOS was the runtime); Windows is untested; the x86_64 check was one emulated image; the UI container is exercised through its health endpoint and one manual browser check, while the screen script itself is exercised headlessly on the host against the container API; nothing was pushed to a registry or hosted; there is no live hot swap, canary, or shadow router. The local demo stack was stopped at the end of the session (the images `med-api:phase9` and `med-ui:phase9` remain); `mkdir -p var/demo && docker compose up -d --wait` starts it again.
- **After Phase 10 (outside the project's scope):** representative reviewed labels and a real reviewer; an independent, more varied evaluation set (a new frozen dataset version) so AC01 can be supported or fail; prospective validation on real mail; mail integration with privacy controls and a decision on wider monitoring logs; correction logging; shadow, canary, and a live rollback switch; a hosted deployment; Linux and Windows hosts beyond CI's one Ubuntu runner; efforts to reduce the S01, S04, and S11 misses (each would be a new bundle needing a new frozen test). Phase 10 itself is complete. Every earlier review item (P5 to P10, RA, RB, RC) has a reply; the whole-project items WP-01 to WP-09 are answered in `comments.md` and described in the section below.
- **Phase 8 review (2026-09-30):** P8-01 (High) and P8-02/P8-03 (Medium) in `project_context/comments.md` were verified as addressed. The original review ran 30 focused tests in 22.68 s; the verification ran `.venv/bin/python -m pytest tests/test_phase8.py -q`: 32 passed in 22.39 s. `git diff --check` passed. The full suite was not rerun in the verification.
- **Phase 7 UI** shows the API's result and adds nothing: no reason codes, no scoring. It makes the S01, S04, and S11 misses visible; it does not reduce them. What Phase 8 should monitor: per-bundle assessment volume, `unable_to_assess` counts by category and message (unknown addresses in particular, since typos are `unavailable`), warning rate against the validation rate (8 of 4,000), email risk scores near `T_warn` (the legitimate first-contact margin is 2.3e-3), `LIMITED_RELATIONSHIP_HISTORY` and `LIMITED_TEXT` rates, API latency, and feedback volume and label mix (feedback on warned drafts only is biased; sampled allowed drafts need review too). Feedback lands in `var/feedback.jsonl` (gitignored); it is not a label until reviewed.
- **Phase 8 monitoring is a simulation.** No production traffic, real reviewer, or online experiment exists. Thresholds are conventions that no incident has tested. The stored records are aggregates; the API log allow-list was not widened. The metrics a deployment needs but the log cannot carry today (failure messages, evidence limitations, a near-cutoff flag, a score band) are a proposed privacy decision in `docs/phase_8/MONITORING.md`, not implemented.
- **What Phase 9 did with the Phase 8 handoff.** (1) A rollback between two loadable bundles still does not exist in one process; it is rehearsed as an image swap (known-good versus failing candidates), not as a live switch. (2) A shadow mode and a per-sender routing switch were not built; they remain future capabilities. (3) The UI still records no correction. (4) A sender-level A/B test still cannot run on this population. (5) The regression suite holds failure probes similar to the replay's; the eight-window replay itself stays a Phase 8 command (about two minutes). (6) Decided: split environments (see Phase 9 findings).
- **Latency alerts are timing-dependent** and are excluded from the deterministic alert set; the stored latency numbers describe one run on this machine.
- **`replay --api URL`** needs `httpx` (the `monitor`, `ui`, or `dev` extra). The in-process default needs it too, through the FastAPI test client.
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
