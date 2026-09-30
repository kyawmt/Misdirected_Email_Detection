"""Reviewed feedback: sources, a simulated review of a sampled queue, and efficacy.

Three rules hold throughout.

1. A click is not a label. `POST /feedback` lines are unreviewed by definition.
   Only a reviewer record with status `accepted` can change an effective label,
   and this module changes no stored label at all.
2. Nothing here retrains, recalibrates, or moves the cutoff. It reads the
   policy and model files only to record that their checksums did not change.
3. Efficacy (recall, false interventions) is computed only from labels a
   reviewer returned, with the counts and denominators shown.

Today the real reviewed evidence is nearly empty: the dataset's
`reviewer_feedback.csv` holds three train rows and none is accepted, and the
API feedback file holds unreviewed clicks with no draft link or assessment
timestamp. The review of the replay queue is therefore a *simulation*: the
simulated reviewer answers each queued email with the dataset's stipulated
label after a seeded delay. Its delays and its 100% return rate are
assumptions, not measurements.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import beta

from med_monitor.data import read_api_feedback, read_labels, read_reviewer_feedback
from med_monitor.version import (
    API_FEEDBACK_PATH,
    MONITOR_VERSION,
    PERFORMANCE_HORIZON_DAYS,
    PLAN_SEED,
    REVIEW_CONFIDENCE,
    REVIEW_DELAY_SCALE_DAYS,
    REVIEW_DELAY_SHAPE,
    REVIEW_HORIZONS_DAYS,
    WARNED_STRATUM,
)

ACCEPTED = "accepted"


def delay_days(window: int, position: int) -> float:
    """Seeded reviewer delay for one queued email, in days. Depends on window and position only."""
    rng = np.random.default_rng([PLAN_SEED, 3, window, position])
    return float(rng.gamma(REVIEW_DELAY_SHAPE, REVIEW_DELAY_SCALE_DAYS))


def clopper_pearson(k: int, n: int, confidence: float = REVIEW_CONFIDENCE) -> tuple[float, float]:
    """Exact binomial interval for k events in n trials."""
    if n <= 0:
        return 0.0, 1.0
    alpha = 1 - confidence
    low = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    high = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return low, high


def stratum_count(population: int, reviewed: int, mistakes: int) -> dict:
    """Mistakes in one stratum: confirmed ones plus an estimate for the emails not reviewed.

    The unreviewed emails are unknown, not zero. A stratum with nothing reviewed
    has no estimate and an interval from the confirmed count to the population.
    """
    unreviewed = population - reviewed
    if reviewed == 0:
        return {"estimate": None, "low": float(mistakes), "high": float(population), "reviewed": 0, "mistakes": mistakes, "population": population}
    rate_low, rate_high = clopper_pearson(mistakes, reviewed)
    return {
        "estimate": mistakes + unreviewed * mistakes / reviewed,
        "low": mistakes + unreviewed * rate_low,
        "high": mistakes + unreviewed * rate_high,
        "reviewed": reviewed,
        "mistakes": mistakes,
        "population": population,
    }


def recall_interval(warned: dict, allowed: list[dict]) -> dict:
    """Recall of the warning policy from a stratified review.

    Recall is confirmed-warned mistakes over all mistakes, where the mistakes
    among allowed emails are estimated from the sampled strata. The interval adds
    the per-stratum 95% intervals, so it is conservative and not simultaneous.
    """
    if any(item["estimate"] is None for item in [warned, *allowed]):
        return {"estimate": None, "low": None, "high": None, "note": "A stratum has no returned labels at this horizon."}
    tp, fn = warned["estimate"], sum(item["estimate"] for item in allowed)
    tp_low, tp_high = warned["low"], warned["high"]
    fn_low, fn_high = sum(item["low"] for item in allowed), sum(item["high"] for item in allowed)

    def ratio(hit: float, miss: float) -> float:
        return hit / (hit + miss) if hit + miss > 0 else float("nan")

    return {
        "estimate": ratio(tp, fn),
        "low": ratio(tp_low, fn_high),
        "high": ratio(tp_high, fn_low),
        "note": "Conservative: per-stratum 95% Clopper-Pearson intervals added together, not simultaneous.",
    }


def review_block(items: list[dict], population: dict[str, int], misdirected: dict[str, bool], delays: dict[tuple, float], horizon: float, assessed: int) -> dict:
    """Efficacy from the labels returned within `horizon` days, for one block of windows."""
    returned = [item for item in items if delays[(item["window"], item["position"])] <= horizon]
    by_stratum: dict[str, dict] = {}
    for name, size in population.items():
        chosen = [item for item in returned if item["stratum"] == name]
        by_stratum[name] = stratum_count(size, len(chosen), sum(misdirected[item["draft_id"]] for item in chosen))
        by_stratum[name]["queued"] = sum(1 for item in items if item["stratum"] == name)
    warned = by_stratum.get(WARNED_STRATUM) or stratum_count(0, 0, 0)
    allowed = [value for name, value in by_stratum.items() if name != WARNED_STRATUM]
    confirmed = sum(value["mistakes"] for value in by_stratum.values())
    reviewed_total = sum(value["reviewed"] for value in by_stratum.values())
    warned_reviewed = warned["reviewed"]
    false_warned = warned_reviewed - warned["mistakes"]
    naive = None if warned["mistakes"] == 0 else 1.0
    mistakes_hat = sum(value["estimate"] for value in by_stratum.values() if value["estimate"] is not None)
    legit_hat = assessed - mistakes_hat
    return {
        "assessed_emails": assessed,
        "queued": len(items),
        "returned": len(returned),
        "label_coverage_of_assessed": len(returned) / assessed if assessed else None,
        "warned": {
            "population": warned["population"],
            "reviewed": warned_reviewed,
            "confirmed_misdirected": warned["mistakes"],
            "confirmed_all_intended": false_warned,
            "coverage": warned_reviewed / warned["population"] if warned["population"] else None,
        },
        "strata": {name: value for name, value in sorted(by_stratum.items())},
        "positives_confirmed": confirmed,
        "reviewed_total": reviewed_total,
        "recall": recall_interval(warned, allowed),
        "false_interventions": {
            "confirmed": false_warned,
            "of_reviewed_warned": warned_reviewed,
            "legitimate_emails_estimated": legit_hat if warned["estimate"] is not None and all(v["estimate"] is not None for v in allowed) else None,
            "note": "Confirmed false interventions are a lower bound while warned emails are still unreviewed.",
        },
        "warned_only_view": {
            "recall_if_only_warned_emails_were_reviewed": naive,
            "why_biased": "No allowed email is reviewed, so no missed mistake can be observed; the denominator drops every miss.",
        },
    }


def api_feedback_summary(path: Path, expected_versions: dict) -> dict:
    """Click feedback: counts only. Every line is unreviewed and cannot be tied to a draft."""
    lines = read_api_feedback(path)
    labels = Counter(item.get("label") for item in lines)
    matching = sum(all(item.get(name) == value for name, value in expected_versions.items()) for item in lines)
    received = sorted(item["received_at"] for item in lines if "received_at" in item)
    return {
        "path": str(path),
        "lines": len(lines),
        "distinct_assessments": len({item.get("request_id") for item in lines}),
        "distinct_contacts": len({item.get("contact_id") for item in lines}),
        "labels": dict(sorted(labels.items())),
        "lines_for_the_served_bundle": matching,
        "first_received": received[0] if received else None,
        "last_received": received[-1] if received else None,
        "reviewed": 0,
        "review_status": "unreviewed: a click is a request for review, not a label",
        "label_delay": "not computable: neither the log line nor the feedback line carries an assessment time",
        "linkable_to_a_draft": False,
    }


def dataset_feedback_summary(data_dir: Path) -> dict:
    """Reviewer rows of the published dataset about non-frozen drafts."""
    frame = read_reviewer_feedback(data_dir)
    statuses = Counter(zip(frame["subset"], frame["review_status"], strict=True))
    return {
        "file": "reviewer_feedback.csv",
        "rows_about_non_frozen_drafts": int(len(frame)),
        "by_subset_and_status": {f"{subset}/{status}": count for (subset, status), count in sorted(statuses.items())},
        "accepted": int((frame["review_status"] == ACCEPTED).sum()),
        "about_validation_drafts": int(frame["subset"].str.startswith("validation").sum()),
        "note": "Illustrative rows. None is accepted and none concerns a validation draft, so none is a reviewed label for the monitored traffic.",
    }


def apply_accepted_reviews(stipulated: dict[tuple[str, str], bool], reviews: list[dict]) -> dict[tuple[str, str], bool]:
    """Effective recipient labels. Only an `accepted` review with an asserted bit changes a label.

    Pending and rejected reviews and every click leave the stipulated label as it is.
    """
    effective = dict(stipulated)
    for review in reviews:
        if review.get("review_status") != ACCEPTED:
            continue
        asserted = str(review.get("asserted_intended", "")).lower()
        key = (review["draft_id"], review["contact_id"])
        if asserted in ("true", "false") and key in effective:
            effective[key] = asserted == "true"
    return effective


def file_checksums(paths: dict[str, Path]) -> dict[str, str]:
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in paths.items()}


def summarize(replay: dict, data_dir: Path, *, policy_path: Path, model_path: Path, feedback_path: Path = API_FEEDBACK_PATH) -> dict:
    """Build the stored feedback record: sources, simulated queue outcomes, and efficacy by horizon."""
    watched = {"policy.json": policy_path, "model.joblib": model_path}
    before = file_checksums(watched)
    queue = replay["review_queue"]
    items = queue["items"]
    misdirected = read_labels(data_dir, {item["draft_id"] for item in items})
    delays = {(item["window"], item["position"]): delay_days(item["window"], item["position"]) for item in items}
    blocks = {"reference": set(replay["blocks"]["reference"]["windows"]), "current": set(replay["blocks"]["current"]["windows"])}
    population = queue["population"]
    by_horizon = {}
    for horizon in REVIEW_HORIZONS_DAYS:
        sides = {}
        for role, windows in blocks.items():
            role_items = [item for item in items if item["window"] in windows]
            merged: Counter = Counter()
            for number in windows:
                merged.update(population[str(number)])
            assessed = replay["blocks"][role]["summary"]["assessed"]
            sides[role] = review_block(role_items, dict(merged), misdirected, delays, horizon, assessed)
        by_horizon[str(horizon)] = sides
    ordered = sorted(delays.values())
    delay_summary = {
        "queued": len(ordered),
        "median_days": float(np.percentile(ordered, 50)) if ordered else None,
        "p90_days": float(np.percentile(ordered, 90)) if ordered else None,
        "max_days": float(ordered[-1]) if ordered else None,
        "distribution": f"gamma(shape={REVIEW_DELAY_SHAPE}, scale={REVIEW_DELAY_SCALE_DAYS} days), seeded per queued email",
    }
    served = {"model_version": replay["bundle"]["model_version"], "feature_spec_version": replay["bundle"]["feature_spec_version"], "policy_version": replay["bundle"]["policy_version"]}
    after = file_checksums(watched)
    return {
        "monitor_version": MONITOR_VERSION,
        "kind": "feedback_review",
        "plan_checksum": replay["plan_checksum"],
        "real_reviewed_labels": {
            "api_feedback": api_feedback_summary(feedback_path, served),
            "dataset_reviewer_feedback": dataset_feedback_summary(data_dir),
            "reviewed_labels_on_monitored_traffic": 0,
        },
        "simulation": {
            "label_source": "simulated reviewer: the stipulated label of each queued validation draft, returned after a seeded delay",
            "assumptions": "Every queued email is answered; delays are gamma-distributed; the reviewer is always right. These are assumptions.",
            "queue_policy": queue["strata"],
            "delay": delay_summary,
        },
        "efficacy": {
            "comparison_horizon_days": PERFORMANCE_HORIZON_DAYS,
            "horizons_days": list(REVIEW_HORIZONS_DAYS),
            "by_horizon": by_horizon,
        },
        "labels_changed_by_feedback": 0,
        "effective_label_rule": "Only a reviewer record with status accepted and an asserted bit changes a recipient label; clicks, pending, and rejected records change nothing.",
        "policy_and_model_unchanged": before == after,
        "checksums": {"before": before, "after": after},
        "queue_items": [
            {"window": item["window"], "position": item["position"], "draft_id": item["draft_id"], "decision": item["decision"], "stratum": item["stratum"], "delay_days": round(delays[(item["window"], item["position"])], 3), "misdirected": misdirected[item["draft_id"]]}
            for item in items
        ],
    }


def dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
