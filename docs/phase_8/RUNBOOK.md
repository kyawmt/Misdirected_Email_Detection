# Phase 8 — Runbook: rollout, rollback, and incident triage

Served bundle: contract `med-api-v1`, snapshot `med-synth-v4`, features `med-features-v2`, model `med-model-v2`, policy `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled. This runbook describes how a frozen, versioned bundle would be shadowed, canaried, rolled back, and investigated. It is a document, not deployment tooling: there is no live switch between two bundles, no shadow mode, and no canary. Phase 9 later added local containers, a CI workflow, and a rollback rehearsed as an image swap ([rollback rehearsal](../phase_9/ROLLBACK_REHEARSAL.md)); the rollback steps below are the ones it rehearsed. All data is fictional. Monitored requests are `validation_product_like` drafts, plus copies of legitimate first-contact validation drafts in the shifted windows. No monitor command opens a file that holds frozen test results or a frozen feature matrix (`test_evaluation.json` and `features_test_*` are never read), and no frozen draft is scored, replayed, or summarized. The draft-keyed tables (drafts, recipients, labels, reviewer notes) are streamed record by record and only validation records are kept; the CSV parser still reads past each frozen record to find the next record boundary, because a quoted body can hold newlines, and drops it at once.

## The unit of change is a frozen bundle

A bundle is the dataset snapshot, the feature artifact, the model, and the policy, each with a version and a checksum, loaded together and never edited in place.

| Part | Version | Checksum (SHA-256) |
| --- | --- | --- |
| Model | `med-model-v2` (`logistic_all_balanced`) | `f698b69f7ff20fc9df9068ff06c1be44c9c6bc8ee6ce8cfacea851dbd7f9dfaa` |
| Feature artifact manifest | `med-features-v2` | `b9ef336f22952042cb64c61b6080a2040bec9b232848f93729b645e2e4d5fff9` |
| Policy | `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled | recorded inside the policy file |
| Snapshot | `med-synth-v4` | verified against the dataset manifest at startup |

A change to any part is a new bundle with a new version, evaluated offline first. The cutoff is never moved inside a version.

## What the service does today with a bad bundle

Each case builds the real API on altered copies of the frozen files in a temporary directory, then calls `/health`, `/ready`, and `/assess` (`python -m med_monitor bundle-checks`). The frozen files are never edited.

| Case | Change | `/health` | `/ready` | `/assess` | Decision, score | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| `control_unchanged` | The frozen bundle, untouched. | 200 | 200 | 200 assessed | allow, score reported | served |
| `policy_names_another_policy_version` | policy.json says med-policy-v1. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `policy_names_another_model_run` | policy.json names a different model run. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `policy_model_checksum_mismatch` | policy.json records a different model checksum. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `model_file_corrupted` | One byte of model.joblib is flipped. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `policy_enables_blocking` | policy.json sets blocking_enabled to true. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `policy_cutoff_not_a_number` | policy.json sets T_warn to text. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `policy_file_missing` | policy.json does not exist. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `feature_artifact_tampered` | One byte of features_train.csv is flipped. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |
| `previous_bundle` | The previous bundle on disk: med-policy-v1, med-model-v1, med-features-v1. | 200 | 503 | 503 unavailable | none, none | refused: unavailable, no decision, no score |

Every altered bundle was refused: the process stays up, `/ready` reports 503 with the reason, and `/assess` returns `unavailable` with no decision and no score, so a broken bundle can never produce an allow. The refusal reasons the service reported:

- `policy_names_another_policy_version`: PolicyError: Policy version med-policy-v1 does not match med-policy-v2
- `policy_names_another_model_run`: PolicyError: Policy names a different model run
- `policy_model_checksum_mismatch`: PolicyError: Checksum mismatch for model.joblib
- `model_file_corrupted`: PolicyError: Checksum mismatch for model.joblib
- `policy_enables_blocking`: PolicyError: Blocking must be disabled with T_block null in this policy version
- `policy_cutoff_not_a_number`: PolicyError: T_warn must be a finite number
- `policy_file_missing`: PolicyError: Policy file <tmp>/missing.json does not exist
- `feature_artifact_tampered`: ModelError: Checksum mismatch for features_train.csv
- `previous_bundle`: ModelError: Feature artifact is med-features-v1, expected med-features-v2

