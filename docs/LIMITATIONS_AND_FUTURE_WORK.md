# Limitations and future work

What this project does not show, why that matters, and what evidence would change it. This page collects the limits in one place; each one is also stated where it applies. Figures behind them are generated from stored records in the block below and in [results](RESULTS.md), and the prose states none.

## What this project does not claim

- That detection improved. The monitoring and deployment phases changed no model, feature, policy, cutoff, dataset, or contract.
- Real-world accuracy, a production-ready system, or a hosted service. It is a local simulation on fictional mail.
- A confidence-supported warning budget. The zero false warnings on the frozen test pass are a descriptive result on this corpus.
- That a score is a probability. Scores are uncalibrated risk scores.
- That blocking is justified. Blocking is disabled and stays disabled.

## Limitations

### Synthetic data

Every person, address, and message is fictional, on reserved `.example` domains, and every label is a stipulation written by the generator, not a judgment by a reviewer. Results show behavior under the generator's assumptions, not accuracy on real mail. Template wording repeats across time, so a shared phrase is not proof of a copied thread, and the exact-copy hash check does not remove shortcut risk from repeated wording. Product-like prevalence is a simulation assumption, and the training mix is enriched. See the [dataset specification](phase_2/DATASET_SPECIFICATION.md) and the [leakage checklist](phase_2/DATA_QUALITY_AND_LEAKAGE.md).

### AC01 independence

