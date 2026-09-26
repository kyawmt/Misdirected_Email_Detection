"""Load the frozen policy with its model bundle, and decide one draft.

The decision is allow or warn. Blocking is disabled, so `block` is never
returned. A missing or invalid policy, a bundle mismatch, or a scoring
failure yields `unable_to_assess` with no decision and no risk score.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from med_features.schema import FEATURE_SPEC_VERSION, FeatureError
from med_features.transform import transform_draft
from med_models.data import sha256_file
from med_models.package import LoadedModel, load_model
from med_models.version import MODEL_VERSION, ModelError
from med_policy.version import POLICY_VERSION, PolicyError

REQUIRED_KEYS = (
    "policy_version",
    "model_version",
    "feature_spec_version",
    "dataset_version",
    "T_warn",
    "blocking_enabled",
    "T_block",
    "scores_are",
    "calibration",
    "checksums",
    "model_run_name",
)


@dataclass(frozen=True)
class PolicyBundle:
    policy: dict
    model: LoadedModel
    t_warn: float

    @property
    def versions(self) -> dict:
        return {
            "model_version": self.policy["model_version"],
            "feature_spec_version": self.policy["feature_spec_version"],
            "policy_version": self.policy["policy_version"],
        }


def load_bundle(policy_path: Path, model_path: Path, feature_manifest_path: Path) -> PolicyBundle:
    """Load and cross-check the policy, model, and feature manifest. Raises PolicyError."""
    policy_path = Path(policy_path)
    if not policy_path.exists():
        raise PolicyError(f"Policy file {policy_path} does not exist")
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyError(f"Policy file is not readable JSON: {error}") from error
    missing = [key for key in REQUIRED_KEYS if key not in policy]
    if missing:
        raise PolicyError(f"Policy is missing {missing}")
    if policy["policy_version"] != POLICY_VERSION:
        raise PolicyError(f"Policy version {policy['policy_version']} does not match {POLICY_VERSION}")
    if policy["model_version"] != MODEL_VERSION:
        raise PolicyError(f"Policy expects model {policy['model_version']}, installed {MODEL_VERSION}")
    if policy["feature_spec_version"] != FEATURE_SPEC_VERSION:
        raise PolicyError(
            f"Policy expects features {policy['feature_spec_version']}, installed {FEATURE_SPEC_VERSION}"
        )
    if policy["blocking_enabled"] is not False or policy["T_block"] is not None:
        raise PolicyError("Blocking must be disabled with T_block null in this policy version")
    if policy["scores_are"] != "risk_scores" or policy["calibration"] != "not_fit":
        raise PolicyError("Policy must describe uncalibrated risk scores")
    t_warn = policy["T_warn"]
    if isinstance(t_warn, bool) or not isinstance(t_warn, (int, float)) or not math.isfinite(t_warn):
        raise PolicyError("T_warn must be a finite number")
    checksums = policy["checksums"]
    for label, path in (("model.joblib", Path(model_path)), ("artifact_manifest.json", Path(feature_manifest_path))):
        if not path.exists():
            raise PolicyError(f"{label} not found at {path}")
        if sha256_file(path) != checksums.get(label):
            raise PolicyError(f"Checksum mismatch for {label}")
    try:
        model = load_model(Path(model_path))
    except ModelError as error:
        raise PolicyError(str(error)) from error
    if policy.get("model_run_name") != model.metadata.get("run_name"):
        raise PolicyError("Policy names a different model run")
    return PolicyBundle(policy=policy, model=model, t_warn=float(t_warn))


def try_load_bundle(policy_path: Path, model_path: Path, feature_manifest_path: Path) -> tuple[PolicyBundle | None, str | None]:
    """Load the bundle, or return (None, reason) for the caller to report unable_to_assess."""
    try:
        return load_bundle(policy_path, model_path, feature_manifest_path), None
    except PolicyError as error:
        return None, str(error)


def unable_to_assess(reason: str) -> dict:
    return {
        "status": "unable_to_assess",
        "decision": None,
        "email_risk": None,
        "flagged_recipient_ids": [],
        "recipient_scores": [],
        "reason": reason,
    }


def decide(bundle: PolicyBundle | None, recipient_scores: pd.DataFrame, *, reason: str | None = None) -> dict:
    """Decide one assessed draft from its recipient risk scores."""
    if bundle is None:
        return unable_to_assess(reason or "policy_unavailable")
    if recipient_scores is None or len(recipient_scores) == 0:
        return unable_to_assess("no_recipient_scores")
    scores = recipient_scores["risk_score"].to_numpy(dtype=np.float64)
    if not np.isfinite(scores).all():
        return unable_to_assess("non_finite_risk_score")
    email_risk = float(scores.max())
    flagged = [
        str(contact_id)
        for contact_id, score in zip(recipient_scores["contact_id"], scores, strict=True)
        if score >= bundle.t_warn
    ]
    result = {
        "status": "assessed",
        "decision": "warn" if email_risk >= bundle.t_warn else "allow",
        "email_risk": email_risk,
        "flagged_recipient_ids": flagged,
        "recipient_scores": [
            {"contact_id": str(contact_id), "risk_score": float(score)}
            for contact_id, score in zip(recipient_scores["contact_id"], scores, strict=True)
        ],
    }
    result.update(bundle.versions)
    return result


def assess_draft(
    bundle: PolicyBundle | None,
    directory,
    history,
    transformer,
    query,
    *,
    reason: str | None = None,
    include_features: bool = False,
) -> dict:
    """Transform one draft, score it with the frozen model, and apply the policy.

    With `include_features`, the assessed result also carries the feature rows
    under `feature_rows` so a caller can describe evidence limitations without
    transforming the draft twice. The rows never change the decision.
    """
    if bundle is None:
        return unable_to_assess(reason or "policy_unavailable")
    try:
        frame = transform_draft(directory, history, transformer, query)
        scored = frame.loc[:, ["draft_id", "contact_id", "recipient_order"]].copy()
        scored["risk_score"] = bundle.model.score_frame(frame)
    except (FeatureError, ModelError, ValueError) as error:
        return unable_to_assess(f"scoring_failed: {error}")
    result = decide(bundle, scored)
    if include_features and result["status"] == "assessed":
        result["feature_rows"] = frame
    return result