**Not covered:** A live switch between two loadable bundles. The service loads one bundle version and refuses every other, including the previous one. The previous bundle is refused by design (case `previous_bundle`), so today's code cannot roll back to it. A rollback needs the previous code and the previous bundle as a pair, which is what packaging is for.

## Rollout

A new bundle moves through these stages. Each stage has an exit rule that is written before the stage starts.

1. **Offline gates (before any traffic).** The bundle passes the offline checks in the promotion gates below, on a validation set separate from the one that chose its cutoff, with one test pass on a new frozen dataset version.
2. **Shadow.** The candidate scores the same requests as the served bundle and its decisions are logged, not shown. Compare decisions, the warning rate, the near-band share, and latency against the served bundle on identical traffic. Exit: agreement on the rules in [monitoring](MONITORING.md), no critical or high alert, and reviewed samples from the stratified queue.
3. **Canary.** A small set of senders, chosen by a seeded draw, sees the candidate's warnings. Everyone else keeps the served bundle. Exit: the guardrails in [the experiment proposal](EXPERIMENT_PROPOSAL.md) hold for the planned horizon.
4. **Full rollout.** Only after the canary exits cleanly and a named reviewer signs the promotion record. The previous bundle stays deployable until the next bundle has run clean for a stated period.

## Rollback

**Roll back when** any critical alert fires, a guardrail is breached, a high-impact incident (below) is confirmed, or `/ready` no longer reports the expected versions.

1. Stop routing new senders to the candidate. Keep the record of what it did.
2. Restore the previous bundle: the previous code revision and the previous frozen bundle files together, pointed to by the service's path settings (`MED_API_POLICY`, `MED_API_MODEL`, `MED_API_FEATURES`, `MED_API_DATA`). Do not edit files in place.
3. Confirm with `GET /ready` (versions and `T_warn` must match the previous policy file) and re-run the failure probes.
4. Confirm the monitor: served versions match, no block decisions, unable-to-assess back to the reference.
5. Write the incident record: trigger, time, bundle versions, counts, decision, and the offline check that must pass before the candidate returns.

**Capabilities this needs that do not exist:** a way to hold two bundles loadable at once, a per-sender routing switch, and a shadow mode that records without showing. None was built. A rollback to a known-good image was rehearsed later, in Phase 9, as an image swap ([rollback rehearsal](../phase_9/ROLLBACK_REHEARSAL.md)).

## Alert reference

| Signal | Rule | Severity |
| --- | --- | --- |
| Any block decision | count above 0 | critical |
| Any response that breaks a contract invariant | for example a failure body with a decision or score | critical |
| A response naming a bundle other than the frozen one | any | critical |
| A failure with no version provenance (the service answered without a loaded bundle) | any | high |
| Unexpected (non-contract) responses | any | high |
| Unable-to-assess rate above the reference | one-sided exact test, alpha 0.01, at least 200 requests | high |
| Input drift | PSI alert 0.25; indicator share shift 0.1 | high |
| Emails in the near band | one-sided exact test, alpha 0.01, at least 500 assessed emails | medium |
| Client p95 latency | above 300 ms or 2 times the reference p95 | medium |

## Incident triage

Warnings are advisory and blocking is disabled, so the worst automatic outcome is an unnecessary interruption or a missed mistake. A failure is `unable_to_assess`, never an allow. In every incident: preserve the evidence first, change nothing in the frozen bundle, and never move `T_warn` to make a symptom go away.

### A high-impact false positive

