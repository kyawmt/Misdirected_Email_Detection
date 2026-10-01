# Documentation index

Every public document, by audience. Phase documents stay where they were written, in `docs/phase_*/`; this page is how to find them. Start with the [README](../README.md) for the problem, the quick start, and the headline results.

All data is fictional and every result is from a simulation. Scores are risk scores, not probabilities.

## Start here

| Document | Purpose |
| --- | --- |
| [README](../README.md) | What the demo is and is not, a quick start, the architecture in brief, headline results with their limits |
| [Results](RESULTS.md) | Every result with its denominator, the per-scenario outcomes, latency, the final acceptance table, and what is demonstrated versus assumed. Generated from stored records |
| [Model card](MODEL_CARD.md) | Intended use, inputs, training and evaluation data, the operating point, failure modes, fairness and privacy notes, versions, and technique labels |
| [Architecture](ARCHITECTURE.md) | One diagram of the real system, the batch and request paths, versioned artifacts, the leakage boundary, parity, and the failure model |
| [Usage guide](USAGE_GUIDE.md) | Install from the pins, start the demo, use the screen, run the checks, rehearse a rollback, and troubleshoot |
| [Demo walkthrough](DEMO_WALKTHROUGH.md) | A short spoken demonstration in six steps, with the honest limit of each |
| [Limitations and future work](LIMITATIONS_AND_FUTURE_WORK.md) | What the project does not show, and the evidence each next step would produce |

## Product

| Document | Purpose |
| --- | --- |
| [Product brief](phase_1/PRODUCT_BRIEF.md) | The problem, the user, the scope, and the decisions |
| [Scenarios](phase_1/SCENARIOS.md) | The scenarios, with the desired behavior of each |
| [Input and output specification](phase_1/INPUT_OUTPUT_SPECIFICATION.md) | The product contract: inputs, outputs, decisions, and failure outcomes |
| [Acceptance criteria](phase_1/ACCEPTANCE_CRITERIA.md) | The measurable requirements; their final statuses are in [results](RESULTS.md#5-acceptance-criteria) |
| [UI guide](phase_7/UI_GUIDE.md) | The simulated draft-review screen |
| [Walkthrough](phase_7/WALKTHROUGH.md) | Each step with the desired outcome beside the measured one, generated from the live API |

## Data

| Document | Purpose |
| --- | --- |
| [Data dictionary](phase_2/DATA_DICTIONARY.md) | Every table and column |
| [Labeling guide](phase_2/LABELING_GUIDE.md) | What a label means and how stipulated labels are assigned |
| [Dataset specification](phase_2/DATASET_SPECIFICATION.md) | Splits, subsets, quotas, and the frozen test policy |
| [Data quality and leakage checklist](phase_2/DATA_QUALITY_AND_LEAKAGE.md) | The executable checks and the leakage rules |

## Modeling

| Document | Purpose |
| --- | --- |
| [Feature catalog](phase_3/FEATURE_CATALOG.md) | Every feature, its definition, and its availability rule |
| [Profile and transform contract](phase_3/PROFILE_AND_TRANSFORM.md) | How history is looked up and how training and serving share one row builder |
| [Feature quality report](phase_3/FEATURE_QUALITY_REPORT.md) | Signal distributions and the shortcut checks |
| [Training and serving parity](phase_3/TRAINING_SERVING_PARITY.md) | The checks that keep the two paths equal |
| [Experiment table](phase_4/EXPERIMENT_TABLE.md) | Every recorded run, with intervals |
| [Comparison](phase_4/COMPARISON.md) | The baselines and the learned models side by side |
| [Ablations](phase_4/ABLATIONS.md) | What each feature group adds |
| [Model artifact](phase_4/MODEL_ARTIFACT.md) | What the stored model holds and how it is checked |
| [Decision record](phase_4/DECISION_RECORD.md) | The selection rule and why this model |
| [Evaluation report](phase_5/EVALUATION_REPORT.md) | The frozen policy on four subsets, with intervals |
| [Threshold policy](phase_5/THRESHOLD_POLICY.md) | How the one cutoff was chosen, and its load checks |
| [Error analysis](phase_5/ERROR_ANALYSIS.md) | Examples of allowed, warned, and missed emails |
| [Uncertainty and prevalence](phase_5/UNCERTAINTY_AND_PREVALENCE.md) | Interval methods, the independence limit, and prevalence sensitivity |
| [Phase 5 model card](phase_5/MODEL_CARD.md) | The card written at evaluation time, kept as the historical record; the current entry point is the [model card](MODEL_CARD.md) |

## Operations

| Document | Purpose |
| --- | --- |
| [API contract](phase_6/API_CONTRACT.md) | Endpoints, requests, responses, and codes |
| [Scoring flow](phase_6/SCORING_FLOW.md) | Startup and request handling, and the Phase 6 latency record |
| [Error behavior](phase_6/ERROR_BEHAVIOR.md) | The two failure categories and what never happens |
| [Monitoring](phase_8/MONITORING.md) | Metrics, references, minimum samples, and alert rules |
| [Drift replay](phase_8/DRIFT_REPLAY.md) | One replayed shift, followed from alert to investigation |
| [Feedback review](phase_8/FEEDBACK_REVIEW.md) | The reviewed-label workflow and what the simulated review shows |
| [A/B test proposal](phase_8/EXPERIMENT_PROPOSAL.md) | A sender-level experiment, with its primary outcome and preconditions |
| [Runbook](phase_8/RUNBOOK.md) | Rollout, rollback, incident triage, and promotion gates |
| [Test report](phase_9/TEST_REPORT.md) | The checks that were run, the scenario regression, and latency |
| [Reproducibility](phase_9/REPRODUCIBILITY.md) | Pins, fresh installs, and a rebuild into scratch |
| [Local deployment](phase_9/LOCAL_DEPLOYMENT.md) | The two containers, what each reads, and feedback retention |
| [Rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md) | A known-good image swapped for failing candidates |

## How the generated pages are kept honest

[Results](RESULTS.md), the generated blocks of the [model card](MODEL_CARD.md), the [architecture](ARCHITECTURE.md), the [demo walkthrough](DEMO_WALKTHROUGH.md), the [limitations](LIMITATIONS_AND_FUTURE_WORK.md), and the headline in the [README](../README.md) are written by `python -m med_docs report` from stored records. `python -m med_docs check` fails if any of them differs from the records, and the generator reads only aggregate fields of the frozen test record.
