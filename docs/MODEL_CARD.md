# Model card

The entry point for the misdirected-email risk scorer (`med-model-v2`) and its warning policy (`med-policy-v2`). It supersedes [the Phase 5 model card](phase_5/MODEL_CARD.md) as the place to start, and does not rewrite it: that card stays as the record written when the policy was evaluated.

The tables in this card are generated from stored records by `python -m med_docs report`, the same generator as [results](RESULTS.md), and the prose around them states no number. Scores are uncalibrated risk scores, not probabilities. Everything here describes a simulation on synthetic data.

## Intended use

- Rank the recipients of a **fictional** draft email by risk score of being unintended and, when the highest recipient score reaches the frozen cutoff, ask the sender to review the flagged recipients before a **simulated** send.
- Show an applied machine-learning workflow to engineers and product reviewers: how signals are combined, how a cutoff trades interruptions against detections, how an evaluation is kept honest, and how a service fails safely.
- Read every decision as advisory. A warning asks the sender to check addresses and is not proof of a mistake. An allow is not a check that every recipient is correct.

## Out-of-scope use

- Real mail, real senders, or any statement about real-world accuracy. The data is synthetic and the labels are stipulated.
- Any automatic action. Blocking is disabled, and the evidence here does not justify enabling it.
- Reading a score as a probability, or a warning budget as confidence-supported. Calibration was not fit.
- A different mix of mail. Product-like prevalence is a simulation assumption, and precision depends on prevalence.
- Other organizations, other languages, attachments, distribution lists, aliases that need directory expansion, or a directory that changes over time.
- Judging a sender's intent, or monitoring individuals.

## Model and inputs

The scorer is one logistic regression on standardized features, one row per addressed recipient. The email's risk score is the maximum over its unique recipients, and a recipient is flagged when its own score reaches the cutoff. Role (To, Cc, or Bcc) is not a feature.

The inputs are computed only from mail sent strictly before the draft. When the training and evaluation rows are built offline, the draft's family and any earlier copy of its body are also dropped. The service has no family for a client's draft, so it drops only an earlier copy of the draft's own body:

- **Relationship:** how often the sender wrote to the recipient and the recipient's domain, how often the recipient wrote back, how recently, over the lifetime and over a fixed recent window, and whether the recipient is internal.
- **Recipient group:** how much earlier mail supports this set of addressees together.
- **Contact similarity:** name and address similarity to other contacts visible in the directory.
- **Content:** cosine similarity between the draft and the earlier mail with that recipient, from a TF-IDF vectorizer fit once on mail from before the validation window, plus flags for empty, short, or out-of-vocabulary draft text.
- **Missing history is explicit.** An indicator says when a relationship, recency, text comparison, or sender history is unobserved, and a fixed fallback fills the value. No history is not forced to look safe or risky.

The model never receives scenario ids, variants, generator topics, withheld contacts, counterfactual flags, family ids, splits, subsets, labels, stipulations, feedback, or fixture reasons. The [feature catalog](phase_3/FEATURE_CATALOG.md) defines every input.

<!-- med-docs:begin card_model -->
| Item | Value |
| --- | --- |
| Estimator | logistic regression, one linear model on standardized features |
| Run | `logistic_all_balanced` (`all` features) |
| Input features | 34 per recipient row |
| Regularization | `C = 1000`, class weight `balanced` |
| Output | `risk_scores`: one score per recipient; the email score is the maximum over unique recipients |
| Calibration | `not_fit`; thresholds `not_selected` in the model, set by the policy |
| No history | unobserved recency is replaced by the training median of observed recency (0.234375 days, 337.5 minutes) and then log-transformed, with an indicator that the value was missing |
| Libraries | scikit-learn 1.9.1, NumPy 2.4.6 |
<!-- med-docs:end card_model -->

## Training data