**Signal.** A sender or a support contact reports a warning that stopped important, legitimate mail. Or the warning rate, the flagged-recipient count, or a confirmed false intervention rises.

1. **Contain.** Do not change the cutoff. If a shadow mode exists, move the affected senders to it. Otherwise record the affected window and the count.
2. **Capture** the request id, the bundle versions, and the reason codes the service returned. Do not copy the body, subject, or addresses out of the affected mailbox.
3. **Classify.** Was the warning correct on the evidence (a real mistake the sender then confirmed), or a false intervention? A reviewer, not a click, decides.
4. **Locate.** Compare the email risk score with `T_warn` (the margin is small: the highest legitimate validation score sits 2.31e-03 below it). Check the input-drift and near-band findings for the same period, and whether the recipient is a first contact.
5. **Offline check.** Reproduce the assessment from the request. If it reproduces, the cause is the policy on this input; go to the promotion gates. If it does not, treat it as a service defect and check parity.
6. **Decide** with a reviewer. A confirmed false intervention counts against the budget. It is a reason to open a new policy version, not to move the cutoff in place.


### Rising false negatives

**Signal.** Reviewed samples of allowed emails show more mistakes than before, or a reported mistake was allowed. Remember the policy already misses lookalike replacements (S01), familiar-recipient topic mistakes (S04), and mistaken first contacts (S11) by design of its cutoff.

1. **Confirm with labels.** Only the stratified review of allowed emails can show a rise. Check the number of confirmed misdirected emails first: a performance statement needs 30 on each side, and until then the honest report is that there is not enough evidence.
2. **Separate the cause.** Input drift (did the mix change, for example toward first contacts), decision-rate change (did the warning rate move), and confirmed performance change are three findings; report each.
3. **Slice.** Which scenario-like slice do the misses fall in: added recipient, lookalike, topic mismatch, first contact? Compare with the recorded per-scenario results.
4. **Do not lower the cutoff.** Any lower cutoff produced false warnings on validation. A lower cutoff is a new policy version with its own budget evidence.
5. **Offline check and review** as in the promotion gates. Record the finding even if nothing is promoted.


### A scoring outage

**Signal.** `/ready` returns 503, the bundle-availability or unable-to-assess alert fires, latency exceeds the target, or the timeout message appears.

1. **Read the category.** `unavailable` with "The scoring bundle is not loaded" means startup failed; `/ready` gives the reason (a version or checksum mismatch, a missing file). "Scoring timed out" means the 2-second scoring timeout fired. "A recipient is not in the context snapshot directory" is one address, not an outage.
2. **Nothing fails open.** A failure returns unable to assess with no decision and no score. Clients must show it as unable to assess, never as allow.
3. **Restore.** Fix the bundle path or files, or restore the previous bundle as in the rollback steps, and re-check `/ready`.
4. **Verify.** Re-run the failure probes and a small replay; confirm the served versions and that unable-to-assess is back to the reference.
5. **Follow up.** Record the duration and the count of requests that were unable to assess. Those requests were not assessed, and that burden belongs in the incident record.


## Promotion gates

No model, feature, or policy change is promoted on monitoring evidence alone. Every promotion needs all of:

1. **A new version.** New model, feature, or policy versions get new artifact directories; nothing is edited in place.
2. **An offline evaluation on data that did not choose the change.** Validation for selection, a separate portion for any calibration, and one pass on a new frozen test set. Report counts, denominators, and intervals.
3. **The interruption budget.** False interventions per 1,000 legitimate emails against the budget, with the independence caveat recorded (AC01 is insufficient evidence today).
4. **Parity.** The batch path and the single-draft path give identical decisions on every selection draft.
5. **Failure behavior.** Every bundle mismatch case above is still refused, and no failure returns a decision or score.
6. **Review.** A second person reads the evidence and signs the promotion record.
7. **Staged exposure.** Shadow, then canary, with the exit rules above.

A reviewed label, a click, or a monitoring alert can start this process. None of them can finish it.
