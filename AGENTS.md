# Agent instructions

Read this file before editing the repository. It states durable rules. Current progress lives in [PROJECT_STATUS.md](PROJECT_STATUS.md). Update that status when a session changes phase completion, artifacts, or verified results. Change this file only when a durable rule changes.

## Required reading

Read these before implementing a phase:

1. [PROJECT_STATUS.md](PROJECT_STATUS.md), so you do not redo finished work or ignore a frozen dataset.
2. The local plan at `project_context/PROJECT_PLAN.md`, including the research basis and the phase you were asked to do.
3. The job-description file in `project_context/`, for scope only.
4. The phase brief in `project_context/` when the user points you at one.
5. Public phase documents already written under `docs/phase_1/` and `docs/phase_2/`.
6. [README.md](README.md), for what a public reader is allowed to see.

Phase 1 documents define the product contract: scenarios, inputs and outputs, and acceptance criteria. Phase 2 documents define the dataset, labels, splits, and leakage rules. Later phases must follow those contracts.

## Phase boundaries

Work only on the phase the user requested. Phases are dependency order, not permission to continue into the next one.

| Phase | Stop when |
| --- | --- |
| 1 | Product brief, scenarios, input/output contract, and acceptance criteria exist. |
| 2 | Fictional data, labels, chronological splits, leakage checks, and the frozen test subsets exist. |
| 3 | Shared behavioral and text features, with history strictly before each draft. |
| 4 | Baselines and a small set of recorded model comparisons. |
| 5 | Evaluation, calibration only if needed, and a versioned threshold policy. |
| 6 | Scoring API and explicit failure behavior. |
| 7 | Simulated draft-review UI. |
| 8 | Monitoring, reviewed feedback, and rollback notes. |
| 9 | Repeatable tests, packaging, and deployment checks. |
| 10 | Public architecture, results, model card, and usage guide. |

Do not start feature engineering, model training, threshold selection, API, or UI work while a data-phase task is open. Do not tune features, models, or thresholds on `test_product_like` or `test_diagnostic`.

Dataset identity is `med-synth-v2`, generator `1.1.0`, seed `20260926`. Bump `DATASET_VERSION` when the seed, quotas, or generation rules change, and treat the new test subsets as the frozen sets. Do not silently rewrite a version whose test set has already been used for evaluation.

## Research rules

Use the papers already cited in the README and the plan as sources of techniques, not as performance claims for this system.

- A label is whether the sender intended the recipient. Novelty, an external domain, a topic change, a lookalike name, or a Bcc role does not set the label.
- Report this project's metrics on its own splits, with sample counts. Diagnostic-set rates are not product-like prevalence results.
- Product-like prevalence is a simulation assumption of 0.5%. The training subset is enriched to 10% and is not an operating point.
- Paper results, especially injected-recipient ranking scores, do not transfer to the warning budget.
- Keep methods interpretable: rules, logistic regression, and one small tree model are the planned comparison. Do not add deep learning or an external LLM dependency unless the user asks.
- Scores are risk scores until calibration evidence says otherwise. Blocking stays disabled until a separate evaluation justifies it.
- A scoring failure is `unable_to_assess`, never an automatic allow.
- All people, addresses, and messages stay fictional and on reserved `.example` domains. Do not ingest real mail.

## Leakage rules

History for a draft is sent mail with `sent_at` strictly earlier than the draft. Also drop the draft's `family_id` and any earlier copy of its non-empty body. Empty bodies may repeat.

Model inputs come from `scoring_view` or the same allow-list. Do not feed the model scenario ids, variants, generator topics, withheld contacts, counterfactual flags, family ids, splits, subsets, labels, stipulations, feedback, or fixture reasons. `split` is unsafe because train prevalence differs from product-like prevalence.

Keep corrupted variants and clean twins of one source in the same family, split, and subset. Later metrics must cluster on `family_id`. Product-like families contain one draft.

Fit vocabularies and other learned preprocessing only on training data. Use one feature specification for later training and serving.

Template sentences repeat on purpose. Exact bodies include a unique reference token. Do not treat a shared template phrase as proof of a copied thread, and do not claim the hash check removes shortcut risk from repeated wording.

## Testing

From the repository root, with Python 3.11 or newer:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m med_data validate --data data/med-synth-v2
```

Rebuild only when generation rules change, then validate the new version:

```bash
python -m med_data build --output data/med-synth-v2
```

Install from the pinned versions with `pip install -c constraints.txt -e ".[dev,ui,monitor]"` (Python 3.11.14 is the tested interpreter). The full `pytest` is the release gate. CI and quick iteration use `pytest -m "not slow"`, which deselects the tests marked `slow` and stays under about three minutes.

**Never run `python -m med_features build` or `python -m med_models run` with their default paths.** They overwrite the published `artifacts/med-features-v2` and `artifacts/med-model-v2` without refusing, `med_models run` also rewrites `docs/phase_4`, and the frozen test subsets of `med-synth-v4` have been evaluated once. A rebuild demonstration sends every output to a scratch directory (`python -m med_deploy rebuild-demo` does this and compares the result with the published files). Image builds and CI never fit, retrain, select a cutoff, or evaluate the frozen subsets.

Record the command, the pass count, and the date in `PROJECT_STATUS.md`. Do not report a check as passed unless you ran it in that session or you are quoting a result already written there.

`pytest` rebuilds the dataset in memory and compares it to the published files. `validate` checks checksums, parsed CSV record counts, and the quality checks. Quoted newlines inside a body are one record.

Documents generated from stored records are never edited by hand. They are `docs/RESULTS.md` and the blocks between `<!-- med-docs:begin NAME -->` and `<!-- med-docs:end NAME -->` markers in `README.md`, `docs/ARCHITECTURE.md`, `docs/MODEL_CARD.md`, `docs/DEMO_WALKTHROUGH.md`, and `docs/LIMITATIONS_AND_FUTURE_WORK.md`. Regenerate them with `python -m med_docs report`; `python -m med_docs check` fails when one is stale. A number in a public Phase 10 document comes from a stored record through that generator, or the document links to a generated page that states it. `src/med_docs/` uses the standard library only. It reads `test_evaluation.json` through the allow-list of aggregate key paths in `med_docs.version`, discarding the per-draft `outcomes` while the file is parsed. Do not widen that allow-list, do not read `outcomes`, and do not use `med_policy.report.stored_results` or `_context`, which load the whole file.

## Private context

`project_context/` is local and gitignored. Read it. Do not quote it into public files.

Public files are `README.md`, `docs/`, source code, tests, and files under `data/`. In those files, do not name the employer, the role, an interview, the job description, or the `project_context/` directory. Public research citations that are already in the README may stay. Phase documents may point at `docs/` paths only.

`AGENTS.md` and `PROJECT_STATUS.md` may name `project_context/` so the next session can find the plan. They still must not copy the job description or describe the work as an interview exercise.

## Coordination

- Start from `PROJECT_STATUS.md`. If it names active work and an owner, continue that work. Do not open a second implementation of the same phase.
- If the owner is another session and files for that work already exist, read them before editing.
- Leave status as unassigned when no implementation is in progress.
- At the end of a session that changes artifacts, tests, or the next phase, update `PROJECT_STATUS.md` with what was verified.
- Keep edits inside the requested phase. Ask only when the next action would cross a phase boundary or change the frozen test policy.
