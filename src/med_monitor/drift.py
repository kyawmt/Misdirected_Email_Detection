"""Input drift, decision-rate change, and confirmed performance change.

These are three different questions and they return three separately labeled
findings:

- input drift: do the model inputs look like the training inputs? Uses only
  feature rows, never a score, decision, or label.
- decision-rate change: did the share of emails that warn move? Uses only
  decisions.
- confirmed performance change: did recall or false interventions move among
  emails whose intent a reviewer confirmed? Uses only reviewed labels.

Each one refuses to speak below its minimum sample size and says so.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from med_features.schema import FEATURE_COLUMNS
from med_monitor.reference import assign_bins, bin_counts, unit_values
from med_monitor.version import (
    MIN_EMAILS_DECISION_RATE,
    MIN_EMAILS_INPUT_DRIFT,
    MIN_EXCESS_ROWS,
    MIN_REVIEWED_POSITIVES,
    MIN_ROWS_INPUT_DRIFT,
    PSI_ALERT,
    PSI_PSEUDO_COUNT,
    PSI_WATCH,
    RATE_ALPHA,
    SHARE_SHIFT_ALERT,
    SHARE_SHIFT_WATCH,
)

INSUFFICIENT = "insufficient_sample"
ALERT = "alert"
WATCH = "watch"
OK = "ok"
STRUCTURAL = "structural"
NO_DRIFT = "no_drift_detected"
NO_CHANGE = "no_change_detected"


def psi(reference_counts, current_counts, pseudo: float = PSI_PSEUDO_COUNT) -> float:
    """Population stability index with half a row added to every bin on both sides."""
    ref = np.asarray(reference_counts, dtype=np.float64)
    cur = np.asarray(current_counts, dtype=np.float64)
    if ref.shape != cur.shape:
        raise ValueError("Reference and current bins differ in length")
    p_ref = (ref + pseudo) / (ref.sum() + pseudo * len(ref))
    p_cur = (cur + pseudo) / (cur.sum() + pseudo * len(cur))
    return float(np.sum((p_cur - p_ref) * np.log(p_cur / p_ref)))


def input_drift(reference: dict, frame: pd.DataFrame) -> dict:
    """Compare a window's model inputs with the train reference.

    `frame` holds the window's recipient rows with an `occurrence` column that
    is unique per email in the window (a draft replayed twice is two emails).
    Recipient-level features are counted over rows and draft-level features
    over emails. Below the minimum sample nothing is computed and nothing is
    reported per feature. Cumulative features are reported as structural.
    """
    rows = int(len(frame))
    emails = int(frame["occurrence"].nunique()) if rows else 0
    result = {
        "finding": "input_drift",
        "reference_subset": reference["subset"],
        "reference_rows": reference["rows"],
        "reference_emails": reference["drafts"],
        "rows": rows,
        "emails": emails,
        "min_rows": MIN_ROWS_INPUT_DRIFT,
        "min_emails": MIN_EMAILS_INPUT_DRIFT,
        "thresholds": {
            "psi_watch": PSI_WATCH,
            "psi_alert": PSI_ALERT,
            "share_shift_watch": SHARE_SHIFT_WATCH,
            "share_shift_alert": SHARE_SHIFT_ALERT,
            "min_excess_rows": MIN_EXCESS_ROWS,
        },
    }
    if rows < MIN_ROWS_INPUT_DRIFT or emails < MIN_EMAILS_INPUT_DRIFT:
        result.update(
            status=INSUFFICIENT,
            features=[],
            alert=[],
            watch=[],
            structural=[],
            statement=(
                f"No input-drift statement: {rows} recipient rows and {emails} emails, "
                f"minimum {MIN_ROWS_INPUT_DRIFT} rows and {MIN_EMAILS_INPUT_DRIFT} emails."
            ),
        )
        return result
    missing = [name for name in FEATURE_COLUMNS if name not in frame.columns]
    if missing:
        raise ValueError(f"Window rows are missing model inputs: {missing}")
    features = []
    for name in FEATURE_COLUMNS:
        spec = reference["features"][name]
        values = unit_values(frame, name, "occurrence").astype(np.float64)
        n = int(len(values))
        item = {
            "feature": name,
            "kind": spec["kind"],
            "unit": spec["unit"],
            "n": n,
            "mean_train": spec["mean"],
            "mean_window": float(values.mean()),
        }
        if spec["cumulative"]:
            above = int((values > spec["max"]).sum())
            below = int((values < spec["min"]).sum())
            item.update(
                status=STRUCTURAL,
                psi=None,
                train_min=spec["min"],
                train_max=spec["max"],
                rows_above_train_max=above,
                rows_below_train_min=below,
                share_outside_train_range=(above + below) / n,
            )
        else:
            counts = bin_counts(spec, values)
            expected = np.asarray(spec["counts"], dtype=np.float64) / spec["rows"] * n
            excess = float(np.maximum(counts - expected, 0.0).sum())
            value = psi(spec["counts"], counts)
            unseen = 0
            indicator = spec["kind"] == "discrete" and spec["values"] == [0.0, 1.0]
            if spec["kind"] != "quantile":
                unseen = int((assign_bins(spec, values) == len(spec["values"])).sum())
            shift = abs(item["mean_window"] - spec["mean"]) if indicator else 0.0
            alerting = value >= PSI_ALERT or (indicator and shift >= SHARE_SHIFT_ALERT)
            if alerting and excess >= MIN_EXCESS_ROWS:
                status = ALERT
            elif alerting or value >= PSI_WATCH or unseen > 0 or (indicator and shift >= SHARE_SHIFT_WATCH):
                status = WATCH
            else:
                status = OK
            item.update(status=status, psi=value, excess_rows=excess, unseen_value_rows=unseen)
            if indicator:
                item["share_shift"] = item["mean_window"] - spec["mean"]
        features.append(item)
    ranked = sorted((item for item in features if item["psi"] is not None), key=lambda item: (-item["psi"], item["feature"]))
    alert = [item["feature"] for item in ranked if item["status"] == ALERT]
    watch = [item["feature"] for item in ranked if item["status"] == WATCH]
    structural = [item["feature"] for item in features if item["status"] == STRUCTURAL]
    overall = ALERT if alert else WATCH if watch else NO_DRIFT
    result.update(
        status=overall,
        features=features,
        alert=alert,
        watch=watch,
        structural=structural,
        statement=(
            f"{_features(len(alert))} in the alert band and {len(watch)} in the watch band against the train reference "
            f"({rows} recipient rows, {emails} emails); {_features(len(structural))} cumulative and structural, not scored."
        ),
    )
    return result


def _features(amount: int) -> str:
    return f"{amount} feature" if amount == 1 else f"{amount} features"


def exact_rate_p(reference_k: int, reference_n: int, current_k: int, current_n: int, alternative: str) -> float:
    """Fisher exact test of two counts. `greater` asks whether the current rate is higher."""
    table = [[current_k, current_n - current_k], [reference_k, reference_n - reference_k]]
    return float(fisher_exact(table, alternative=alternative)[1])


def rate_finding(metric: str, reference: dict, current: dict, *, alternative: str, min_n: int, alpha: float = RATE_ALPHA) -> dict:
    """Exact comparison of a count-out-of-emails rate against the reference period.

    `reference` and `current` are {"k": events, "n": emails}. Below `min_n`
    emails on either side no test is run and no p-value is reported.
    """
    result = {
        "metric": metric,
        "alternative": alternative,
        "alpha": alpha,
        "min_n": min_n,
        "reference": {**reference, "rate": _rate(reference)},
        "current": {**current, "rate": _rate(current)},
    }
    if reference["n"] < min_n or current["n"] < min_n:
        result.update(status=INSUFFICIENT, p_value=None)
        return result
    p_value = exact_rate_p(reference["k"], reference["n"], current["k"], current["n"], alternative)
    result.update(status=ALERT if p_value <= alpha else NO_CHANGE, p_value=p_value)
    return result


def _rate(counts: dict) -> float | None:
    return counts["k"] / counts["n"] if counts["n"] else None


def decision_rate_change(reference: dict, current: dict) -> dict:
    """Did the warning rate move? Decisions only; no score, feature, or label is read."""
    finding = rate_finding("warning_rate", reference, current, alternative="two-sided", min_n=MIN_EMAILS_DECISION_RATE)
    finding["finding"] = "decision_rate_change"
    return finding


def performance_change(reference: dict, current: dict) -> dict:
    """Did recall move among reviewed emails? Reviewed labels only.

    Each side is {"positives_confirmed": n, "recall": {"estimate", "low", "high"}}
    from `med_monitor.feedback`. A change is confirmed only when both sides have
    at least `MIN_REVIEWED_POSITIVES` confirmed misdirected emails and their
    conservative intervals do not overlap.
    """
    result = {
        "finding": "confirmed_performance_change",
        "min_reviewed_positives": MIN_REVIEWED_POSITIVES,
        "reference": reference,
        "current": current,
    }
    if reference["positives_confirmed"] < MIN_REVIEWED_POSITIVES or current["positives_confirmed"] < MIN_REVIEWED_POSITIVES:
        result.update(
            status=INSUFFICIENT,
            statement=(
                f"No performance statement: {reference['positives_confirmed']} and {current['positives_confirmed']} "
                f"confirmed misdirected emails, minimum {MIN_REVIEWED_POSITIVES} on each side."
            ),
        )
        return result
    ref, cur = reference["recall"], current["recall"]
    disjoint = cur["high"] < ref["low"] or cur["low"] > ref["high"]
    result.update(
        status=ALERT if disjoint else NO_CHANGE,
        statement="Recall intervals do not overlap." if disjoint else "Recall intervals overlap.",
    )
    return result
