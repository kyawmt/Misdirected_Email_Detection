"""Warning-threshold search on the product-like validation subset.

Candidates are the distinct email risk scores on that subset plus one cutoff
above every score. Keep the candidates with zero false interventions, maximize
email recall, and break ties with the highest cutoff. Equality warns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from med_policy.version import SELECTION_SUBSET, TEST_SUBSETS, PolicyError


def email_scores(table: pd.DataFrame, score_column: str = "risk_score") -> pd.DataFrame:
    """One row per draft. Email risk is the maximum recipient score."""
    frame = table.copy()
    frame["_score"] = frame[score_column]
    frame["_positive_recipient"] = frame["positive"] & frame["assessed"]
    grouped = frame.groupby("draft_id", sort=False)
    emails = grouped.agg(
        subset=("subset", "first"),
        family_id=("family_id", "first"),
        scenario_id=("scenario_id", "first"),
        email_risk=("_score", "max"),
        positive=("positive", "any"),
        assessed=("assessed", "all"),
        n_recipients=("assessed", "sum"),
        n_unintended=("_positive_recipient", "sum"),
    ).reset_index()
    emails.loc[~emails["assessed"], "email_risk"] = np.nan
    return emails


def candidate_cutoffs(email_risk: np.ndarray) -> list[float]:
    values = np.unique(np.asarray(email_risk, dtype=np.float64))
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise PolicyError("No finite email risk scores to choose a cutoff from")
    above = float(np.nextafter(values.max(), np.inf))
    return [float(value) for value in values] + [above]


def select_cutoff(emails: pd.DataFrame, subset: str) -> dict:
    """Apply the zero-false-intervention, maximum-recall rule to one validation table."""
    if subset in TEST_SUBSETS:
        raise PolicyError(f"Refusing to select a threshold on frozen subset {subset}")
    if subset != SELECTION_SUBSET:
        raise PolicyError(f"Thresholds are selected on {SELECTION_SUBSET} only, not {subset}")
    tags = set(emails["subset"].astype(str))
    if tags != {SELECTION_SUBSET}:
        raise PolicyError(f"Selection table is tagged {sorted(tags)}, expected {SELECTION_SUBSET}")
    if not emails["assessed"].all():
        raise PolicyError("Selection table contains unassessed emails")
    risk = emails["email_risk"].to_numpy(dtype=np.float64)
    positive = emails["positive"].to_numpy(dtype=bool)
    n_pos = int(positive.sum())
    n_neg = int((~positive).sum())
    if n_pos == 0 or n_neg == 0:
        raise PolicyError("Selection table needs both classes")
    rows = []
    for cutoff in candidate_cutoffs(risk):
        warned = risk >= cutoff
        tp = int((warned & positive).sum())
        fp = int((warned & ~positive).sum())
        rows.append(
            {
                "cutoff": cutoff,
                "true_positives": tp,
                "false_interventions": fp,
                "recall": tp / n_pos,
                "warnings": int(warned.sum()),
            }
        )
    zero = [row for row in rows if row["false_interventions"] == 0]
    best_recall = max(row["recall"] for row in zero)
    tied = [row for row in zero if row["recall"] == best_recall]
    chosen = max(tied, key=lambda row: row["cutoff"])
    lowest_positive_free = min(row["cutoff"] for row in rows if row["false_interventions"] == 0)
    return {
        "subset": subset,
        "n_emails": int(len(emails)),
        "n_positive_emails": n_pos,
        "n_legitimate_emails": n_neg,
        "n_candidates": len(rows),
        "chosen": chosen,
        "tied_candidates": tied,
        "zero_false_intervention_candidates": len(zero),
        "lowest_zero_false_intervention_cutoff": lowest_positive_free,
        "highest_legitimate_email_risk": float(risk[~positive].max()),
        "recall_is_zero": best_recall == 0,
    }
