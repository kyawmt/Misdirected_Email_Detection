# Phase 5 — Error analysis

Examples use the frozen policy (`T_warn = 0.134557`). Scores are risk scores. Subjects are fictional and shortened.

## Validation examples

### `validation_product_like`

| Case | Draft | Scenario | Email risk score | Decision | Subject |
| --- | --- | --- | --- | --- | --- |
| Allowed ordinary email | `d001929` | S05 | 3.6e-05 | allow | "Shipment window 2025-08-08" |
| Warned mistake | `d001019` | S04 | 0.135 | warn | "Salary band planning 2025-03-31" |
| Missed mistake | `d001001` | S01 | 0.0828 | allow | "Headcount update for 2025-03-31" |
| Legitimate first contact | `d001077` | S09 | 5.82e-05 | allow | "Introduction for 2025-04-09" |

### `validation_diagnostic`

| Case | Draft | Scenario | Email risk score | Decision | Subject |
| --- | --- | --- | --- | --- | --- |
| Allowed ordinary email | `d001063` | S05 | 7.4e-24 | allow | "Weekly project status T-17923" |
| Warned mistake | `d001041` | S08 | 1 | warn | "Weekly project status T-21001" |
| Missed mistake | `d001020` | S04 | 0.106 | allow | "Salary band planning 2025-04-30" |
| Legitimate first contact | `d001079` | S09 | 8.85e-05 | allow | "Welcome and introduction T-29181" |

- `validation_product_like`: warned S02 1, S04 1, S08 2; 1 to 6 recipients; risk scores 0.135 to 1. Missed S01 1; 1 recipient each; risk score 0.0828.
- `validation_diagnostic`: warned S02 4, S08 12, S09 4; 1 to 6 recipients; risk score 1. Missed S01 4, S04 4; 1 recipient each; risk scores 0.00476 to 0.106.
- On `validation_product_like` the highest missed mistake scores 0.08284, and 6 legitimate emails score above it. The selection rule cannot warn on it without a false warning.

S01 and S04 hinge on content: the wrong recipient is a known correspondent, so relationship and co-recipient features look ordinary. The behavior-only scorer leaves content out on purpose, because content cosine is the generator shortcut. The one S04 warning on `validation_product_like` scores exactly `T_warn`; it set the cutoff.

### Missed and false warnings, `validation_product_like`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d001001` | S01 | 0.0828 | 1 |

### Missed and false warnings, `validation_diagnostic`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d001020` | S04 | 0.106 | 1 |
| missed | `d001002` | S01 | 0.085 | 1 |
| missed | `d001022` | S04 | 0.0524 | 1 |
| missed | `d001004` | S01 | 0.0501 | 1 |
| missed | `d001024` | S04 | 0.0354 | 1 |
| missed | `d001008` | S01 | 0.0314 | 1 |
| missed | `d001006` | S01 | 0.0217 | 1 |
| missed | `d001026` | S04 | 0.00476 | 1 |

### Missed and false warnings, `test_product_like`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d002088` | S04 | 0.0149 | 1 |
| missed | `d002066` | S01 | 0.0132 | 1 |
| missed | `d002065` | S01 | 0.00643 | 1 |
| missed | `d002067` | S01 | 0.00533 | 1 |
| missed | `d002087` | S04 | 0.00331 | 1 |

### Missed and false warnings, `test_diagnostic`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d002070` | S01 | 0.00438 | 1 |
| missed | `d002091` | S04 | 0.00426 | 1 |
| missed | `d002068` | S01 | 0.0031 | 1 |
| missed | `d002074` | S01 | 0.00205 | 1 |
| missed | `d002089` | S04 | 0.002 | 1 |
| missed | `d002072` | S01 | 0.00176 | 1 |
| missed | `d004131` | S01 | 0.0014 | 1 |
| missed | `d002093` | S04 | 0.000734 | 1 |
| missed | `d002095` | S04 | 0.000696 | 1 |
| missed | `d004135` | S04 | 3.02e-05 | 1 |

## Note on the single test pass

This is inspection after the one test pass. It does not permit moving the cutoff. Across `test_product_like` and `test_diagnostic`, missed mistakes by scenario: S01 8, S04 7. Warned mistakes by scenario: S02 8, S08 17, S09 5. False warnings: 0. The pattern matches validation: added recipients (S02, S08) and cold-sender cases (S09) warn; lookalike replacements (S01) and familiar-recipient topic mistakes (S04) do not.

## Synthetic shortcuts

Read every recall figure in this phase next to these limits of the synthetic data and the frozen scorer:

- **Content shortcut.** An all-features logistic model reaches email average precision 1.000 on `validation_product_like` because content cosine restates the generator's per-relationship topics. The frozen scorer is behavior-only and does not use it, so lookalike replacements (S01) and familiar-recipient, unusual-topic mistakes (S04) are mostly missed: `validation_product_like`: S01 0 warned / 1 missed, S04 1 warned / 0 missed; `validation_diagnostic`: S01 0 warned / 4 missed, S04 0 warned / 4 missed; `test_product_like`: S01 0 warned / 3 missed, S04 0 warned / 2 missed; `test_diagnostic`: S01 0 warned / 5 missed, S04 0 warned / 5 missed. The drafts are listed in the [error analysis](ERROR_ANALYSIS.md).
- **Five-minute burst.** 1543 of 2259 legitimate recipient rows on `validation_product_like` had earlier mail to the same recipient under five minutes before the draft; 0 of 6 unintended rows did. Part of the behavior-only risk score is that generator timing.
- **First contact near 0.** Rewriting the 6 unintended `validation_product_like` rows as first contacts moves their median risk score from 0.9998 to 5.3e-08; 0 of them would still be flagged. This version cannot warn on a mistaken first contact.
- **Few positives.** `validation_product_like` has 5 misdirected emails and `test_product_like` has 10. Recall intervals are wide.
- **Unregularized fit.** The scorer is logistic regression with `C = 100`, the top of its training grid. Coefficients on overlapping counts are not separate effects.
