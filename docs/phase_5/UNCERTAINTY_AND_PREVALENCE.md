# Phase 5 — Uncertainty and prevalence

## Interval methods

- **Family bootstrap.** 1000 draws, seed 20260926, resampling `family_id` clusters of emails; the 2.5 and 97.5 percentiles are reported with the number of draws kept. Diagnostic families contain several drafts, so only this interval respects their dependence. A zero false-intervention count bootstraps to [0, 0] in every draw, which is not an upper bound, so the diagnostic false-intervention rate has no valid upper bound in this report. The diagnostic recall bootstrap is still reported.
- **Exact binomial (Clopper–Pearson).** Used for the false-intervention rate and recall on product-like subsets, where each family has one draft and emails are independent. It gives a positive upper bound for a zero count. The AC01 strong claim uses this upper bound.

## The sample-size limit on AC01

| Subset | Legitimate emails | One false warning, per 1,000 | False warnings | Rate per 1,000 | Exact upper 95% | Upper 95% if zero |
| --- | --- | --- | --- | --- | --- | --- |
| `validation_product_like` | 995 | 1.005 | 0 | 0.00 | 3.70 | 3.70 |
| `test_product_like` | 1990 | 0.503 | 0 | 0.00 | 1.85 | 1.85 |

The budget is 1 false intervention per 1,000 legitimate emails. Even zero false warnings on these sample sizes leave the upper bound above it, so the strong AC01 claim cannot be supported by this data. A point estimate within the budget is provisional. The subsets were not enlarged.

## Prevalence sensitivity

0.5% is a simulation assumption. Precision at the frozen cutoff is computed from the product-like true-positive rate and false-positive rate, at several assumed prevalences. When the observed false-positive rate is 0, point precision is 1.0 at every prevalence, which overstates it; the second column uses the exact upper false-positive rate instead. Neither column is chosen as the result.

### `validation_product_like`

| Prevalence | TPR | FPR | Precision | FPR upper 95% | Precision at FPR upper |
| --- | --- | --- | --- | --- | --- |
| 0.1% | 0.800 | 0.00000 | 1.000 | 0.00370 | 0.178 |
| 0.5% | 0.800 | 0.00000 | 1.000 | 0.00370 | 0.521 |
| 1.0% | 0.800 | 0.00000 | 1.000 | 0.00370 | 0.686 |
| 2.0% | 0.800 | 0.00000 | 1.000 | 0.00370 | 0.815 |

### `test_product_like`

| Prevalence | TPR | FPR | Precision | FPR upper 95% | Precision at FPR upper |
| --- | --- | --- | --- | --- | --- |
| 0.1% | 0.500 | 0.00000 | 1.000 | 0.00185 | 0.213 |
| 0.5% | 0.500 | 0.00000 | 1.000 | 0.00185 | 0.576 |
| 1.0% | 0.500 | 0.00000 | 1.000 | 0.00185 | 0.732 |
| 2.0% | 0.500 | 0.00000 | 1.000 | 0.00185 | 0.846 |

Diagnostic-set rates are not product-like prevalence results and are not used in this table. Train precision at the 10% training mix is not an operating point.
