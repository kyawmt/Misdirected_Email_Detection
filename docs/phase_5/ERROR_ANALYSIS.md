# Phase 5 — Error analysis

Examples use the frozen policy (`T_warn = 0.999677`). Scores are risk scores. Subjects are fictional and shortened.

## Validation examples

### `validation_product_like`

| Case | Draft | Scenario | Email risk score | Decision | Subject |
| --- | --- | --- | --- | --- | --- |
| Allowed ordinary email | `d005704` | routine | 5.40698e-05 | allow | "Project status and schedule 2025-07-01" |
| Warned mistake | `d003028` | S02 | 0.999677 | warn | "Cost center forecast 2025-05-01" |
| Missed mistake | `d003026` | S02 | 0.994951 | allow | "Forecast variance T-97455" |
| Legitimate first contact | `d003216` | S03 | 0.997371 | allow | "Introduction and next steps T-154687" |

### `validation_diagnostic`

| Case | Draft | Scenario | Email risk score | Decision | Subject |
| --- | --- | --- | --- | --- | --- |
| Allowed ordinary email | `d003194` | S05 | 2.75122e-11 | allow | "Project status and schedule 2025-05-15" |
| Warned mistake | `d003148` | S08 | 0.999998 | warn | "Project status and schedule 2025-08-05" |
| Missed mistake | `d003037` | S02 | 0.999664 | allow | "Cost center forecast 2025-06-25" |
| Legitimate first contact | `d003226` | S03 | 0.998527 | allow | "Introduction and next steps T-154707" |

- `validation_product_like`: warned S02 3, S08 4, S09 1; 1 to 6 recipients; risk scores 0.9997 to 1. Missed S01 4, S02 1, S04 4, S08 1, S11 2; 1 to 5 recipients; risk scores 0.9261 to 0.995.
- `validation_diagnostic`: warned S02 1, S08 22, S09 10; 1 to 6 recipients; risk score 1. Missed S01 10, S02 9, S04 10, S08 8, S11 10; 1 to 5 recipients; risk scores 0.1387 to 0.9997.
- On `validation_product_like` the highest missed mistake scores 0.994951, and 1 legitimate emails score above it. The selection rule cannot warn on it without a false warning.

The zero-false-warning rule puts `T_warn` at 0.999677, above every legitimate validation email. Legitimate first contacts are among the highest-scoring legitimate emails (up to 0.997371), so they set how high the cutoff must go. Mistakes that score below that band, including every S01, S04, and S11 validation mistake, are allowed.

### Missed and false warnings, `validation_product_like`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d003026` | S02 | 0.994951 | 2 |
| missed | `d003049` | S04 | 0.994319 | 1 |
| missed | `d003051` | S04 | 0.993733 | 1 |
| missed | `d003050` | S04 | 0.993702 | 1 |
| missed | `d003052` | S04 | 0.993533 | 1 |
| missed | `d003095` | S08 | 0.987284 | 5 |
| missed | `d003002` | S01 | 0.981836 | 1 |
| missed | `d003074` | S11 | 0.981468 | 1 |
| missed | `d003004` | S01 | 0.974564 | 1 |
| missed | `d003003` | S01 | 0.9512 | 1 |
| missed | `d003001` | S01 | 0.927079 | 1 |
| missed | `d003073` | S11 | 0.926096 | 1 |