The interruption budget is **insufficient evidence**. Zero false warnings on the frozen product-like test pass give a small exact upper bound, but that bound assumes independent emails, and they are not shown to be independent: most test drafts come from one sender and routine drafts repeat generated patterns. One draft per family removes thread copies and does not establish independence, and a sender-clustered interval has no upper bound for a zero count. The validation bound is not evidence either, because validation chose the cutoff. See [uncertainty and prevalence](phase_5/UNCERTAINTY_AND_PREVALENCE.md#independence). A supported claim needs an independence argument or a more independent evaluation, which needs a new frozen dataset version.

### The S01, S04, and S11 misses

Lookalike replacements (S01), familiar-recipient topic mistakes (S04), and mistaken first contacts (S11) were allowed on every subset. Legitimate first contacts score just below the cutoff, so any cutoff low enough to warn on these mistakes warned on legitimate validation mail. The review screen and the scenario regression keep these misses visible; neither reduces them. See the [error analysis](phase_5/ERROR_ANALYSIS.md).

### Content cosine is a strong signal

Content similarity separates training mistakes from ordinary mail well inside the audit bounds but not far inside them, and the off-topic scenarios (S02, S04) are low on it by how they were written. The all-features model passed three recorded train-only checks before selection, and a model without content features is much weaker on validation. A model that leans on content could be learning how this generator writes mistakes. See the [feature quality report](phase_3/FEATURE_QUALITY_REPORT.md) and the [decision record](phase_4/DECISION_RECORD.md).

### Scores are uncalibrated

`calibration: not_fit`. The validation subset has too few mistakes to split into a calibration portion and a selection portion. Scores rank risk. No warning level, "risk percentage", or probability should be read from them. A reliability table on the diagnostic subset is a shape check only.

### One machine

Latency, the container checks, and the rollback rehearsal ran on one machine with one container runtime. The boundaries of the latency measurements differ, and a four-client probe exceeded the target. A second CPU architecture was checked once, emulated, and timing under emulation is not meaningful. Capacity planning is out of scope.

### CI on GitHub

The workflow file is checked by a test that it contains the same steps as the local clean-copy run, and those steps passed in a fresh virtual environment on macOS. CI then ran once on GitHub, on 2026-10-01, and failed: one test compared freshly computed features with the published ones bit for bit, and on Linux one `content_cosine` value differs in its 17th significant digit (about 3e-17) from the value computed on macOS, where the artifact was fitted. Reproducing CI in Linux containers found a second sentence, in the generated Phase 7 walkthrough, that printed a live score at full precision (a 2e-16 difference on x86_64). No decision or count changed. The fix compares feature floats within 1e-12 (the CSV storage is still tested bit for bit) and prints that score to seven decimals. With it, the CI test selection passes on macOS arm64, Linux arm64, and Linux x86_64 (emulated) in a `python:3.11.14-slim-bookworm` container. The fix was pushed, and the next run, [run 36811479847](https://github.com/kyawmt/Misdirected_Email_Detection/actions/runs/36811479847) on commit `50b82bd` (2026-10-01, `ubuntu-24.04`), passed every step: the pinned install, the dependency and environment checks, both bundle checks, the fast test selection, and the end-to-end smoke run. CI runs only the fast selection (`pytest -m "not slow"`); the full release gate and `med_data validate` run locally, not on GitHub, and the container image builds and the rollback rehearsal are not part of CI.

### Linux and Windows are untested

No Linux host and no Windows host was used. The container user must be able to write the feedback folder, which on Linux is a documented step and not a tested one. Docker Desktop on macOS was the only container runtime.

### Unknown addresses are not assessed

A well-formed address that is not in the directory snapshot, such as a typo, returns `unable_to_assess` and is not a warning. That is the product contract, and a user-visible burden: the sender sees "unavailable" for a mistake the policy never judged. Changing it is a contract decision, not a model change.

### Feedback has never been reviewed by real people

Feedback is a stored click. No reviewed label exists for the monitored traffic, the reviewer rows in the dataset are illustrative and none was accepted, and the review in the monitoring replay is a simulated reviewer that returns the stipulated label after a seeded delay and is always right. Confirmed performance cannot be stated, and any efficacy figure from the simulated review describes the simulation.

### Other limits

- **Few positives.** The product-like subsets hold few misdirected emails, so recall intervals are wide and per-scenario counts are small.
- **A thin margin.** The cutoff sits just above the highest legitimate validation score. A drift in legitimate scores, or a new kind of legitimate first contact, adds false warnings. The drift replay shows near-cutoff scores rising under a first-contact wave.
- **Monitoring is a simulation.** Its thresholds are conventions no real incident has tested. Several lifetime-count inputs leave the training range as time passes, and the monitor reports them as structural and cannot say when that starts to matter.
- **Weak regularization.** The selected constant is at the top of its grid, and coefficients on overlapping counts are not separate effects.
- **One organization, English plain text.** No attachments, distribution lists, aliases, other languages, or changing directories.
- **A rollback is an image swap.** There is no live switch between two bundles, no shadow mode, and no canary.
- **A concurrency limit.** One API process queues requests when several clients send at once; the latency target applies to one request in flight.

## The evidence behind these limits

<!-- med-docs:begin limit_evidence -->
Scenarios never warned on, by subset (warned mistakes / all mistakes of the scenario):

| Scenario | Story | `validation_product_like` | `validation_diagnostic` | `test_product_like` | `test_diagnostic` |
| --- | --- | --- | --- | --- | --- |
| **S01** | Lookalike replacement | 0 / 4 | 0 / 10 | 0 / 6 | 0 / 11 |
| **S04** | Familiar recipient, unusual topic | 0 / 4 | 0 / 10 | 0 / 5 | 0 / 11 |
| **S11** | Mistaken first contact | 0 / 2 | 0 / 10 | 0 / 3 | 0 / 11 |

- **Margin.** Highest legitimate validation email 0.9973707; `T_warn` 0.9996767; gap 2.31e-03.
- **Content.** Train separation of content cosine 0.932; selected run AP 0.831 against 0.494 for the best behavior-only logistic run, on 20 positive emails.
- **Prevalence and positives.** Product-like prevalence 0.5% (assumed); 20 and 30 misdirected emails in the validation and test product-like subsets.
- **Reviewed labels.** 0 reviewed labels exist for the monitored traffic; the replay's review is `simulated reviewer: the stipulated label of each queued validation draft, returned after a seeded delay`.
- **Machine.** macOS-27.0-arm64-arm-64bit, 10 CPUs; containers on Docker Desktop. A second architecture (linux/amd64, emulated) passed 20 of 20 fixtures.
- **Not verified when the Phase 9 record was written.** GitHub Actions itself: the workflow file was not executed by a GitHub runner from this machine. Later status: [CI on GitHub](#ci-on-github).
<!-- med-docs:end limit_evidence -->

## Realistic next steps

Each step names the evidence it would produce. None is started, and none can be claimed from this repository.

| Next step | Why it matters | Evidence it would produce |
| --- | --- | --- |
| Representative reviewed labels | Labels are stipulations today, and feedback is not reviewed | Agreement between reviewer judgments and the generator's stipulations; recall and false-warning rates against reviewed labels with label coverage and delay; enough confirmed mistakes to state performance change and to consider calibration |
| An independent and more varied evaluation set, as a new frozen dataset version | Independence is not established, and few senders and few positives limit every interval | An interval for the interruption budget that can be supported or can fail; per-sender and per-scenario slices with usable counts; one frozen test pass for any new policy version |
| Reducing the known misses | Three scenario families are never warned on | Higher recall at the same or a justified budget on a fresh frozen set, with no new false warnings on legitimate first contacts; a group-topic profile (R2) and windowed or rate features are candidates, each needing a measured gain over the current bundle |
| Broader organizations and languages | One organization and English text | Results by organization, naming convention, and language; whether name, address, and text features transfer; fairness slices where attributes exist |
| Real mail integration with privacy controls | The demo reads only fictional mail | Behavior with real addresses, aliases, and distribution lists; latency in a real mail flow; a recorded data-protection review with access, retention, and notice decisions |
| A privacy decision on wider monitoring logs | Several monitors need fields the log does not carry | A recorded decision on which integer and enum fields (a score band, a near-cutoff flag, counts of limited history and limited text, a failure-message code) the log may carry; live monitors that need no addresses, names, subjects, or bodies |
| Shadow, then canary rollout | There is no way to score without showing, and no staged exposure | Agreement between a shadowed candidate and the served bundle on identical traffic; canary guardrails holding for a stated horizon; correction logging, which the proposed sender-level test needs as a precondition |
| Prospective validation | Everything here is retrospective on generated data | Reviewed performance on later, unseen mail over time, and whether the offline results predicted it |
| Run the workflow on GitHub and on Linux and Windows hosts | One machine and one runtime were used | A recorded CI run; a Linux container run with the feedback-folder step tested; a Windows install check |

## Related documents

[Results](RESULTS.md) · [model card](MODEL_CARD.md) · [architecture](ARCHITECTURE.md) · [monitoring](phase_8/MONITORING.md) · [A/B test proposal](phase_8/EXPERIMENT_PROPOSAL.md) · [test report](phase_9/TEST_REPORT.md) · [documentation index](README.md)
