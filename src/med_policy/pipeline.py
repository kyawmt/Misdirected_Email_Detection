"""Policy selection on validation, and the one-shot frozen test evaluation.

`run_selection` reads validation only and writes `policy.json` before any
test label is read. `run_frozen_evaluation` refuses to run without that file,
refuses to run twice, computes test features in memory, and never fits.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from med_data.calendar import FROZEN_SUBSETS
from med_features.schema import FEATURE_SPEC_VERSION
from med_models.data import sha256_file, verify_feature_artifact
from med_models.package import load_model
from med_models.version import MODEL_VERSION
from med_policy.decision import load_bundle
from med_policy.evaluate import (
    examples,
    first_contact_check,
    operating_point,
    outcome_list,
    prevalence_table,
    ranking_summary,
    recency_burst,
    reliability_bins,
    slices,
)
from med_policy.scoring import in_memory_table, published_table
from med_policy.select import email_scores, select_cutoff
from med_policy.version import (
    BUDGET_PER_1000,
    DIAGNOSTIC_SUBSET,
    N_BOOTSTRAP,
    POLICY_VERSION,
    SEED,
    SELECTION_SUBSET,
    TEST_SUBSETS,
    PolicyError,
)

POLICY_FILE = "policy.json"
VALIDATION_SCORES_FILE = "validation_scores.csv"
VALIDATION_EVALUATION_FILE = "validation_evaluation.json"
TEST_EVALUATION_FILE = "test_evaluation.json"
LATENCY_FILE = "latency.json"

BUDGET_DEFINITION = {
    "intervention": "a warn or a simulated block, counted once per email",
    "rate": "false interventions per 1,000 legitimate emails",
    "denominator": "all legitimate emails in the evaluation subset",
    "recall_denominator": "all misdirected emails in the evaluation subset; an unassessed positive is not a detection",
    "budget_per_1000": BUDGET_PER_1000,
}


def run_selection(features_dir: Path, data_dir: Path, model_path: Path, out_dir: Path) -> dict:
    """Choose T_warn on validation_product_like and write the policy artifacts."""
    out_dir = Path(out_dir)
    if (out_dir / TEST_EVALUATION_FILE).exists():
        raise PolicyError(
            f"{TEST_EVALUATION_FILE} exists. The policy was already evaluated on the frozen test and cannot be reselected."
        )
    verify_feature_artifact(features_dir)
    model = load_model(model_path)
    product = published_table(features_dir, data_dir, model, SELECTION_SUBSET)
    diagnostic = published_table(features_dir, data_dir, model, DIAGNOSTIC_SUBSET)
    product_emails = email_scores(product)
    selection = select_cutoff(product_emails, SELECTION_SUBSET)
    rules_selection = select_cutoff(email_scores(product, "rules_score"), SELECTION_SUBSET)
    t_warn = selection["chosen"]["cutoff"]
    point = operating_point(product, t_warn)

    out_dir.mkdir(parents=True, exist_ok=True)
    policy = {
        "policy_version": POLICY_VERSION,
        "model_version": MODEL_VERSION,
        "model_run_name": model.metadata["run_name"],
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "dataset_version": model.metadata["dataset_version"],
        "T_warn": t_warn,
        "blocking_enabled": False,
        "T_block": None,
        "scores_are": "risk_scores",
        "calibration": "not_fit",
        "calibration_reason": (
            "validation_product_like has 5 misdirected emails, too few to fit or to split for a calibrator. "
            "validation_diagnostic is not the operating mix and train fit the model. A reliability table on "
            "validation_diagnostic is a shape check only."
        ),
        "decision_rule": {
            "email_risk": "maximum recipient risk score",
            "allow": "email_risk < T_warn",
            "warn": "email_risk >= T_warn (equality warns)",
            "block": "disabled",
            "flagged_recipients": "every recipient with risk score >= T_warn",
        },
        "selection": {
            "subset": SELECTION_SUBSET,
            "level": "email",
            "rule": (
                "Candidates are the distinct email risk scores on the subset plus one cutoff above every score. "
                "Keep candidates with 0 false interventions, maximize email recall, break ties with the highest cutoff."
            ),
            "n_candidates": selection["n_candidates"],
            "zero_false_intervention_candidates": selection["zero_false_intervention_candidates"],
            "chosen": selection["chosen"],
            "tied_candidates": selection["tied_candidates"],
            "highest_legitimate_email_risk": selection["highest_legitimate_email_risk"],
            "recall_is_zero": selection["recall_is_zero"],
        },
        "budget": BUDGET_DEFINITION,
        "validation_confusion": {
            "email": {key: point["email"][key] for key in ("n", "positives", "legitimate", "true_positives", "false_positives", "false_negatives", "true_negatives")},
            "recipient": {key: point["recipient"][key] for key in ("n", "positives", "true_positives", "false_positives", "false_negatives", "true_negatives")},
            "warnings": point["interventions"]["warnings"],
            "blocks": 0,
        },
        "checksums": {
            "model.joblib": sha256_file(Path(model_path)),
            "artifact_manifest.json": sha256_file(Path(features_dir) / "artifact_manifest.json"),
        },
        "test_subsets_used": False,
        "statement": "Selected on validation_product_like only. test_product_like and test_diagnostic were not read.",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _write_json(out_dir / POLICY_FILE, policy)
    write_validation_scores(product_emails, t_warn, out_dir / VALIDATION_SCORES_FILE)

    subjects = _subjects(data_dir, (SELECTION_SUBSET, DIAGNOSTIC_SUBSET))
    evaluation = {
        "policy_version": POLICY_VERSION,
        "T_warn": t_warn,
        "rules_same_budget": {"cutoff": rules_selection["chosen"]["cutoff"], "selection": rules_selection},
        "subsets": {
            SELECTION_SUBSET: evaluate_subset(product, t_warn, rules_selection["chosen"]["cutoff"], subjects),
            DIAGNOSTIC_SUBSET: evaluate_subset(diagnostic, t_warn, rules_selection["chosen"]["cutoff"], subjects),
        },
        "reliability_validation_diagnostic": reliability_bins(diagnostic),
        "examples_validation": {
            SELECTION_SUBSET: examples(product, t_warn, subjects),
            DIAGNOSTIC_SUBSET: examples(diagnostic, t_warn, subjects),
        },
        "bootstrap": {"n_resamples": N_BOOTSTRAP, "seed": SEED, "unit": "family_id"},
    }
    _write_json(out_dir / VALIDATION_EVALUATION_FILE, evaluation)
    return {"policy": policy, "evaluation": evaluation}


def write_validation_scores(emails: pd.DataFrame, t_warn: float, path: Path) -> None:
    """Write the selection table with the decision computed from the in-memory floats.

    `warned` is the audit of each decision. A reader need not reparse
    `email_risk` exactly to reproduce the operating point.
    """
    table = emails.loc[:, ["draft_id", "family_id", "email_risk", "positive"]].rename(columns={"positive": "misdirected"})
    table["warned"] = emails["email_risk"].to_numpy(dtype=np.float64) >= t_warn
    table.to_csv(path, index=False, float_format="%.17g")


def refresh_validation_scores(features_dir: Path, data_dir: Path, model_path: Path, out_dir: Path) -> dict:
    """Rewrite validation_scores.csv under the existing policy. Never touches policy.json.

    Recomputes the validation email scores from the published matrix and
    refuses unless they reproduce the stored cutoff's confusion counts.
    """
    out_dir = Path(out_dir)
    policy_path = out_dir / POLICY_FILE
    if not policy_path.exists():
        raise PolicyError(f"{policy_path} is missing")
    before = sha256_file(policy_path)
    bundle = load_bundle(policy_path, model_path, Path(features_dir) / "artifact_manifest.json")
    table = published_table(features_dir, data_dir, bundle.model, SELECTION_SUBSET)
    emails = email_scores(table)
    point = operating_point(table, bundle.t_warn)
    stored = bundle.policy["validation_confusion"]["email"]
    for key in ("n", "positives", "true_positives", "false_positives", "false_negatives", "true_negatives"):
        if point["email"][key] != stored[key]:
            raise PolicyError(f"Recomputed validation {key} {point['email'][key]} does not match policy.json {stored[key]}")
    write_validation_scores(emails, bundle.t_warn, out_dir / VALIDATION_SCORES_FILE)
    if sha256_file(policy_path) != before:
        raise PolicyError("policy.json changed during the refresh")
    return {"rows": int(len(emails)), "warned": int((emails["email_risk"] >= bundle.t_warn).sum())}


def evaluate_subset(table: pd.DataFrame, t_warn: float, rules_cutoff: float, subjects: dict) -> dict:
    point = operating_point(table, t_warn)
    return {
        "policy": point,
        "rules_same_budget": operating_point(table, rules_cutoff, score_column="rules_score"),
        "always_allow": operating_point(table, None),
        "ranking": ranking_summary(table, t_warn),
        "rules_ranking": ranking_summary(table, rules_cutoff, score_column="rules_score"),
        "slices": slices(table, t_warn),
        "prevalence": prevalence_table(point),
        "first_contact": first_contact_check(table, t_warn),
        "recency_burst": recency_burst(table),
        "outcomes": outcome_list(table, t_warn, subjects),
    }


def run_frozen_evaluation(policy_dir: Path, model_path: Path, features_dir: Path, data_dir: Path) -> dict:
    """Score test_product_like and test_diagnostic once under the frozen policy."""
    policy_dir = Path(policy_dir)
    out = policy_dir / TEST_EVALUATION_FILE
    if out.exists():
        raise PolicyError(f"{out} already exists. The frozen test is evaluated once.")
    policy_path = policy_dir / POLICY_FILE
    if not policy_path.exists():
        raise PolicyError(f"{policy_path} is missing. Select the policy on validation first.")
    validation_path = policy_dir / VALIDATION_EVALUATION_FILE
    if not validation_path.exists():
        raise PolicyError(f"{validation_path} is missing. Rerun selection on validation first.")
    policy_sha = sha256_file(policy_path)
    bundle = load_bundle(policy_path, model_path, Path(features_dir) / "artifact_manifest.json")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    if validation["T_warn"] != bundle.t_warn:
        raise PolicyError("validation_evaluation.json does not match the policy cutoff")
    rules_cutoff = validation["rules_same_budget"]["cutoff"]
    if tuple(TEST_SUBSETS) != tuple(FROZEN_SUBSETS):
        raise PolicyError("Frozen subset names do not match the dataset calendar")

    table, failures = in_memory_table(Path(features_dir), Path(data_dir), bundle.model, TEST_SUBSETS)
    subjects = _subjects(data_dir, TEST_SUBSETS)
    result = {
        "policy_version": bundle.policy["policy_version"],
        "policy_sha256": policy_sha,
        "T_warn": bundle.t_warn,
        "rules_same_budget_cutoff": rules_cutoff,
        "blocking_enabled": False,
        "features": "computed in memory with the saved transformer; no feature file written",
        "fit_calls": "none",
        "scoring_failures": failures,
        "subsets": {
            subset: evaluate_subset(table.loc[table["subset"] == subset], bundle.t_warn, rules_cutoff, subjects)
            for subset in TEST_SUBSETS
        },
        "bootstrap": {"n_resamples": N_BOOTSTRAP, "seed": SEED, "unit": "family_id"},
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if sha256_file(policy_path) != policy_sha:
        raise PolicyError("policy.json changed during the frozen evaluation")
    payload = json.dumps(_ready(result), indent=2) + "\n"
    with open(out, "x", encoding="utf-8") as handle:
        handle.write(payload)
    return result


def _subjects(data_dir: Path, subsets: tuple[str, ...]) -> dict[str, str]:
    drafts = pd.read_csv(Path(data_dir) / "drafts.csv", usecols=["draft_id", "subject", "subset"], keep_default_na=False)
    drafts = drafts.loc[drafts["subset"].isin(list(subsets))]
    return dict(zip(drafts["draft_id"].astype(str), drafts["subject"].astype(str), strict=True))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(_ready(payload), indent=2) + "\n", encoding="utf-8")


def _ready(value):
    if isinstance(value, dict):
        return {str(key): _ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, np.bool_):
        return bool(value)
    return value