### Missed and false warnings, `validation_diagnostic`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d003037` | S02 | 0.999664 | 2 |
| missed | `d003031` | S02 | 0.999321 | 2 |
| missed | `d003033` | S02 | 0.999238 | 2 |
| missed | `d003045` | S02 | 0.999138 | 2 |
| missed | `d003075` | S11 | 0.998265 | 1 |
| missed | `d003079` | S11 | 0.998244 | 1 |
| missed | `d003043` | S02 | 0.998049 | 2 |
| missed | `d003029` | S02 | 0.998014 | 2 |
| missed | `d003093` | S11 | 0.997972 | 1 |
| missed | `d003083` | S11 | 0.997618 | 1 |
| missed | `d003039` | S02 | 0.997573 | 2 |
| missed | `d003047` | S02 | 0.997565 | 2 |
| missed | `d003091` | S11 | 0.996823 | 1 |
| missed | `d003057` | S04 | 0.99595 | 1 |
| missed | `d003063` | S04 | 0.995552 | 1 |
| missed | `d003041` | S02 | 0.995372 | 2 |
| missed | `d003081` | S11 | 0.99433 | 1 |
| missed | `d003055` | S04 | 0.99257 | 1 |
| missed | `d003053` | S04 | 0.992465 | 1 |
| missed | `d003077` | S11 | 0.992157 | 1 |
| missed | `d003071` | S04 | 0.989442 | 1 |
| missed | `d003065` | S04 | 0.98795 | 1 |
| missed | `d003087` | S11 | 0.987723 | 1 |
| missed | `d003067` | S04 | 0.987082 | 1 |
| missed | `d003089` | S11 | 0.986992 | 1 |
| missed | `d003059` | S04 | 0.985142 | 1 |
| missed | `d003069` | S04 | 0.985057 | 1 |
| missed | `d003085` | S11 | 0.980825 | 1 |
| missed | `d003013` | S01 | 0.980604 | 1 |
| missed | `d003113` | S08 | 0.97037 | 5 |
| missed | `d003126` | S08 | 0.967897 | 5 |
| missed | `d003061` | S04 | 0.960975 | 1 |
| missed | `d003005` | S01 | 0.960801 | 1 |
| missed | `d003021` | S01 | 0.950878 | 1 |
| missed | `d003017` | S01 | 0.941488 | 1 |
| missed | `d003007` | S01 | 0.926559 | 1 |
| missed | `d003019` | S01 | 0.921482 | 1 |
| missed | `d003011` | S01 | 0.848794 | 1 |
| missed | `d003023` | S01 | 0.835681 | 1 |
| missed | `d003015` | S01 | 0.711014 | 1 |
| missed | `d003009` | S01 | 0.680228 | 1 |
| missed | `d003109` | S08 | 0.631707 | 5 |
| missed | `d003105` | S08 | 0.548039 | 5 |
| missed | `d003097` | S08 | 0.484965 | 5 |
| missed | `d003134` | S08 | 0.342304 | 5 |
| missed | `d003130` | S08 | 0.19884 | 5 |
| missed | `d003101` | S08 | 0.138672 | 5 |

### Missed and false warnings, `test_product_like`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d007272` | S02 | 0.99853 | 2 |
| missed | `d007268` | S02 | 0.997634 | 2 |
| missed | `d007271` | S02 | 0.997482 | 2 |
| missed | `d007319` | S11 | 0.997442 | 1 |
| missed | `d007270` | S02 | 0.997332 | 2 |
| missed | `d007295` | S04 | 0.992705 | 1 |
| missed | `d007294` | S04 | 0.99134 | 1 |
| missed | `d007297` | S04 | 0.991029 | 1 |
| missed | `d007241` | S01 | 0.989237 | 1 |
| missed | `d007320` | S11 | 0.987842 | 1 |
| missed | `d007244` | S01 | 0.987699 | 1 |
| missed | `d007243` | S01 | 0.98465 | 1 |
| missed | `d007296` | S04 | 0.976203 | 1 |
| missed | `d007293` | S04 | 0.974206 | 1 |
| missed | `d007242` | S01 | 0.955719 | 1 |
| missed | `d007318` | S11 | 0.919411 | 1 |
| missed | `d007246` | S01 | 0.915111 | 1 |
| missed | `d007245` | S01 | 0.908527 | 1 |
| missed | `d007343` | S08 | 0.864696 | 5 |
| missed | `d007341` | S08 | 0.453008 | 5 |
| missed | `d007364` | S08 | 0.151426 | 5 |

### Missed and false warnings, `test_diagnostic`

