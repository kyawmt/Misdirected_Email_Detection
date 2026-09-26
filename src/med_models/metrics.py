"""Threshold-free metrics at recipient and email level.

Email risk is the maximum recipient score. Bootstrap resamples family_id
clusters. A resample without both classes is skipped and counted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from med_models.version import N_BOOTSTRAP, SEED


def email_table(audit: pd.DataFrame, scores: np.ndarray) -> pd.DataFrame:
    """One row per draft: max score, any-positive label, family, and scenario."""
    table = audit.loc[:, ["draft_id", "family_id", "scenario_id", "sent_at"]].copy()
    table["score"] = scores
    table["positive"] = audit["positive"].to_numpy()
    if "addressed_recipient_count" in audit.columns:
        table["addressed_recipient_count"] = audit["addressed_recipient_count"].to_numpy()
    grouped = table.groupby("draft_id", sort=False)
    emails = grouped.agg(
        family_id=("family_id", "first"),
        scenario_id=("scenario_id", "first"),
        sent_at=("sent_at", "first"),
        score=("score", "max"),
        positive=("positive", "any"),
        n_recipients=("score", "size"),
    )
    if "addressed_recipient_count" in table.columns:
        emails["addressed_recipient_count"] = grouped["addressed_recipient_count"].first()
    else:
        emails["addressed_recipient_count"] = emails["n_recipients"]
    return emails.reset_index()


def ranking_metrics(y_true: np.ndarray, scores: np.ndarray) -> dict:
    y_true = np.asarray(y_true).astype(bool)
    scores = np.asarray(scores, dtype=np.float64)
    positives = int(y_true.sum())
    negatives = int((~y_true).sum())
    result = {
        "n": int(len(y_true)),
        "positives": positives,
        "negatives": negatives,
        "average_precision": None,
        "roc_auc": None,
    }
    if positives == 0 or negatives == 0:
        return result
    result["average_precision"] = float(average_precision_score(y_true, scores))
    result["roc_auc"] = _roc(y_true, scores)
    return result


def bootstrap_metrics(
    family_ids: np.ndarray,
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    n_resamples: int = N_BOOTSTRAP,
    seed: int = SEED,
) -> dict:
    point = ranking_metrics(y_true, scores)
    rng = np.random.default_rng(seed)
    families = np.unique(family_ids)
    groups = [np.flatnonzero(family_ids == family) for family in families]
    ap_draws = []
    roc_draws = []
    skipped = 0
    n_families = len(groups)
    for _ in range(n_resamples):
        chosen = rng.integers(0, n_families, size=n_families)
        y_parts = [y_true[groups[index]] for index in chosen]
        s_parts = [scores[groups[index]] for index in chosen]
        y_boot = np.concatenate(y_parts)
        s_boot = np.concatenate(s_parts)
        if np.unique(y_boot.astype(bool)).size < 2:
            skipped += 1
            continue
        ap_draws.append(float(average_precision_score(y_boot, s_boot)))
        roc_draws.append(_roc(y_boot, s_boot))
    point["bootstrap"] = {
        "n_resamples": n_resamples,
        "n_used": len(ap_draws),
        "n_skipped": skipped,
        "seed": seed,
        "average_precision": _interval(ap_draws),
        "roc_auc": _interval([value for value in roc_draws if value is not None]),
    }
    return point


def recipient_view(audit: pd.DataFrame, scores: np.ndarray) -> dict:
    return bootstrap_metrics(
        audit["family_id"].to_numpy(),
        audit["positive"].to_numpy(),
        np.asarray(scores, dtype=np.float64),
    )


def email_view(emails: pd.DataFrame) -> dict:
    return bootstrap_metrics(
        emails["family_id"].to_numpy(),
        emails["positive"].to_numpy(),
        emails["score"].to_numpy(dtype=np.float64),
    )


def breakdowns(audit: pd.DataFrame, scores: np.ndarray, emails: pd.DataFrame) -> dict:
    """Sampled slices. Rates here are descriptive, not an operating point."""
    recipient = audit.copy()
    recipient["score"] = scores
    recipient["recipient_count_bin"] = recipient["addressed_recipient_count"].map(_count_bin)
    recipient["internal"] = np.where(recipient["recipient_is_internal"].to_numpy() == 1, "internal", "external")
    recipient["familiarity"] = np.where(
        recipient["recipient_novel_to_sender"].to_numpy() == 1, "new", "familiar"
    )
    email = emails.copy()
    email["recipient_count_bin"] = email["addressed_recipient_count"].map(_count_bin)
    return {
        "recipient_by_scenario": _group_metrics(recipient, "scenario_id"),
        "recipient_by_count": _group_metrics(recipient, "recipient_count_bin"),
        "recipient_by_internal": _group_metrics(recipient, "internal"),
        "recipient_by_familiarity": _group_metrics(recipient, "familiarity"),
        "email_by_scenario": _group_metrics(email, "scenario_id", score_column="score"),
        "email_by_count": _group_metrics(email, "recipient_count_bin", score_column="score"),
    }


def _group_metrics(frame: pd.DataFrame, column: str, score_column: str | None = None) -> list[dict]:
    rows = []
    for key, group in frame.groupby(column, sort=True):
        scores = group["score"].to_numpy() if score_column else group["score"].to_numpy()
        metrics = ranking_metrics(group["positive"].to_numpy(), scores)
        metrics["slice"] = str(key)
        rows.append(metrics)
    return rows


def _count_bin(value: int) -> str:
    count = int(value)
    if count <= 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def _roc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    if np.unique(scores).size < 2:
        return 0.5
    return float(roc_auc_score(y_true, scores))


def _interval(values: list[float]) -> dict | None:
    if not values:
        return None
    array = np.asarray(values, dtype=np.float64)
    return {
        "low": float(np.percentile(array, 2.5)),
        "high": float(np.percentile(array, 97.5)),
    }
