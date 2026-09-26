"""Metrics for a fixed cutoff on a scored table.

Every rate carries its numerator and denominator. Intervals are:

- a family-cluster bootstrap (1,000 draws, seed 20260926) with the 2.5 and
  97.5 percentiles, and the number of draws kept
- an exact Clopper–Pearson binomial interval, which treats emails as
  independent. That holds on product-like subsets, where each family has one
  draft. A zero count still has a positive upper bound this way; the
  bootstrap of a zero count is always [0, 0].
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import beta
from sklearn.metrics import average_precision_score, precision_recall_curve

from med_policy.select import email_scores
from med_policy.version import BUDGET_PER_1000, N_BOOTSTRAP, PREVALENCES, SEED

FIVE_MINUTES_DAYS = 5 / 1440


def clopper_pearson(successes: int, trials: int, level: float = 0.95) -> dict | None:
    if trials <= 0:
        return None
    alpha = 1 - level
    low = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    high = 1.0 if successes == trials else float(beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    return {"low": low, "high": high, "method": "clopper_pearson", "level": level}


def family_bootstrap(families: np.ndarray, stat, *, n_resamples: int = N_BOOTSTRAP, seed: int = SEED) -> dict:
    """Resample family clusters. `stat(index)` returns a value or None to skip the draw."""
    rng = np.random.default_rng(seed)
    unique, inverse = np.unique(families, return_inverse=True)
    groups = [np.flatnonzero(inverse == position) for position in range(len(unique))]
    values = []
    for _ in range(n_resamples):
        chosen = rng.integers(0, len(groups), size=len(groups))
        index = np.concatenate([groups[item] for item in chosen])
        value = stat(index)
        if value is not None:
            values.append(value)
    result = {"n_resamples": n_resamples, "n_kept": len(values), "seed": seed, "unit": "family_id"}
    if values:
        result["low"] = float(np.percentile(values, 2.5))
        result["high"] = float(np.percentile(values, 97.5))
    return result


def operating_point(table: pd.DataFrame, cutoff: float | None, *, score_column: str = "risk_score") -> dict:
    """Email and recipient counts at one cutoff. `cutoff=None` is always-allow."""
    emails = email_scores(table, score_column)
    assessed = emails["assessed"].to_numpy(dtype=bool)
    risk = emails["email_risk"].to_numpy(dtype=np.float64)
    positive = emails["positive"].to_numpy(dtype=bool)
    if cutoff is None:
        warned = np.zeros(len(emails), dtype=bool)
    else:
        warned = assessed & (np.nan_to_num(risk, nan=-np.inf) >= cutoff)
    n_pos = int(positive.sum())
    n_neg = int((~positive).sum())
    tp = int((warned & positive).sum())
    fp = int((warned & ~positive).sum())
    fn = n_pos - tp
    tn = n_neg - fp

    rows = table.loc[table["assessed"]]
    row_scores = rows[score_column].to_numpy(dtype=np.float64)
    row_positive = rows["positive"].to_numpy(dtype=bool)
    flagged = np.zeros(len(rows), dtype=bool) if cutoff is None else row_scores >= cutoff
    attributed_drafts = set(rows.loc[flagged & row_positive, "draft_id"])
    positive_drafts = emails.loc[positive, "draft_id"]
    attributed = int(positive_drafts.isin(attributed_drafts).sum())

    families = emails["family_id"].to_numpy()

    def fi_rate(index):
        neg = ~positive[index]
        if neg.sum() == 0:
            return None
        return float((warned[index] & neg).sum() / neg.sum() * 1000)

    def recall(index):
        pos = positive[index]
        if pos.sum() == 0:
            return None
        return float((warned[index] & pos).sum() / pos.sum())

    fi_exact = clopper_pearson(fp, n_neg)
    return {
        "cutoff": cutoff,
        "score_column": score_column,
        "email": {
            "n": int(len(emails)),
            "positives": n_pos,
            "legitimate": n_neg,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "recall": tp / n_pos if n_pos else None,
            "precision": tp / (tp + fp) if (tp + fp) else None,
            "recall_interval_exact": clopper_pearson(tp, n_pos),
            "recall_interval_bootstrap": family_bootstrap(families, recall),
        },
        "recipient": {
            "n": int(len(rows)),
            "positives": int(row_positive.sum()),
            "true_positives": int((flagged & row_positive).sum()),
            "false_positives": int((flagged & ~row_positive).sum()),
            "false_negatives": int((~flagged & row_positive).sum()),
            "true_negatives": int((~flagged & ~row_positive).sum()),
            "recall": float((flagged & row_positive).sum() / row_positive.sum()) if row_positive.sum() else None,
        },
        "attribution": {
            "misdirected_emails": n_pos,
            "with_unintended_recipient_flagged": attributed,
            "fraction": attributed / n_pos if n_pos else None,
        },
        "interventions": {
            "warnings": int(warned.sum()),
            "blocks": 0,
            "false_interventions": fp,
            "legitimate_emails": n_neg,
            "per_1000_legitimate": fp / n_neg * 1000 if n_neg else None,
            "interval_per_1000_exact": _scaled(fi_exact, 1000),
            "interval_per_1000_bootstrap": family_bootstrap(families, fi_rate),
            "budget_per_1000": BUDGET_PER_1000,
            "zero_count_upper_per_1000": _scaled(clopper_pearson(0, n_neg), 1000)["high"] if n_neg else None,
        },
        "coverage": {
            "emails": int(len(emails)),
            "assessed": int(assessed.sum()),
            "fraction": float(assessed.mean()) if len(emails) else None,
        },
    }


def ranking_summary(table: pd.DataFrame, cutoff: float | None, *, score_column: str = "risk_score") -> dict:
    """Average precision and the precision–recall curve, with the cutoff marked."""
    emails = email_scores(table, score_column)
    emails = emails.loc[emails["assessed"]]
    y = emails["positive"].to_numpy(dtype=bool)
    s = emails["email_risk"].to_numpy(dtype=np.float64)
    rows = table.loc[table["assessed"]]
    ry = rows["positive"].to_numpy(dtype=bool)
    rs = rows[score_column].to_numpy(dtype=np.float64)
    out = {"email": _curve(y, s, cutoff), "recipient": _curve(ry, rs, cutoff)}
    families = emails["family_id"].to_numpy()

    def ap(index):
        yy = y[index]
        if yy.all() or not yy.any():
            return None
        return float(average_precision_score(yy, s[index]))

    out["email"]["average_precision_bootstrap"] = family_bootstrap(families, ap)
    return out


def _curve(y: np.ndarray, s: np.ndarray, cutoff: float | None) -> dict:
    if y.sum() == 0 or (~y).sum() == 0:
        return {"average_precision": None, "points": [], "marked": None}
    precision, recall, thresholds = precision_recall_curve(y, s)
    points = [
        {"recall": float(r), "precision": float(p), "threshold": float(t) if i < len(thresholds) else None}
        for i, (p, r, t) in enumerate(zip(precision, recall, list(thresholds) + [np.nan]))
    ]
    marked = None
    if cutoff is not None:
        warned = s >= cutoff
        tp = int((warned & y).sum())
        marked = {
            "recall": tp / int(y.sum()),
            "precision": tp / int(warned.sum()) if warned.sum() else None,
        }
    return {
        "average_precision": float(average_precision_score(y, s)),
        "positives": int(y.sum()),
        "n": int(len(y)),
        "points": points,
        "marked": marked,
    }


def slices(table: pd.DataFrame, cutoff: float | None, *, score_column: str = "risk_score") -> dict:
    """Intervention counts by recipient and email slice. Every cell has its count."""
    rows = table.loc[table["assessed"]].copy()
    flagged = rows[score_column].to_numpy(dtype=np.float64) >= (np.inf if cutoff is None else cutoff)
    rows["flagged"] = flagged
    rows["internal"] = np.where(rows["recipient_is_internal"] == 1, "internal", "external")
    rows["familiarity"] = np.where(rows["recipient_novel_to_sender"] == 1, "new", "familiar")
    emails = email_scores(table, score_column)
    emails["warned"] = emails["assessed"] & (emails["email_risk"].fillna(-np.inf) >= (np.inf if cutoff is None else cutoff))
    emails["band"] = emails["n_recipients"].map(_band)
    emails["unintended_band"] = emails["n_unintended"].map(lambda value: "0" if value == 0 else "1" if value == 1 else "2+")
    return {
        "recipient_by_internal": _recipient_cells(rows, "internal"),
        "recipient_by_familiarity": _recipient_cells(rows, "familiarity"),
        "recipient_by_scenario": _recipient_cells(rows, "scenario_id"),
        "email_by_recipient_count": _email_cells(emails, "band"),
        "email_by_unintended_count": _email_cells(emails, "unintended_band"),
        "email_by_scenario": _email_cells(emails, "scenario_id"),
    }


def _recipient_cells(rows: pd.DataFrame, column: str) -> list[dict]:
    cells = []
    for key, group in rows.groupby(column, sort=True):
        pos = group["positive"].to_numpy(dtype=bool)
        flag = group["flagged"].to_numpy(dtype=bool)
        cells.append(
            {
                "slice": str(key),
                "rows": int(len(group)),
                "unintended": int(pos.sum()),
                "intended": int((~pos).sum()),
                "flagged_unintended": int((flag & pos).sum()),
                "flagged_intended": int((flag & ~pos).sum()),
            }
        )
    return cells


def _email_cells(emails: pd.DataFrame, column: str) -> list[dict]:
    cells = []
    for key, group in emails.groupby(column, sort=True):
        pos = group["positive"].to_numpy(dtype=bool)
        warned = group["warned"].to_numpy(dtype=bool)
        cells.append(
            {
                "slice": str(key),
                "emails": int(len(group)),
                "misdirected": int(pos.sum()),
                "legitimate": int((~pos).sum()),
                "warned_misdirected": int((warned & pos).sum()),
                "warned_legitimate": int((warned & ~pos).sum()),
                "families": int(group["family_id"].nunique()),
            }
        )
    return cells


def _band(count: int) -> str:
    count = int(count)
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 4:
        return "3-4"
    return "5+"


def prevalence_table(point: dict) -> list[dict]:
    """Precision at assumed prevalences from the product-like TPR and FPR at the cutoff."""
    email = point["email"]
    interventions = point["interventions"]
    tpr = email["recall"]
    fpr = email["false_positives"] / email["legitimate"] if email["legitimate"] else None
    fpr_upper = interventions["interval_per_1000_exact"]["high"] / 1000 if interventions["interval_per_1000_exact"] else None
    rows = []
    for prevalence in PREVALENCES:
        rows.append(
            {
                "prevalence": prevalence,
                "precision_point": _precision(tpr, fpr, prevalence),
                "precision_at_fpr_upper": _precision(tpr, fpr_upper, prevalence),
                "tpr": tpr,
                "fpr_point": fpr,
                "fpr_upper": fpr_upper,
            }
        )
    return rows


def _precision(tpr, fpr, prevalence):
    if tpr is None or fpr is None:
        return None
    numerator = tpr * prevalence
    denominator = numerator + fpr * (1 - prevalence)
    return numerator / denominator if denominator else None


def reliability_bins(table: pd.DataFrame, *, n_bins: int = 10) -> list[dict]:
    """Recipient risk score against observed frequency. A shape check only; nothing is fit."""
    rows = table.loc[table["assessed"]]
    scores = rows["risk_score"].to_numpy(dtype=np.float64)
    positive = rows["positive"].to_numpy(dtype=bool)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out = []
    for index in range(n_bins):
        low, high = edges[index], edges[index + 1]
        mask = (scores >= low) & ((scores < high) if index < n_bins - 1 else (scores <= high))
        count = int(mask.sum())
        out.append(
            {
                "bin_low": float(low),
                "bin_high": float(high),
                "rows": count,
                "mean_risk_score": float(scores[mask].mean()) if count else None,
                "observed_unintended_fraction": float(positive[mask].mean()) if count else None,
            }
        )
    return out


def first_contact_check(table: pd.DataFrame, cutoff: float) -> dict:
    """Score each unintended row as stored and as a first contact, against the cutoff."""
    rows = table.loc[table["assessed"] & table["positive"]]
    before = rows["risk_score"].to_numpy(dtype=np.float64)
    after = rows["risk_score_as_first_contact"].to_numpy(dtype=np.float64)
    novel_legit = table.loc[table["assessed"] & ~table["positive"] & (table["recipient_novel_to_sender"] == 1)]
    return {
        "unintended_rows": int(len(rows)),
        "median_before": float(np.median(before)) if len(before) else None,
        "median_after": float(np.median(after)) if len(after) else None,
        "flagged_before": int((before >= cutoff).sum()),
        "flagged_after_rewrite": int((after >= cutoff).sum()),
        "novel_intended_rows": int(len(novel_legit)),
        "novel_intended_max_score": float(novel_legit["risk_score"].max()) if len(novel_legit) else None,
        "novel_intended_flagged": int((novel_legit["risk_score"] >= cutoff).sum()),
    }


def recency_burst(table: pd.DataFrame) -> dict:
    rows = table.loc[table["assessed"]]
    days = rows["pair_recency_days"].to_numpy(dtype=np.float64)
    positive = rows["positive"].to_numpy(dtype=bool)
    legit = days[~positive]
    mis = days[positive]
    return {
        "legitimate_rows": int(len(legit)),
        "legitimate_under_5_minutes": int((legit < FIVE_MINUTES_DAYS).sum()),
        "unintended_rows": int(len(mis)),
        "unintended_under_5_minutes": int((mis < FIVE_MINUTES_DAYS).sum()),
    }


def examples(table: pd.DataFrame, cutoff: float, subjects: dict[str, str]) -> dict:
    """Named examples: an allowed ordinary email, a warned and a missed mistake, a legitimate first contact."""
    emails = email_scores(table)
    emails = emails.loc[emails["assessed"]].copy()
    emails["decision"] = np.where(emails["email_risk"] >= cutoff, "warn", "allow")
    novel_drafts = set(table.loc[(table["recipient_novel_to_sender"] == 1) & ~table["positive"], "draft_id"])

    def pick(frame: pd.DataFrame, order: str):
        if frame.empty:
            return None
        frame = frame.sort_values(["email_risk", "draft_id"], ascending=[order == "asc", True])
        row = frame.iloc[len(frame) // 2] if order == "mid" else frame.iloc[0]
        return {
            "draft_id": row["draft_id"],
            "scenario_id": row["scenario_id"],
            "email_risk": float(row["email_risk"]),
            "decision": row["decision"],
            "misdirected": bool(row["positive"]),
            "n_recipients": int(row["n_recipients"]),
            "subject": _short(subjects.get(row["draft_id"], "")),
        }

    ordinary = emails.loc[~emails["positive"] & (emails["decision"] == "allow") & emails["scenario_id"].isin(["S05", "routine"])]
    warned = emails.loc[emails["positive"] & (emails["decision"] == "warn")]
    missed = emails.loc[emails["positive"] & (emails["decision"] == "allow")]
    first = emails.loc[~emails["positive"] & emails["draft_id"].isin(novel_drafts)]
    return {
        "allowed_ordinary": pick(ordinary, "mid"),
        "warned_mistake": pick(warned, "asc"),
        "missed_mistake": pick(missed, "desc"),
        "legitimate_first_contact": pick(first, "desc"),
    }


def outcome_list(table: pd.DataFrame, cutoff: float, subjects: dict[str, str]) -> dict:
    """Every missed mistake and every false warning, for inspection only."""
    emails = email_scores(table)
    emails = emails.loc[emails["assessed"]]
    warned = emails["email_risk"] >= cutoff

    def rows(frame):
        return [
            {
                "draft_id": row.draft_id,
                "scenario_id": row.scenario_id,
                "email_risk": float(row.email_risk),
                "n_recipients": int(row.n_recipients),
                "subject": _short(subjects.get(row.draft_id, "")),
            }
            for row in frame.sort_values("email_risk", ascending=False).itertuples(index=False)
        ]

    return {
        "missed_mistakes": rows(emails.loc[emails["positive"] & ~warned]),
        "false_warnings": rows(emails.loc[~emails["positive"] & warned]),
        "warned_mistakes": rows(emails.loc[emails["positive"] & warned]),
    }


def _short(text: str, limit: int = 48) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _scaled(interval: dict | None, factor: float) -> dict | None:
    if interval is None:
        return None
    return {**interval, "low": interval["low"] * factor, "high": interval["high"] * factor}
