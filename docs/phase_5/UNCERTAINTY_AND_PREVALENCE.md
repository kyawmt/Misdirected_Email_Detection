# Phase 5 — Uncertainty and prevalence

## Interval methods

- **Family bootstrap.** 1000 draws, seed 20260926, resampling `family_id` clusters of emails; the 2.5 and 97.5 percentiles are reported with the number of draws kept. Diagnostic families contain several drafts, so only this interval respects their dependence. A zero false-intervention count bootstraps to [0, 0] in every draw, which is not an upper bound, so the diagnostic false-intervention rate has no valid upper bound in this report. The diagnostic recall bootstrap is still reported.
- **Exact binomial (Clopper–Pearson).** Used for the false-intervention rate and recall on product-like subsets, where each family has one draft and emails are independent. It gives a positive upper bound for a zero count. The AC01 strong claim uses this upper bound.

## The sample-size limit on AC01

| Subset | Legitimate emails | One false warning, per 1,000 | False warnings | Rate per 1,000 | Exact upper 95% | Upper 95% if zero |
| --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` | 3980 | 0.251 | 0 | 0.00 | 0.93 | 0.93 |
| `test_product_like` | 5970 | 0.168 | 0 | 0.00 | 0.62 | 0.62 |

The budget is 1 false intervention per 1,000 legitimate emails. A point estimate within the budget is provisional; the strong AC01 claim needs the exact upper bound at or below the budget. With 3980 legitimate emails on `validation_product_like`, zero false warnings give an upper bound of 0.93 per 1,000, within the budget. With 5970 legitimate emails on `test_product_like`, zero false warnings give an upper bound of 0.62 per 1,000, within the budget. Only the `test_product_like` pass counts for AC01, because `validation_product_like` chose the cutoff.

## Prevalence sensitivity

0.5% is a simulation assumption. Precision at the frozen cutoff is computed from the product-like true-positive rate and false-positive rate, at several assumed prevalences. When the observed false-positive rate is 0, point precision is 1.0 at every prevalence, which overstates it; the second column uses the exact upper false-positive rate instead. Neither column is chosen as the result.

### `validation_product_like`

| Prevalence | TPR | FPR | Precision | FPR upper 95% | Precision at FPR upper |
| --- | --- | --- | --- | --- | --- |
| 0.1% | 0.400 | 0.00000 | 1.000 | 0.00093 | 0.302 |
| 0.5% | 0.400 | 0.00000 | 1.000 | 0.00093 | 0.685 |
| 1.0% | 0.400 | 0.00000 | 1.000 | 0.00093 | 0.813 |
| 2.0% | 0.400 | 0.00000 | 1.000 | 0.00093 | 0.898 |

### `test_product_like`

| Prevalence | TPR | FPR | Precision | FPR upper 95% | Precision at FPR upper |
| --- | --- | --- | --- | --- | --- |
| 0.1% | 0.300 | 0.00000 | 1.000 | 0.00062 | 0.327 |
| 0.5% | 0.300 | 0.00000 | 1.000 | 0.00062 | 0.709 |
| 1.0% | 0.300 | 0.00000 | 1.000 | 0.00062 | 0.831 |
| 2.0% | 0.300 | 0.00000 | 1.000 | 0.00062 | 0.908 |

Diagnostic-set rates are not product-like prevalence results and are not used in this table. Train precision at the 10% training mix is not an operating point.