<!-- med-docs:begin card_training -->
- **Training subset** `train`: 3,000 emails, 300 misdirected (10.0%, enriched; not an operating point), 3,955 recipient rows of which 315 unintended. Sent 2024-07-01 to 2025-03-31 (end exclusive); earlier mail from 2024-01-08 is history only.
- **Text vocabulary and weights** were fit on 95,241 sent messages before 2025-03-31 (vocabulary 1,366; warm-up mail included; validation and test mail excluded), not on validation or test.
- **Tuning** used expanding chronological folds inside `train`: 4 blocks covering weeks 2024-07-01 to 2025-03-24, of which 3 were scored; each block keeps a draft's family together. The regularization constant was chosen from the grid 0.001, 0.01, 0.1, 1, 10, 100, 1000 by mean email average precision across the scored folds.
- **Selected** `C = 1000`, the top of the grid, with `class_weight = balanced`. A weaker-regularized fit was not searched, and coefficients on overlapping count features are not separate effects.
- **Eligibility** of an all-features model required a clean shortcut audit and a win over the behavior-only and content-only runs in every train fold (smallest margins +0.234 and +0.117).
- **Seed** 20260926. The scratch rebuild of features and model reproduced the feature files and the model byte for byte ([reproducibility](phase_9/REPRODUCIBILITY.md)).
<!-- med-docs:end card_training -->

The training subset is enriched with mistakes so that the model sees enough of them. That mix is not an operating point, and precision at that mix says nothing about use.

## Evaluation data and the one test pass

<!-- med-docs:begin card_evaluation -->
| Subset | Emails | Misdirected | Legitimate | Used for | Frozen |
| --- | --- | --- | --- | --- | --- |
| `train` | 3,000 | 300 | 2,700 | fit the model and the text transformer's history | no |
| `validation_product_like` | 4,000 | 20 | 3,980 | model selection and the one cutoff choice | no |
| `validation_diagnostic` | 240 | 80 | 160 | scenario diagnostics | no |
| `test_product_like` | 6,000 | 30 | 5,970 | one evaluation of the frozen policy | yes |
| `test_diagnostic` | 256 | 88 | 168 | one scenario evaluation of the frozen policy | yes |

Validation mail was sent 2025-03-31 to 2025-09-01; test mail 2025-09-01 to 2026-01-05 (ends exclusive). The policy file was written 2026-09-26T15:12:05Z and the frozen subsets were scored once, 2026-09-26T15:17:08Z, with the policy whose SHA-256 the test record stores (`be39929a3c92cf97…`). Product-like subsets hold exactly 0.5% misdirected emails by construction.
<!-- med-docs:end card_evaluation -->

The two diagnostic subsets are scenario challenge sets. They hold many mistakes and several drafts per family, so their rates are not product-like results and carry no valid false-warning bound. The frozen subsets were never used to choose features, a model, or a cutoff.

## Operating point and how it was chosen

One warning cutoff on the email risk score, chosen on `validation_product_like` by a rule written before any test result existed: keep the candidates with no false warnings, take the one with the highest recall, and break ties with the highest cutoff. The cutoff equals the score of the lowest-scoring mistake it warns on, so it is tight by construction. Blocking is disabled and the policy file records that. The [threshold policy](phase_5/THRESHOLD_POLICY.md) documents the rule, the budget, and the load checks.

<!-- med-docs:begin card_operating_point -->
| Item | Value |
| --- | --- |
| Decision rule | email risk = maximum recipient risk score; allow when `email_risk < T_warn`; warn when `email_risk >= T_warn (equality warns)`; block: disabled |
| `T_warn` | `0.9996767050340489` |
| Chosen on | `validation_product_like`, email level |
| Candidates | 3,999, of which 9 had no false interventions; 1 at the chosen recall |
| Chosen operating point | 8 of 20 mistakes warned, 0 of 3,980 legitimate emails warned |
| Highest legitimate validation score | 0.9973707, 2.31e-03 below `T_warn` |
| Budget | at most 1 false intervention per 1,000 legitimate emails; an intervention is a warn or a simulated block, counted once per email; the denominator is all legitimate emails in the evaluation subset |
| Parity check before the policy was written | 4,000 of 4,000 decisions identical between the batch path and the single-draft path the API uses; largest score difference 3.89e-15 |
| Calibration | `not_fit` |

Selection rule: Candidates are the distinct email risk scores on the subset plus one cutoff above every score. Keep candidates with 0 false interventions, maximize email recall, break ties with the highest cutoff.
<!-- med-docs:end card_operating_point -->

## Results