| Outcome | Draft | Scenario | Email risk score | Recipients |
| --- | --- | --- | --- | --- |
| missed | `d007283` | S02 | 0.999649 | 2 |
| missed | `d007289` | S02 | 0.99926 | 2 |
| missed | `d007279` | S02 | 0.999124 | 2 |
| missed | `d007285` | S02 | 0.999073 | 2 |
| missed | `d007325` | S11 | 0.998983 | 1 |
| missed | `d007291` | S02 | 0.998977 | 2 |
| missed | `d007287` | S02 | 0.998315 | 2 |
| missed | `d007323` | S11 | 0.998016 | 1 |
| missed | `d007339` | S11 | 0.997788 | 1 |
| missed | `d007273` | S02 | 0.997428 | 2 |
| missed | `d007329` | S11 | 0.996471 | 1 |
| missed | `d007335` | S11 | 0.996327 | 1 |
| missed | `d007300` | S04 | 0.994767 | 1 |
| missed | `d007281` | S02 | 0.994512 | 2 |
| missed | `d007312` | S04 | 0.993472 | 1 |
| missed | `d007316` | S04 | 0.992851 | 1 |
| missed | `d007308` | S04 | 0.991482 | 1 |
| missed | `d007337` | S11 | 0.990187 | 1 |
| missed | `d007306` | S04 | 0.988874 | 1 |
| missed | `d007247` | S01 | 0.987939 | 1 |
| missed | `d007253` | S01 | 0.987197 | 1 |
| missed | `d007321` | S11 | 0.986662 | 1 |
| missed | `d007265` | S01 | 0.986486 | 1 |
| missed | `d007259` | S01 | 0.986002 | 1 |
| missed | `d007331` | S11 | 0.985793 | 1 |
| missed | `d007310` | S04 | 0.984506 | 1 |
| missed | `d007314` | S04 | 0.98415 | 1 |
| missed | `d007302` | S04 | 0.981768 | 1 |
| missed | `d007298` | S04 | 0.981 | 1 |
| missed | `d007275` | S02 | 0.98077 | 2 |
| missed | `d007327` | S11 | 0.978226 | 1 |
| missed | `d007333` | S11 | 0.977378 | 1 |
| missed | `d007261` | S01 | 0.956124 | 1 |
| missed | `d007304` | S04 | 0.952933 | 1 |
| missed | `d007251` | S01 | 0.937339 | 1 |
| missed | `d007263` | S01 | 0.93553 | 1 |
| missed | `d013483` | S01 | 0.93355 | 1 |
| missed | `d007249` | S01 | 0.909625 | 1 |
| missed | `d007255` | S01 | 0.835985 | 1 |
| missed | `d007382` | S08 | 0.774611 | 5 |
| missed | `d007257` | S01 | 0.772351 | 1 |
| missed | `d007366` | S08 | 0.163814 | 5 |
| missed | `d013487` | S11 | 0.154617 | 1 |
| missed | `d007348` | S08 | 0.146225 | 5 |
| missed | `d007370` | S08 | 0.14373 | 5 |
| missed | `d007374` | S08 | 0.0937008 | 5 |
| missed | `d007352` | S08 | 0.0625282 | 5 |
| missed | `d007356` | S08 | 0.0580693 | 5 |
| missed | `d007360` | S08 | 0.0487103 | 5 |
| missed | `d007344` | S08 | 0.0360904 | 5 |
| missed | `d013488` | S04 | 0.000148529 | 1 |

## Note on the single test pass

This is inspection after the one test pass. It does not permit moving the cutoff. Across `test_product_like` and `test_diagnostic`, missed mistakes by scenario: S01 17, S02 13, S04 16, S08 12, S11 14. Warned mistakes by scenario: S02 4, S08 29, S09 13. False warnings: 0. Scenarios warned on test but never warned on validation: none. Scenarios missed on test and never warned on validation: S01, S04, S11.

## Synthetic shortcuts

Read every recall figure in this phase next to these limits of the synthetic data and the frozen scorer:

- **Content signal.** The scorer uses all features, content cosine included. On train, content cosine alone separates mistakes from ordinary mail with separation 0.932 (the eligibility audit flags a feature only beyond 0.95). The same-family behavior-only model has product-like validation email average precision 0.467 against 0.831 for the scorer. S01, S04, and S11 outcomes by subset: `validation_product_like`: S01 0 of 4 warned, S04 0 of 4 warned, S11 0 of 2 warned; `validation_diagnostic`: S01 0 of 10 warned, S04 0 of 10 warned, S11 0 of 10 warned; `test_product_like`: S01 0 of 6 warned, S04 0 of 5 warned, S11 0 of 3 warned; `test_diagnostic`: S01 0 of 11 warned, S04 0 of 11 warned, S11 0 of 11 warned. The drafts are listed in the [error analysis](ERROR_ANALYSIS.md).
- **Five-minute recency.** 0 of 4948 legitimate recipient rows on `validation_product_like` had earlier mail between the sender and that recipient under five minutes before the draft; 1 of 22 unintended rows did.
- **First contacts.** Rewriting the 22 unintended `validation_product_like` rows as first contacts (no pair history, no pair text) moves their median risk score from 0.9940 to 0.9986; 9 are flagged as stored and 9 after the rewrite. The 30 intended first-contact rows reach a highest risk score of 0.99737, just below `T_warn`, and none is flagged. Legitimate first contacts are among the highest-scoring legitimate rows; the high cutoff, not the score, keeps them allowed.
- **Few positives.** `validation_product_like` has 20 misdirected emails and `test_product_like` has 30. Recall intervals are wide.
- **Weak regularization.** The scorer is logistic regression with `C = 1000`, the top edge of its training grid. Coefficients on overlapping counts are not separate effects.
