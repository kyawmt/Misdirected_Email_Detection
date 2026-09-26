# Misdirected Email Detection

A machine learning project exploring how to identify potentially unintended email recipients before a message is sent. The goal is to reduce accidental data loss while keeping interruptions to legitimate communication low.

**Status: requirements and product specifications complete; implementation has not started.** The repository currently contains documentation only. No dataset, trained model, scoring service, application, or measured performance results are available yet.

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

The proposed stack is **Python**, **pandas/NumPy**, **scikit-learn**, **FastAPI**, and **Streamlit**, with SQLite or versioned local files for lightweight storage. These are planned choices, not installed dependencies or implemented components.

## Research basis and techniques

The design draws on published work while keeping the initial methods interpretable and inexpensive to run:

| Reference | Relevant technique and planned use |
| --- | --- |
| Carvalho & Cohen (2007), [*Preventing Information Leaks in Email*](https://doi.org/10.1137/1.9781611972771.7), SDM, pp. 68–77 | Treat message–recipient incompatibility as an outlier problem; combine text similarity, communication frequency, and recipient co-occurrence. |
| Zilberman, Katz, Shabtai & Elovici (2013), [*Analyzing group E-mail exchange to detect data leakage*](https://doi.org/10.1002/asi.22886), JASIST 64(9), pp. 1780–1790 | Consider shared topic context even without direct prior communication. Motivates legitimate first-contact cases and an optional group-topic experiment. |
| Stolfo et al. (2006), [*Behavior-based modeling and its application to Email analysis*](https://doi.org/10.1145/1149121.1149125), ACM TOIT 6(2), pp. 187–221 | Combine behavioral profiles and communication-group signals. Its viral-email experiments support anomaly-modeling ideas, not claims about accidental-recipient accuracy. |
| Balasubramanyan, Carvalho & Cohen (2008), [*CutOnce — Recipient Recommendation and Leak Detection in Action*](https://cdn.aaai.org/Workshops/2008/WS-08-04/WS08-04-001.pdf), AAAI EMAIL Workshop | Use TF-IDF recipient profiles, frequency, recency, and pre-send feedback; evaluate a simple signal combination as an optional comparison. |

Planned baselines include rules and logistic regression, followed by one small tree-based challenger. Features will include TF-IDF/cosine content similarity, relationship frequency and recency, co-recipient support, and contact-name/address similarity. No individual novelty signal will define whether a recipient was intended.

Maximum-risk aggregation, model choices, calibration, threshold policies, and operational monitoring are project adaptations or engineering extensions. This project is not a full reproduction of these papers, and their reported results are not performance claims for this system. In particular, identifying an injected wrong recipient in a ranking experiment is different from accurately warning on ordinary outbound traffic.

## Evaluation goals

Provisional targets are **at most one false intervention per 1,000 legitimate emails** and **warm local scoring p95 below 300 ms**. Neither has been measured. Warnings and simulated blocks both count as interventions.

Evaluation will compare detection recall within the interruption budget, report precision–recall metrics at both recipient and email levels, and include uncertainty, sample counts, and assessment coverage. Chronological splits and an untouched final test set will limit leakage. Errors will be examined for new contacts, external recipients, topic changes, and multi-recipient drafts.

## Repository structure

The current documentation files are:

```text
Misdirected_Email_Detection/
├── README.md
├── .gitignore
└── docs/
    └── phase_1/
        ├── PRODUCT_BRIEF.md
        ├── SCENARIOS.md
        ├── INPUT_OUTPUT_SPECIFICATION.md
        └── ACCEPTANCE_CRITERIA.md
```

## Setup and usage

No runtime setup is needed at this stage. Browse the Markdown files on GitHub or open a local copy in a Markdown viewer.

For a documentation walkthrough, read the [scenarios](docs/phase_1/SCENARIOS.md), inspect the [input/output specification](docs/phase_1/INPUT_OUTPUT_SPECIFICATION.md), and review the [acceptance criteria](docs/phase_1/ACCEPTANCE_CRITERIA.md). These describe desired behavior, not executable examples. Installation, dataset preparation, training, and application startup instructions will be added when those components exist.

## Development roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Product definition, scenarios, contracts, and measurable requirements | Complete — documentation |
| 2 | Fictional histories, synthetic mistakes, labeling, and chronological splits | Planned |
| 3 | Behavioral and text features with consistent historical lookup | Planned |
| 4 | Baselines, model comparison, and feature ablations | Planned |
| 5 | Evaluation, calibration if needed, and threshold selection | Planned |
| 6 | Scoring API, validation, explanations, and failure handling | Planned |
| 7 | Interactive draft review and simulated decisions | Planned |
| 8 | Monitoring, reviewed feedback, drift investigation, and safe iteration | Planned |
| 9 | Regression tests, reproducible packaging, deployment, and rollback | Planned |
| 10 | Architecture documentation, results, model card, and usage guide | Planned; initial README available |

## Limitations and data disclaimer

The project is designed around **fictional identities and synthetic email data**; currently, only scenario narratives exist. Future results on that data will demonstrate behavior under controlled assumptions and will not establish real-world detection accuracy.

The initial scope is English plain-text drafts with 1–20 unique recipients in a fictional environment. Mailbox integration, actual sending or blocking, attachment inspection, enterprise authentication, and production-scale operation are outside scope. Missing intended recipients without an unintended addressee are also outside the detection task.

False positives and missed mistakes are expected risks. Sparse history, legitimate new relationships, and changing topics may make assessments unreliable. An allow decision will not guarantee correctness, and the project should not be relied on to protect real confidential communications.
