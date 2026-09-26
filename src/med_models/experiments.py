"""Recorded Phase 4 runs.

Hyperparameters are chosen by mean email-level average precision on expanding
chronological folds inside train. Each chosen configuration is then fit on all
of train and scored once on each validation subset.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from med_models.data import load_model_table, model_matrix
from med_models.estimators import AlwaysAllow, FusionModel, LogisticModel, RulesModel, TreeModel
from med_models.folds import assign_folds, expanding_tests
from med_models.groups import ABLATIONS, C_GRID, TREE_GRID, ablation_columns
from med_models.metrics import breakdowns, email_table, email_view, ranking_metrics, recipient_view
from med_models.version import SEED

SIMPLICITY = {"rules": 0, "logistic": 1, "tree": 2}


def run_experiments(features_dir: Path, data_dir: Path) -> dict:
    train_frame, train_audit = _prepare(features_dir, data_dir, "train")
    product_frame, product_audit = _prepare(features_dir, data_dir, "validation_product_like")
    diagnostic_frame, diagnostic_audit = _prepare(features_dir, data_dir, "validation_diagnostic")
    draft_folds = assign_folds(train_audit)
    boundaries = list(draft_folds.attrs["boundaries"])
    runs = []
    fitted = {}

    runs.append(_static_run("always_allow", AlwaysAllow(), "none", train_frame, train_audit, product_frame, product_audit, diagnostic_frame, diagnostic_audit, draft_folds))
    runs.append(_static_run("rules", RulesModel(), "behavior_only", train_frame, train_audit, product_frame, product_audit, diagnostic_frame, diagnostic_audit, draft_folds))
    runs.append(_static_run("fusion", FusionModel(), "fusion", train_frame, train_audit, product_frame, product_audit, diagnostic_frame, diagnostic_audit, draft_folds))

    for ablation in ABLATIONS:
        columns = ablation_columns(ablation)
        for class_weight in (None, "balanced"):
            chosen, grid = _tune_logistic(train_frame, train_audit, draft_folds, columns, class_weight)
            weight_name = "balanced" if class_weight == "balanced" else "unweighted"
            model = LogisticModel(columns, chosen["C"], class_weight)
            run = _fit_and_score(
                name=f"logistic_{ablation}_{weight_name}",
                kind="logistic",
                ablation=ablation,
                model=model,
                columns=columns,
                config={"C": chosen["C"], "class_weight": weight_name},
                tuning={"selected": chosen, "grid": grid},
                train_frame=train_frame,
                train_audit=train_audit,
                product_frame=product_frame,
                product_audit=product_audit,
                diagnostic_frame=diagnostic_frame,
                diagnostic_audit=diagnostic_audit,
            )
            runs.append(run)
            fitted[run["name"]] = model
        chosen_tree, tree_grid = _tune_tree(train_frame, train_audit, draft_folds, columns)
        tree = TreeModel(columns, chosen_tree["max_depth"], chosen_tree["min_samples_leaf"])
        run = _fit_and_score(
            name=f"tree_{ablation}",
            kind="tree",
            ablation=ablation,
            model=tree,
            columns=columns,
            config=chosen_tree,
            tuning={"selected": chosen_tree, "grid": tree_grid},
            train_frame=train_frame,
            train_audit=train_audit,
            product_frame=product_frame,
            product_audit=product_audit,
            diagnostic_frame=diagnostic_frame,
            diagnostic_audit=diagnostic_audit,
        )
        runs.append(run)
        fitted[run["name"]] = tree

    behavior_columns = ablation_columns("behavior_only")
    chosen_floor, floor_grid = _tune_logistic(
        train_frame, train_audit, draft_folds, behavior_columns, None, recency_floor_days=1.0
    )
    floor_model = LogisticModel(behavior_columns, chosen_floor["C"], None, recency_floor_days=1.0)
    floor_run = _fit_and_score(
        name="logistic_behavior_recency_floor_unweighted",
        kind="logistic",
        ablation="behavior_recency_floor",
        model=floor_model,
        columns=behavior_columns,
        config={"C": chosen_floor["C"], "class_weight": "unweighted", "recency_floor_days": 1.0},
        tuning={"selected": chosen_floor, "grid": floor_grid},
        train_frame=train_frame,
        train_audit=train_audit,
        product_frame=product_frame,
        product_audit=product_audit,
        diagnostic_frame=diagnostic_frame,
        diagnostic_audit=diagnostic_audit,
    )
    runs.append(floor_run)
    fitted[floor_run["name"]] = floor_model
    rate_columns = [column for column in behavior_columns if column != "pair_outbound_rate_per_day"]
    chosen_rate, rate_grid = _tune_logistic(train_frame, train_audit, draft_folds, rate_columns, None)
    rate_model = LogisticModel(rate_columns, chosen_rate["C"], None)
    rate_run = _fit_and_score(
        name="logistic_behavior_drop_rate_unweighted",
        kind="logistic",
        ablation="behavior_drop_rate",
        model=rate_model,
        columns=rate_columns,
        config={"C": chosen_rate["C"], "class_weight": "unweighted", "dropped": "pair_outbound_rate_per_day"},
        tuning={"selected": chosen_rate, "grid": rate_grid},
        train_frame=train_frame,
        train_audit=train_audit,
        product_frame=product_frame,
        product_audit=product_audit,
        diagnostic_frame=diagnostic_frame,
        diagnostic_audit=diagnostic_audit,
    )
    runs.append(rate_run)
    fitted[rate_run["name"]] = rate_model

    for run in runs:
        if run["name"] in fitted:
            continue
        if run["name"] == "rules":
            fitted[run["name"]] = RulesModel()
        elif run["name"] == "fusion":
            fitted[run["name"]] = FusionModel()
        elif run["name"] == "always_allow":
            fitted[run["name"]] = AlwaysAllow()
    selected_name = _select(runs)
    return {
        "seed": SEED,
        "folds": boundaries,
        "runs": runs,
        "selected": selected_name,
        "fitted": fitted,
        "train_rows": int(len(train_frame)),
        "train_positive_rows": int(train_audit["positive"].sum()),
        "train_positive_emails": int(train_audit.groupby("draft_id")["positive"].any().sum()),
        "recency_shortcut": {
            "train": _recency_shortcut(train_frame, train_audit),
            "validation_product_like": _recency_shortcut(product_frame, product_audit),
        },
    }


def _prepare(features_dir: Path, data_dir: Path, subset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame, audit = load_model_table(features_dir, data_dir, subset)
    audit = audit.copy()
    audit["addressed_recipient_count"] = frame["addressed_recipient_count"].to_numpy()
    audit["recipient_is_internal"] = frame["recipient_is_internal"].to_numpy()
    audit["recipient_novel_to_sender"] = frame["recipient_novel_to_sender"].to_numpy()
    return frame.reset_index(drop=True), audit.reset_index(drop=True)


def _tune_logistic(frame, audit, draft_folds, columns, class_weight, recency_floor_days=None) -> tuple[dict, list[dict]]:
    best = None
    grid = []
    for C in C_GRID:
        started = time.perf_counter()
        summary = _cv_email_ap(
            frame,
            audit,
            draft_folds,
            lambda C=C: LogisticModel(columns, C, class_weight, recency_floor_days=recency_floor_days),
        )
        summary["C"] = C
        summary["seconds"] = time.perf_counter() - started
        grid.append(summary)
        if best is None or summary["mean"] > best["mean"]:
            best = summary
    return {"C": best["C"], "mean": best["mean"]}, _compact_grid(grid)


def _tune_tree(frame, audit, draft_folds, columns) -> tuple[dict, list[dict]]:
    best = None
    grid = []
    for config in TREE_GRID:
        started = time.perf_counter()
        summary = _cv_email_ap(
            frame,
            audit,
            draft_folds,
            lambda config=config: TreeModel(columns, config["max_depth"], config["min_samples_leaf"]),
        )
        summary.update(config)
        summary["seconds"] = time.perf_counter() - started
        grid.append(summary)
        if best is None or summary["mean"] > best["mean"]:
            best = summary
    chosen = {"max_depth": best["max_depth"], "min_samples_leaf": best["min_samples_leaf"], "mean": best["mean"]}
    return chosen, _compact_grid(grid)


def _cv_email_ap(frame, audit, draft_folds, factory) -> dict:
    folds = []
    for test_fold, train_ids, test_ids in expanding_tests(draft_folds):
        train_mask = audit["draft_id"].isin(set(train_ids))
        test_mask = audit["draft_id"].isin(set(test_ids))
        model = factory()
        y_train = audit.loc[train_mask, "positive"].to_numpy()
        if np.unique(y_train.astype(int)).size < 2:
            folds.append(
                {
                    "fold": test_fold,
                    "average_precision": None,
                    "positives": int(y_train.sum()),
                    "n": int(len(y_train)),
                    "skipped": "single_class_train",
                }
            )
            continue
        matrix = model_matrix(frame.loc[train_mask], model.columns)
        model.fit(matrix, y_train)
        scores = model.predict(model_matrix(frame.loc[test_mask], model.columns))
        emails = email_table(audit.loc[test_mask].reset_index(drop=True), scores)
        metrics = ranking_metrics(emails["positive"].to_numpy(), emails["score"].to_numpy())
        folds.append(
            {
                "fold": test_fold,
                "average_precision": metrics["average_precision"],
                "positives": metrics["positives"],
                "n": metrics["n"],
            }
        )
    values = [item["average_precision"] for item in folds if item["average_precision"] is not None]
    return {
        "folds": folds,
        "mean": float(np.mean(values)) if values else float("-inf"),
        "std": float(np.std(values)) if values else None,
        "n_folds_scored": len(values),
    }


def _static_run(name, model, ablation, train_frame, train_audit, product_frame, product_audit, diagnostic_frame, diagnostic_audit, draft_folds):
    columns = ablation_columns("behavior_only") if name == "rules" else ablation_columns("all")
    if name == "always_allow":
        columns = ablation_columns("behavior_only")
    cv = _static_cv(model, train_frame, train_audit, draft_folds, columns)
    return _score_fitted(
        name=name,
        kind=model.kind,
        ablation=ablation,
        model=model,
        columns=columns,
        config={},
        tuning={"cv": cv},
        train_frame=train_frame,
        train_audit=train_audit,
        product_frame=product_frame,
        product_audit=product_audit,
        diagnostic_frame=diagnostic_frame,
        diagnostic_audit=diagnostic_audit,
        fit_seconds=0.0,
    )


def _static_cv(model, frame, audit, draft_folds, columns) -> dict:
    folds = []
    for test_fold, _train_ids, test_ids in expanding_tests(draft_folds):
        test_mask = audit["draft_id"].isin(set(test_ids))
        scores = model.predict(model_matrix(frame.loc[test_mask], columns))
        emails = email_table(audit.loc[test_mask].reset_index(drop=True), scores)
        metrics = ranking_metrics(emails["positive"].to_numpy(), emails["score"].to_numpy())
        folds.append(
            {
                "fold": test_fold,
                "average_precision": metrics["average_precision"],
                "positives": metrics["positives"],
                "n": metrics["n"],
            }
        )
    values = [item["average_precision"] for item in folds if item["average_precision"] is not None]
    return {
        "folds": folds,
        "mean": float(np.mean(values)) if values else None,
        "std": float(np.std(values)) if values else None,
        "n_folds_scored": len(values),
    }


def _fit_and_score(name, kind, ablation, model, columns, config, tuning, train_frame, train_audit, product_frame, product_audit, diagnostic_frame, diagnostic_audit):
    started = time.perf_counter()
    model.fit(model_matrix(train_frame, columns), train_audit["positive"].to_numpy())
    fit_seconds = time.perf_counter() - started
    cv = {"mean": tuning["selected"].get("mean"), "std": None, "folds": []}
    for item in tuning["grid"]:
        if _same_config(kind, item, config):
            cv = {"mean": item["mean"], "std": item["std"], "folds": item["folds"], "n_folds_scored": item["n_folds_scored"]}
    tuning = {"selected_cv_mean": cv["mean"], "grid": [_public_grid_row(kind, row) for row in tuning["grid"]]}
    return _score_fitted(
        name=name,
        kind=kind,
        ablation=ablation,
        model=model,
        columns=columns,
        config=config,
        tuning={"cv": cv, "grid": tuning["grid"]},
        train_frame=train_frame,
        train_audit=train_audit,
        product_frame=product_frame,
        product_audit=product_audit,
        diagnostic_frame=diagnostic_frame,
        diagnostic_audit=diagnostic_audit,
        fit_seconds=fit_seconds,
    )


def _score_fitted(name, kind, ablation, model, columns, config, tuning, train_frame, train_audit, product_frame, product_audit, diagnostic_frame, diagnostic_audit, fit_seconds):
    product = _evaluate(model, product_frame, product_audit, columns)
    diagnostic = _evaluate(model, diagnostic_frame, diagnostic_audit, columns)
    cv = tuning.get("cv", {})
    return {
        "name": name,
        "kind": kind,
        "ablation": ablation,
        "features": list(columns),
        "n_features": len(columns),
        "config": _json_ready(config),
        "simplicity": SIMPLICITY.get(kind, 9),
        "eligible": kind in SIMPLICITY and ablation == "behavior_only",
        "cv": _json_ready(cv),
        "tuning_grid": tuning.get("grid", []),
        "fit_seconds": fit_seconds,
        "validation_product_like": product,
        "validation_diagnostic": diagnostic,
        "novelty": _json_ready(model.novelty()) if hasattr(model, "novelty") else {"available": False},
        "recency_fill_days": _json_ready(getattr(getattr(model, "scaler", None), "recency_fill_", None)),
        "first_contact_contrast": _json_ready(_contrasts(model, columns, product_frame, product_audit, diagnostic_frame, diagnostic_audit))
        if kind == "logistic" and "recipient_novel_to_sender" in columns
        else None,
    }


def _evaluate(model, frame, audit, columns) -> dict:
    matrix = model_matrix(frame, columns)
    started = time.perf_counter()
    scores = model.predict(matrix)
    elapsed = time.perf_counter() - started
    emails = email_table(audit, scores)
    result = {
        "recipient": recipient_view(audit, scores),
        "email": email_view(emails),
        "breakdowns": breakdowns(audit, scores, emails),
        "score_seconds": elapsed,
        "score_seconds_per_1000_rows": elapsed / max(len(frame), 1) * 1000,
    }
    if getattr(model, "kind", "") == "tree":
        result["score_support"] = _score_support(scores, audit["positive"].to_numpy())
    return result


def _select(runs: list[dict]) -> str:
    candidates = [run for run in runs if run["eligible"]]
    if not candidates:
        raise RuntimeError("No behavior-only model was eligible for selection")
    best = max(candidates, key=lambda run: _email_ap(run))
    interval = best["validation_product_like"]["email"]["bootstrap"]["average_precision"]
    within = []
    for run in candidates:
        point = _email_ap(run)
        if interval is None or (interval["low"] <= point <= interval["high"]) or run["name"] == best["name"]:
            within.append(run)
    within.sort(key=lambda run: (run["simplicity"], -_cv_mean(run), run["name"]))
    return within[0]["name"]


def _cv_mean(run: dict) -> float:
    value = (run.get("cv") or {}).get("mean")
    return float(value) if value is not None else float("-inf")


def _contrasts(model, columns, product_frame, product_audit, diagnostic_frame, diagnostic_audit) -> dict:
    return {
        "validation_product_like": _first_contact_contrast(model, product_frame, product_audit, columns),
        "validation_diagnostic": _first_contact_contrast(model, diagnostic_frame, diagnostic_audit, columns),
    }


def _first_contact_contrast(model, frame, audit, columns) -> dict:
    """Score each row as stored and again as a first contact for this sender."""
    original = model.predict(model_matrix(frame, columns))
    altered = frame.copy()
    for name, value in (
        ("pair_outbound_count", 0),
        ("pair_inbound_count", 0),
        ("pair_outbound_count_28d", 0),
        ("pair_inbound_count_28d", 0),
        ("pair_outbound_rate_per_day", 0.0),
        ("pair_recency_days", 3650.0),
        ("pair_recency_observed", 0),
        ("recipient_novel_to_sender", 1),
        ("co_joint_message_count", 0),
        ("co_partner_fraction", 0.0),
        ("co_focus_conditional_fraction", 0.0),
        ("co_focus_history_available", 0),
    ):
        if name in altered.columns:
            altered[name] = value
    rewritten = model.predict(model_matrix(altered, columns))
    positive = audit["positive"].to_numpy()
    return {
        "n": int(len(original)),
        "n_positive": int(positive.sum()),
        "positive_median_before": _median(original[positive]),
        "positive_median_after": _median(rewritten[positive]),
        "negative_median_before": _median(original[~positive]),
        "negative_median_after": _median(rewritten[~positive]),
    }


def _recency_shortcut(frame, audit) -> dict:
    days = frame["pair_recency_days"].to_numpy(dtype=np.float64)
    positive = audit["positive"].to_numpy()
    five_minutes = 5 / 1440
    legit = days[~positive]
    mis = days[positive]
    return {
        "n_legitimate": int((~positive).sum()),
        "n_misdirected": int(positive.sum()),
        "legitimate_share_under_5_minutes": float((legit < five_minutes).mean()) if len(legit) else None,
        "misdirected_share_under_5_minutes": float((mis < five_minutes).mean()) if len(mis) else None,
        "misdirected_min_days": float(mis.min()) if len(mis) else None,
    }


def _score_support(scores: np.ndarray, positive: np.ndarray) -> dict:
    rounded = np.round(np.asarray(scores, dtype=np.float64), 6)
    rows = []
    for value in np.unique(rounded):
        mask = rounded == value
        rows.append({"score": float(value), "n": int(mask.sum()), "n_positive": int(positive[mask].sum())})
    rows.sort(key=lambda item: (-item["n_positive"], -item["n"]))
    return {"n_distinct": len(rows), "buckets_with_positives": [item for item in rows if item["n_positive"]][:5]}


def _median(values: np.ndarray) -> float | None:
    if len(values) == 0:
        return None
    return float(np.median(values))


def _email_ap(run: dict) -> float:
    value = run["validation_product_like"]["email"]["average_precision"]
    return float(value) if value is not None else float("-inf")


def _same_config(kind: str, grid_row: dict, config: dict) -> bool:
    if kind == "logistic":
        return grid_row["C"] == config["C"]
    if kind == "tree":
        return grid_row["max_depth"] == config["max_depth"] and grid_row["min_samples_leaf"] == config["min_samples_leaf"]
    return False


def _compact_grid(rows: list[dict]) -> list[dict]:
    compact = []
    for row in rows:
        item = {key: value for key, value in row.items() if key != "folds"}
        item["folds"] = row["folds"]
        compact.append(item)
    return compact


def _public_grid_row(kind: str, row: dict) -> dict:
    public = {
        "mean_email_average_precision": None if row["mean"] == float("-inf") else row["mean"],
        "std_email_average_precision": row["std"],
        "n_folds_scored": row["n_folds_scored"],
        "folds": row["folds"],
    }
    if kind == "logistic":
        public["C"] = row["C"]
    else:
        public["max_depth"] = row["max_depth"]
        public["min_samples_leaf"] = row["min_samples_leaf"]
    return public


def _json_ready(value):
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if number == float("inf") or number == float("-inf") or number != number:
            return None
        return number
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value