Every figure carries its denominator. Intervals are exact binomial intervals that assume independent emails; that assumption is not established (see [results](RESULTS.md#6-demonstrated-versus-assumed)), so the interval is a conditional figure and not a confidence-supported claim. The one test pass is a single draw from one fictional organization.

<!-- med-docs:begin card_results -->
| Subset | Emails | Misdirected | Warned mistakes | Email recall, exact 95% (if independent) | Legitimate | False warnings | Per 1,000 legitimate | Exact 95% upper per 1,000 (if independent) | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` (chose the cutoff) | 4,000 | 20 | 8 / 20 | 0.400 [0.191, 0.639] | 3,980 | 0 / 3,980 | 0.00 | 0.93 | 100.0% |
| `test_product_like` (the one frozen test pass) | 6,000 | 30 | 9 / 30 | 0.300 [0.147, 0.494] | 5,970 | 0 / 5,970 | 0.00 | 0.62 | 100.0% |

| Subset | Emails | Misdirected per 1,000 emails | Detections per 1,000 emails | Detections, exact 95% (if independent) | Missed per 1,000 emails | False warnings per 1,000 emails | Interruptions per 1,000 emails |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` | 4,000 | 5.00 | 2.00 | [0.96, 3.20] | 3.00 | 0.00 | 2.00 |
| `test_product_like` | 6,000 | 5.00 | 1.50 | [0.74, 2.47] | 3.50 | 0.00 | 1.50 |

Diagnostic subsets, scenario challenge sets and not product-like results:

| Subset | Emails | Warned mistakes | Legitimate emails warned | Interval |
| --- | --- | --- | --- | --- |
| `validation_diagnostic` | 240 | 33 / 80 | 0 / 160 | family-bootstrap interval only; see the evaluation report |
| `test_diagnostic` | 256 | 37 / 88 | 0 / 168 | family-bootstrap interval only; see the evaluation report |

Acceptance status (rules and measured values in [results](RESULTS.md#5-acceptance-criteria)):

| ID | Criterion | Status |
| --- | --- | --- |
| AC01 | Interruption budget | **insufficient evidence** |
| AC02 | Detection utility | **insufficient evidence** |
| AC03 | Threshold integrity | **met** |
| AC04 | Conservative blocking | **met** |
| AC05 | Latency | **met** |
| AC06 | Recipient completeness | **met** |
| AC07 | Legitimate novelty | **insufficient evidence** |
| AC08 | Failure clarity | **met** |
| AC09 | Traceable explanations | **met** |
| AC10 | Scope and evidence honesty | **met** |
<!-- med-docs:end card_results -->

Scenario-by-scenario outcomes, the model comparison, and latency are in [results](RESULTS.md). The Phase 5 [evaluation report](phase_5/EVALUATION_REPORT.md) holds the family-bootstrap intervals, precision–recall curves, and prevalence sensitivity.

## Known failure modes

<!-- med-docs:begin card_failures -->
| Scenario | Story | `validation_product_like` | `validation_diagnostic` | `test_product_like` | `test_diagnostic` |
| --- | --- | --- | --- | --- | --- |
| **S01** | Lookalike replacement | 0 / 4 | 0 / 10 | 0 / 6 | 0 / 11 |
| **S04** | Familiar recipient, unusual topic | 0 / 4 | 0 / 10 | 0 / 5 | 0 / 11 |
| **S11** | Mistaken first contact | 0 / 2 | 0 / 10 | 0 / 3 | 0 / 11 |

- **Legitimate first contacts sit just below the cutoff.** The highest legitimate validation email scores 0.9973707, 2.31e-03 below `T_warn`. A small shift in legitimate scores, or a new kind of legitimate first contact, would add false warnings.
- **Content cosine is a strong signal on this generator.** Its train separation is 0.932, inside the audit bounds (0.05 to 0.95) but not far inside. Validation email average precision is 0.831 for the selected run and 0.494 for the best behavior-only logistic run.
- **Few positives.** 20 and 30 misdirected emails in the product-like subsets.
- **Reason codes in the recorded warning fixtures.** 4 of 5 flagged recipients in 4 warning fixtures carry the reason `CONTENT_RELATIONSHIP_MISMATCH`; the remaining 1 carries only context codes.
<!-- med-docs:end card_failures -->

- **Three kinds of mistake are not warned on.** Lookalike replacements (S01), familiar-recipient topic mistakes (S04), and mistaken first contacts (S11) were allowed on every subset. Legitimate first contacts score just below the cutoff, so a cutoff low enough to warn on these mistakes would also warn on legitimate mail. Making the misses visible in the review screen does not reduce them.
- **The margin is thin.** The cutoff sits just above the highest legitimate validation score. A drift in legitimate scores, or a new kind of legitimate first contact, adds false warnings; the drift replay shows near-cutoff scores rising under a first-contact wave.
- **Content is a strong signal on this generator.** Off-topic mistakes (S02, S04) sit low on content similarity because the scenarios were written that way, and the model's gain on them partly restates how the data was made. The eligibility checks passed, but not by a wide margin.
- **Content similarity drives most warnings.** The API marks a flagged recipient with `CONTENT_RELATIONSHIP_MISMATCH` when raising only that recipient's content similarity to the typical training value would drop its score below the cutoff (the count in the recorded fixtures is above). A flagged recipient without that code rests on other signals. The other codes are context, not proof.
- **An address outside the directory snapshot is not assessed.** A typo returns `unable_to_assess` and is not a warning.
- **Sparse evidence is visible, not corrected.** A cold-start sender, a first contact, or an empty draft is assessed with an evidence limitation.
- **Coefficients are not separate effects.** The regularization constant sits at the top of its grid and several count features overlap, so no single coefficient is a behavioral finding.
- **Lifetime counts leave the training range as time passes.** Several count inputs are structurally outside the training range for later mail; the monitor counts them and cannot say when that starts to matter.

## Calibration status

`calibration: not_fit`. The validation subset has too few mistakes to split into a calibration portion and a threshold-selection portion, the diagnostic subset is not the operating mix, and the training data fit the model. Scores rank risk. They do not estimate the probability that a recipient is unintended, and a reliability table on the diagnostic subset is a shape check only ([evaluation report](phase_5/EVALUATION_REPORT.md#calibration)).

## Fairness and privacy notes

This corpus is one fictional organization, so these are limits of the evidence and not findings.

- **No group fairness analysis is possible or claimed.** The data has no demographic or protected attributes. Results are not disaggregated by sender, team, role, or language: most product-like drafts come from one sender, so per-sender behavior is effectively unmeasured. A real deployment would need per-sender and per-team slices before any fairness claim.
- **Who bears the cost.** False warnings land on senders whose legitimate mail looks unusual: new collaborators, new external domains, topic changes. The evaluation checks synthetic examples of each as counterexamples. It cannot say how real senders with unusual patterns would be treated, and name similarity assumes the naming conventions of the generator, in English only.
- **Privacy in the demo.** All people and addresses are fictional on reserved `.example` domains, and no real mail is read. The API's structured log carries ids, status, category, decision, timing, versions, and counts, never an address, name, subject, or body. A feedback line stores a contact id, a label, versions, and a time, never an address. Monitoring records are aggregates and a simulated review queue.
- **Privacy in a real setting.** The scorer reads message text and a sender's relationship history. That would need a data-protection review, access control, retention limits, and notice to senders. Wider monitoring logs are a privacy decision proposed in [monitoring](phase_8/MONITORING.md#what-the-structured-log-carries-and-what-it-does-not) and not implemented.

## Monitoring, feedback, and rollback

- Monitoring is a simulation: a replay through the API against a train-only input reference, with input drift, decision-rate change, and confirmed performance change kept as three separate findings. See [monitoring](phase_8/MONITORING.md) and the [drift replay](phase_8/DRIFT_REPLAY.md).
- Feedback is a click stored for review. It is not a label until a reviewer accepts it, and it never changes the model, the policy, or the cutoff. See the [feedback review](phase_8/FEEDBACK_REVIEW.md).
- A change to the model, features, or policy is a new bundle evaluated offline with a new frozen test set; promotion gates, rollback steps, and incident triage are in the [runbook](phase_8/RUNBOOK.md). A rollback was rehearsed as an image swap ([rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md)); there is no live hot swap.

## Versions

<!-- med-docs:begin card_versions -->
| Component | Version | Identity (SHA-256 prefix) |
| --- | --- | --- |
| Dataset | `med-synth-v4` (generator `1.3.0`, seed 20260926) | manifest `9f53c114c8cbbb7f…` |
| Features | `med-features-v2` | manifest `b9ef336f22952042…` |
| Model | `med-model-v2`, run `logistic_all_balanced` | `model.joblib` `f698b69f7ff20fc9…` |
| Policy | `med-policy-v2`, `T_warn = 0.9996767050340489`, blocking disabled, calibration `not_fit` | `policy.json` `be39929a3c92cf97…` |
| API contract | `med-api-v1` | - |
| Monitoring record | `med-monitor-v1` | write-once records |
| Deployment record | `med-deploy-v1` | write-once records |
| Document generator | `med-docs-v1` | - |
| Libraries (served) | Python 3.11.14, scikit-learn 1.9.1, NumPy 2.4.6, FastAPI 0.141.1 | model fit with scikit-learn 1.9.1 |
| Images | `med-api:phase9` (arm64, 574 MiB), `med-ui:phase9` (arm64, 786 MiB) | `85d67e46cbf709ac…`, `d1983f4f61227a49…` |
<!-- med-docs:end card_versions -->

## Research basis and technique labels

The references are those in the [README research basis](../README.md#research-basis-and-techniques). Each technique used here is labeled **adopted** (used much as the source describes), **adapted** (a transfer or simplification of the source's idea), or **project extension** (an engineering choice no cited paper validates). Paper results are context for the techniques and are not performance claims for this system.

| Reference | Short form |
| --- | --- |
| R1 | Carvalho and Cohen (2007), *Preventing Information Leaks in Email* |
| R2 | Zilberman, Katz, Shabtai, and Elovici (2013), *Analyzing group E-mail exchange to detect data leakage* |
| R3 | Stolfo et al. (2006), *Behavior-based modeling and its application to Email analysis* |
| R4 | Balasubramanyan, Carvalho, and Cohen (2008), *CutOnce* |

| Technique in this system | Source | Label | Note |
| --- | --- | --- | --- |
| Assess each recipient of a draft against the draft and the sender's history | R1 | adapted | R1 frames unintended recipients as outliers and ranks an injected recipient. Here each recipient gets a supervised risk score, and no recipient is assumed to be wrong. |
| TF-IDF cosine content compatibility between the draft and earlier mail with a recipient | R1, R4 | adapted | The vectorizer is fit once on earlier mail. There is no group-topic profile. |
| Communication frequency and relationship counts | R1 | adopted | Used as features. |
| Recency of contact | R4 | adopted | Used as a feature. |
| Recipient co-occurrence and unusual combinations | R1, R3 | adapted | Pairwise co-occurrence on the sender's own mail is a lightweight substitute for group-pattern modeling. |
| Synthetic mistakes: an added recipient, and a replaced recipient | R1 | adapted | Replacement and lookalike scenarios are this project's adaptation. |
| Legitimate first-contact scenarios, and content compatibility beyond direct frequency | R2 | adapted | Motivated by R2. Its recipient-level rates are not comparable with this system's email-level warning budget. |
| Time-ordered evaluation: chronological splits and expanding folds | R1 | adopted | |
| Pre-send review with recipient-specific feedback, and capture of corrections | R4 | adapted | The warning is simulated; there is no send countdown, and a click is not a label. |
| Comparing combined signals with individual ones (ablations) | R1, R3, R4 | adopted | Reciprocal-rank fusion was not used, because ranks depend on the rest of the batch. |
| Behavioral profile comparison reused for drift monitoring | R3 | adapted | A project adaptation. |
| Maximum-recipient aggregation into an email decision | none | project extension | |
| A zero-false-warning cutoff rule, chosen on validation and applied once to a frozen test set | none | project extension | |
| Fail-closed `unable_to_assess` on any failure | none | project extension | |
| Explicit missing-history indicators and fallbacks | none | project extension | |
| Logistic regression and one small tree as the learned models | none | project extension | Implementation choices, not the papers' classifiers. |
| Versioned bundles, parity checks, scenario regression, containers, CI, drift replay, simulated review, and rollback rehearsal | none | project extension | The cited papers do not validate this complete design. |

R1's headline result is the precision of its top-ranked recipient when locating an injected one, not alert precision on ordinary mail. R2's abstract reports a recipient-level detection and false-flag rate on its own corpus. R3's experiments use simulated viral messages. R4's small study does not show real-world benefit. None of these transfers to the warning budget here.

## Related documents

[Results](RESULTS.md) · [architecture](ARCHITECTURE.md) · [limitations and future work](LIMITATIONS_AND_FUTURE_WORK.md) · [usage guide](USAGE_GUIDE.md) · [Phase 4 decision record](phase_4/DECISION_RECORD.md) · [Phase 5 evaluation report](phase_5/EVALUATION_REPORT.md) · [threshold policy](phase_5/THRESHOLD_POLICY.md) · [API contract](phase_6/API_CONTRACT.md) · [documentation index](README.md)
