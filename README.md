# Misdirected Email Detection

A machine learning project exploring how to identify potentially unintended email recipients before a message is sent. The goal is to reduce accidental data loss while keeping interruptions to legitimate communication low.

**Status: Phase 6 complete on the v4 bundle.** Requirements, the fictional dataset `med-synth-v4`, the feature specification `med-features-v2`, and the logistic risk scorer `med-model-v2` (all features, content cosine included) are in place. Warning policy `med-policy-v2` sets one warning cutoff on the risk score, chosen on product-like validation only, with blocking disabled and no calibration. The frozen v4 test subsets were scored once under that policy: 9 of 30 product-like mistakes warned with 0 false warnings on 5,970 legitimate emails, an exact upper bound of 0.62 false warnings per 1,000, inside the budget of 1 on this simulation. A FastAPI service (`med-api-v1` contract) serves that bundle; its measured p95 latency is 57.04 ms against a 300 ms target. Lookalike replacements, familiar-recipient topic mistakes, and mistaken first contacts are still missed. The review UI has not started.

## Intended behavior

The planned system will assess each recipient against the draft's content and the sender's earlier communication patterns. Example cases include selecting a lookalike contact, accidentally adding an external recipient, and sending an unusual topic to a familiar contact. Legitimate first contacts and topic changes are equally important counterexamples: unusual communication does not necessarily mean a mistake.

1. Enter a fictional draft with its timestamp, sender, To/Cc/Bcc recipients, subject, body, and a reference to fictional historical context.
2. Compare each unique recipient with communication history strictly preceding the draft.
3. Produce recipient risk scores and explanations, then use the highest recipient score as the initial email-level risk.
4. Apply a versioned threshold policy to return **allow**, **warn**, or **simulated block**. Blocking will remain disabled unless separate evaluation justifies it.
5. Reassess after edits; optionally collect corrections for later review.

A scoring failure will return **unable to assess**, never an automatic allow. Scores will be labeled as risk scores rather than probabilities unless calibration supports that interpretation. All sending and blocking behavior will be simulated.

## Planned architecture

```mermaid
flowchart LR
    subgraph Offline[Offline preparation]
        Data[Fictional histories and synthetic examples] --> Prep[Validation and chronological splits]
        Prep --> Train[Feature engineering and model comparison]
        Train --> Eval[Evaluation and threshold selection]
        Eval --> Bundle[Versioned model and policy]
        Prep --> History[Historical profiles]
    end
    subgraph Scoring[Request-time assessment]
        UI[Draft review UI] --> API[Scoring API]
        History --> Features[Shared feature transformations]
        API --> Features
        Features --> Decision[Recipient scores and email decision]
        Bundle --> Decision
        Decision --> UI
    end
    Decision --> Monitor[Latency, errors, and drift monitoring]
    UI --> Feedback[Corrections for review]
```

Historical profiles must respect each draft's cutoff time. Training and serving will share feature definitions to reduce inconsistencies. Feedback will not trigger automatic retraining.

Dataset construction uses **Python**, **pandas**, and **NumPy**. Feature preparation and the model comparison use **scikit-learn**. The scoring API uses **FastAPI**. The review UI is planned around **Streamlit** and is not implemented. Model outputs are risk scores, not probabilities. The warning cutoff lives in `med-policy-v2`, not in the model.

## Research basis and techniques

The design draws on published work while keeping the initial methods interpretable and inexpensive to run:

| Reference | Relevant technique and planned use |
| --- | --- |
| Carvalho & Cohen (2007), [*Preventing Information Leaks in Email*](https://doi.org/10.1137/1.9781611972771.7), SDM, pp. 68–77 | Treat message–recipient incompatibility as an outlier problem; combine text similarity, communication frequency, and recipient co-occurrence. |
| Zilberman, Katz, Shabtai & Elovici (2013), [*Analyzing group E-mail exchange to detect data leakage*](https://doi.org/10.1002/asi.22886), JASIST 64(9), pp. 1780–1790 | Consider shared topic context even without direct prior communication. Motivates legitimate first-contact cases and an optional group-topic experiment. |
| Stolfo et al. (2006), [*Behavior-based modeling and its application to Email analysis*](https://doi.org/10.1145/1149121.1149125), ACM TOIT 6(2), pp. 187–221 | Combine behavioral profiles and communication-group signals. Its viral-email experiments support anomaly-modeling ideas, not claims about accidental-recipient accuracy. |
| Balasubramanyan, Carvalho & Cohen (2008), [*CutOnce — Recipient Recommendation and Leak Detection in Action*](https://cdn.aaai.org/Workshops/2008/WS-08-04/WS08-04-001.pdf), AAAI EMAIL Workshop | Use TF-IDF recipient profiles, frequency, recency, and pre-send feedback; evaluate a simple signal combination as an optional comparison. |

The recorded comparison is an always-allow baseline, a behavioral rules score, logistic regression, and one depth-limited decision tree. `med-features-v2` implements TF-IDF/cosine content similarity, relationship frequency and recency, co-recipient support, and contact-name/address similarity. No individual novelty signal defines whether a recipient was intended. A group-topic profile is still optional and is not in this feature specification.

Maximum-risk aggregation, model choices, calibration, threshold policies, and operational monitoring are project adaptations or engineering extensions. This project is not a full reproduction of these papers, and their reported results are not performance claims for this system. In particular, identifying an injected wrong recipient in a ranking experiment is different from accurately warning on ordinary outbound traffic.

## Evaluation goals

Provisional targets are **at most one false intervention per 1,000 legitimate emails** and **warm local scoring p95 below 300 ms**. Both were measured on this simulation for the v4 bundle; see the [evaluation report](docs/phase_5/EVALUATION_REPORT.md) and [scoring flow](docs/phase_6/SCORING_FLOW.md). Warnings and simulated blocks both count as interventions.

Evaluation will compare detection recall within the interruption budget, report precision–recall metrics at both recipient and email levels, and include uncertainty, sample counts, and assessment coverage. Chronological splits and an untouched final test set will limit leakage. Errors will be examined for new contacts, external recipients, topic changes, and multi-recipient drafts.

## Repository structure

```text
Misdirected_Email_Detection/
├── README.md
├── pyproject.toml
├── data/
│   ├── med-synth-v4/          # current fictional tables, manifest, quality report
│   └── med-synth-v2/          # superseded baseline, kept unchanged
├── docs/
│   ├── phase_1/
│   │   ├── PRODUCT_BRIEF.md
│   │   ├── SCENARIOS.md
│   │   ├── INPUT_OUTPUT_SPECIFICATION.md
│   │   └── ACCEPTANCE_CRITERIA.md
│   ├── phase_2/
│   │   ├── DATA_DICTIONARY.md
│   │   ├── LABELING_GUIDE.md
│   │   ├── DATASET_SPECIFICATION.md
│   │   └── DATA_QUALITY_AND_LEAKAGE.md
│   ├── phase_3/
│   │   ├── FEATURE_CATALOG.md
│   │   ├── PROFILE_AND_TRANSFORM.md
│   │   ├── FEATURE_QUALITY_REPORT.md
│   │   └── TRAINING_SERVING_PARITY.md
│   ├── phase_4/
│   │   ├── EXPERIMENT_TABLE.md
│   │   ├── COMPARISON.md
│   │   ├── ABLATIONS.md
│   │   ├── MODEL_ARTIFACT.md
│   │   └── DECISION_RECORD.md
│   ├── phase_5/
│   │   ├── EVALUATION_REPORT.md
│   │   ├── THRESHOLD_POLICY.md
│   │   ├── ERROR_ANALYSIS.md
│   │   ├── UNCERTAINTY_AND_PREVALENCE.md
│   │   ├── MODEL_CARD.md
│   │   └── figures/
│   └── phase_6/
│       ├── API_CONTRACT.md
│       ├── SCORING_FLOW.md
│       └── ERROR_BEHAVIOR.md
├── artifacts/med-features-v2/ # fitted text transformer and train/validation matrices (v4)
├── artifacts/med-model-v2/    # selected scorer and experiment record (v4)
├── artifacts/med-policy-v2/   # warning policy, validation scores, one-shot test result (v4)
├── artifacts/med-api-latency/ # API latency, one record per served policy bundle
├── artifacts/*-v1/            # superseded v2 baseline bundle and its API latency, kept unchanged
├── src/med_data/              # generator, scoring view, validation
├── src/med_features/          # shared feature transform
├── src/med_models/            # baselines, ablations, and the selected scorer
├── src/med_policy/            # threshold selection, decision function, evaluation, reports
├── src/med_api/               # FastAPI scoring service, request normalizer, feedback
└── tests/
```

## Setup and usage

Python 3.11 or newer is required. From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
python -m med_data validate
python -m med_features build --quality-markdown docs/phase_3/FEATURE_QUALITY_REPORT.md
python -m med_models run
python -m med_policy report
```

Every command reads its default dataset, artifact, and docs paths from one version module per package (`src/*/version.py`), so the defaults above name the v4 bundle. The policy was selected and evaluated once with the commands below. `select` reads validation only, checks that the batch and single-draft scoring paths give identical decisions on every selection draft, and refuses to run after the test result exists. `evaluate-test` refuses to run without `policy.json` and refuses to run a second time. `report` regenerates `docs/phase_5` from the stored results.

```bash
python -m med_policy select
python -m med_policy evaluate-test
```

Start the scoring API (simulation only) on `http://127.0.0.1:8000`:

```bash
python -m med_api serve
```

`GET /health` reports that the process is up. `GET /ready` reports that the frozen bundle and the `med-synth-v4` snapshot loaded. `POST /assess` takes one fictional draft (timestamp with timezone, sender, To/Cc/Bcc, subject, body, and `context_snapshot_id: "med-synth-v4"`) and returns a risk score per unique recipient, the email risk score, and `allow` or `warn`. Invalid input and unavailable context both return `unable_to_assess`, never allow. `POST /feedback` appends a reviewed label to a local gitignored file and changes nothing else. `python -m med_api latency` measures the API boundary once per served policy bundle, writes `artifacts/med-api-latency/<policy version>/latency.json`, and refuses to overwrite an existing record. `python -m med_api report` regenerates `docs/phase_6`.

`pytest` rebuilds the dataset from seed `20260926` and checks it against the published files, then checks the feature and model contracts. `validate` reloads `data/med-synth-v4`, verifies SHA-256 checksums and parsed record counts, and runs the quality checklist. `med_features build` fits TF-IDF on sent mail before the validation window and writes recipient-level features for train and validation only. `med_models run` repeats the recorded comparison and rewrites `med-model-v2`. It does not score the frozen test subsets and does not choose a threshold. `med_policy` never fits the transformer, the scaler, or the model; it computes frozen-test features in memory and writes no test feature file. To write the tables again:

```bash
python -m med_data build
```

The published build is `med-synth-v4` (generator `1.3.0`). Product-like mail uses a **simulation assumption of 0.5% misdirected emails**. The training subset is enriched to 10% and is not an operating point. `test_product_like` and `test_diagnostic` are frozen for this version. The feature build does not write those subsets.

Read the [API contract](docs/phase_6/API_CONTRACT.md), [scoring flow](docs/phase_6/SCORING_FLOW.md), and [error behavior](docs/phase_6/ERROR_BEHAVIOR.md) for the service. Read the [evaluation report](docs/phase_5/EVALUATION_REPORT.md), [threshold policy](docs/phase_5/THRESHOLD_POLICY.md), [error analysis](docs/phase_5/ERROR_ANALYSIS.md), [uncertainty and prevalence](docs/phase_5/UNCERTAINTY_AND_PREVALENCE.md), and [model card](docs/phase_5/MODEL_CARD.md) for the policy and its one test pass. Read the [decision record](docs/phase_4/DECISION_RECORD.md), [experiment table](docs/phase_4/EXPERIMENT_TABLE.md), [comparison](docs/phase_4/COMPARISON.md), and [ablations](docs/phase_4/ABLATIONS.md) for the recorded runs. The [feature catalog](docs/phase_3/FEATURE_CATALOG.md), [profile and transform contract](docs/phase_3/PROFILE_AND_TRANSFORM.md), [feature quality report](docs/phase_3/FEATURE_QUALITY_REPORT.md), and [training/serving parity notes](docs/phase_3/TRAINING_SERVING_PARITY.md) describe the signals. The [data dictionary](docs/phase_2/DATA_DICTIONARY.md), [labeling guide](docs/phase_2/LABELING_GUIDE.md), [dataset specification](docs/phase_2/DATASET_SPECIFICATION.md), and [quality and leakage checklist](docs/phase_2/DATA_QUALITY_AND_LEAKAGE.md) describe the tables. The [scenarios](docs/phase_1/SCENARIOS.md), [input/output specification](docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md), and [acceptance criteria](docs/phase_1/ACCEPTANCE_CRITERIA.md) still describe the product contract. Application startup comes in a later phase.

## Development roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Product definition, scenarios, contracts, and measurable requirements | Complete — documentation |
| 2 | Fictional histories, synthetic mistakes, labeling, and chronological splits | Complete — `med-synth-v4` |
| 3 | Behavioral and text features with consistent historical lookup | Complete — `med-features-v2` |
| 4 | Baselines, model comparison, and feature ablations | Complete — `med-model-v2` |
| 5 | Evaluation, calibration if needed, and threshold selection | Complete — `med-policy-v2` |
| 6 | Scoring API, validation, explanations, and failure handling | Complete — `med-api-v1` contract serving the v4 bundle |
| 7 | Interactive draft review and simulated decisions | Planned |
| 8 | Monitoring, reviewed feedback, drift investigation, and safe iteration | Planned |
| 9 | Regression tests, reproducible packaging, deployment, and rollback | Planned |
| 10 | Architecture documentation, results, model card, and usage guide | Planned; initial README available |

## Limitations and data disclaimer

The project uses **fictional identities and synthetic email**. `med-synth-v4` is a generated record with stipulated labels, not a sample of real mail. Results show behavior under the generator's assumptions and do not establish real-world detection accuracy. The 0.5% product-like prevalence is a simulation assumption; the 10% training mix is enrichment for fitting. Diagnostic challenge rows are dependent within a `family_id` and are not a substitute for the product-like test. Template language repeats across time, and stripping reference, ticket, and date slots does not remove shared topic wording.

Content cosine is a real but strong signal on this generator: alone it separates training mistakes from ordinary mail with an AUC of 0.932. Off-topic mistakes (S02, S04) sit low on it because the scenarios were written that way. An all-features model was allowed into selection only after three recorded train-only checks passed: the shortcut audit flags no content feature beyond 0.05–0.95, the all-features model beats the behavior-only model in every chronological train fold, and it also beats the content-only model in every fold. The selected `logistic_all_balanced` has product-like validation email average precision 0.831 [0.676, 0.954] on 20 positive emails; the best behavior-only model reaches 0.494. Its regularization constant is 1000, the top of the extended training grid, and its coefficients on overlapping counts are not separate effects. The warning cutoff (risk score 0.99968) was chosen with zero false warnings on 3,980 legitimate validation emails; that validation bound is not independent evidence because validation chose the cutoff. On the one product-like test pass, the policy warned on 9 of 30 misdirected emails (exact 95% recall interval 0.147 to 0.494) with 0 false warnings on 5,970 legitimate emails; the exact upper 95% bound, 0.62 per 1,000, is within the budget of 1 on this simulation. The warned mistakes are added recipients (S02, S08) and cold-sender cases (S09). Every lookalike replacement (S01), familiar-recipient topic mistake (S04), and mistaken first contact (S11) in the validation and test subsets was allowed: legitimate first contacts score just below the cutoff, so the cutoff sits above most mistakes that look like them. Scores are not calibrated, and blocking is disabled. A well-formed address that is not in the snapshot directory, such as a typo, returns `unable_to_assess` rather than a warning. Measured at the API boundary over all 4,000 product-like validation drafts with one request in flight, p95 latency is 57.04 ms against the 300 ms target, on this machine only. Diagnostic rates are not 0.5% prevalence results.

The earlier v2 bundle (`med-synth-v2`, `med-features-v1`, `med-model-v1`, `med-policy-v1`) is kept unchanged as a baseline. It was superseded because its data made content cosine a near-perfect separator (train AUC 0.991), placed 66.5% of legitimate training rows within five minutes of earlier mail to the same recipient and no mistakes, and contained no mistaken first contact, so its behavior-only scorer learned that a new recipient is safe. Its test pass (5 of 10 warned, 0 false warnings on 1,990 legitimate emails, upper bound 1.85 per 1,000) could not support the budget, and its API p95 was 345.84 ms.

The initial scope is English plain-text drafts with 1–20 unique recipients in a fictional environment. Mailbox integration, actual sending or blocking, attachment inspection, enterprise authentication, and production-scale operation are outside scope. Missing intended recipients without an unintended addressee are also outside the detection task.

False positives and missed mistakes are expected risks. Sparse history, legitimate new relationships, and changing topics may make assessments unreliable. An allow decision will not guarantee correctness, and the project should not be relied on to protect real confidential communications.
