"""The train-only input reference, and the fixed numbers windows are compared with.

Input drift is measured against the training rows of the published feature
artifact (`features_train.csv`). That file's checksum is verified against the
artifact manifest before it is read, and no validation or test feature file is
opened here. Bin edges and bin counts are computed from train alone; they are
descriptive statistics of the training inputs, not a fitted model.

The training subset is enriched to 10% misdirected mail, so the reference
mix of recipients is not the product-like mix. The report states that offset.

No file that holds frozen test results or rows is opened here. The stored test
evaluation lists per-draft test outcomes, so the monitor does not parse it, even
to quote its aggregate. Operating numbers come from the policy file's validation
record, which is validation only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from med_features.schema import FEATURE_COLUMNS
from med_monitor.data import read_features
from med_monitor.version import (
    CUMULATIVE_FEATURES,
    DATASET_VERSION,
    DRAFT_LEVEL_FEATURES,
    FEATURE_SPEC_VERSION,
    MAX_DISCRETE_VALUES,
    MODEL_VERSION,
    MONITOR_VERSION,
    POLICY_VERSION,
    PSI_ALERT,
    PSI_PSEUDO_COUNT,
    PSI_WATCH,
    QUANTILE_BINS,
    REFERENCE_SUBSET,
    SNAPSHOT_ID,
    API_CONTRACT_VERSION,
)

TOLERANCE = 1e-9


class ReferenceError(ValueError):
    """The reference cannot be built or trusted."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_train_path(features_dir: Path) -> tuple[Path, str]:
    """The train feature file, after its checksum matches the artifact manifest."""
    features_dir = Path(features_dir)
    manifest = json.loads((features_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("feature_spec_version") != FEATURE_SPEC_VERSION:
        raise ReferenceError(f"Feature artifact is {manifest.get('feature_spec_version')}, expected {FEATURE_SPEC_VERSION}")
    name = f"features_{REFERENCE_SUBSET}.csv"
    expected = manifest["files"][name]["sha256"]
    path = features_dir / name
    if sha256_of(path) != expected:
        raise ReferenceError(f"Checksum mismatch for {name}")
    return path, expected


def feature_spec(name: str, values: np.ndarray) -> dict:
    """Bins and reference counts for one feature, from train values only.

    `values` is one value per recipient row, or one per email for a draft-level feature.
    """
    values = np.asarray(values, dtype=np.float64)
    unique = np.unique(values)
    spec = {
        "feature": name,
        "cumulative": name in CUMULATIVE_FEATURES,
        "unit": "email" if name in DRAFT_LEVEL_FEATURES else "recipient_row",
        "rows": int(len(values)),
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "unique": int(len(unique)),
    }
    if len(unique) <= MAX_DISCRETE_VALUES:
        spec["kind"] = "constant" if len(unique) == 1 else "discrete"
        spec["values"] = [float(item) for item in unique]
    else:
        edges = np.unique(np.quantile(values, np.linspace(0, 1, QUANTILE_BINS + 1)[1:-1]))
        spec["kind"] = "quantile"
        spec["edges"] = [float(item) for item in edges]
    spec["counts"] = [int(item) for item in bin_counts(spec, values)]
    return spec


def assign_bins(spec: dict, values: np.ndarray) -> np.ndarray:
    """Bin index for each value. Discrete features get one extra bin for a value never seen in train."""
    values = np.asarray(values, dtype=np.float64)
    if spec["kind"] == "quantile":
        return np.searchsorted(np.asarray(spec["edges"]), values, side="right")
    known = np.asarray(spec["values"])
    distance = np.abs(values[:, None] - known[None, :])
    nearest = distance.argmin(axis=1)
    matched = distance[np.arange(len(values)), nearest] <= TOLERANCE
    return np.where(matched, nearest, len(known))


def bin_count_length(spec: dict) -> int:
    if spec["kind"] == "quantile":
        return len(spec["edges"]) + 1
    return len(spec["values"]) + 1


def bin_counts(spec: dict, values: np.ndarray) -> np.ndarray:
    return np.bincount(assign_bins(spec, values), minlength=bin_count_length(spec))


def unit_values(frame, name: str, key: str) -> np.ndarray:
    """Values of one feature at its unit of analysis: per email for draft-level features, else per row."""
    if name in DRAFT_LEVEL_FEATURES:
        return frame.drop_duplicates(key)[name].to_numpy()
    return frame[name].to_numpy()


def build_reference(features_dir: Path) -> dict:
    """Input reference from the train feature file only."""
    path, checksum = verified_train_path(features_dir)
    frame = read_features(path)
    missing = [name for name in FEATURE_COLUMNS if name not in frame.columns]
    if missing:
        raise ReferenceError(f"Train features are missing {missing}")
    if not np.isfinite(frame[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)).all():
        raise ReferenceError("Train features contain a non-finite value")
    return {
        "monitor_version": MONITOR_VERSION,
        "subset": REFERENCE_SUBSET,
        "source": {"file": path.name, "sha256": checksum, "checked_against": "artifact_manifest.json"},
        "bundle": {
            "contract_version": API_CONTRACT_VERSION,
            "snapshot_id": SNAPSHOT_ID,
            "dataset_version": DATASET_VERSION,
            "feature_spec_version": FEATURE_SPEC_VERSION,
            "model_version": MODEL_VERSION,
            "policy_version": POLICY_VERSION,
        },
        "rows": int(len(frame)),
        "drafts": int(frame["draft_id"].nunique()),
        "psi": {
            "watch": PSI_WATCH,
            "alert": PSI_ALERT,
            "pseudo_count": PSI_PSEUDO_COUNT,
            "quantile_bins": QUANTILE_BINS,
            "max_discrete_values": MAX_DISCRETE_VALUES,
        },
        "cumulative_features": list(CUMULATIVE_FEATURES),
        "features": {name: feature_spec(name, unit_values(frame, name, "draft_id")) for name in FEATURE_COLUMNS},
        "note": (
            "Train is enriched to 10% misdirected mail. Its recipient mix differs from product-like traffic, "
            "so some features sit in the watch band on ordinary validation mail."
        ),
    }


def policy_reference(policy_dir: Path) -> dict:
    """Fixed operating numbers from the frozen policy file. Validation only."""
    policy = json.loads((Path(policy_dir) / "policy.json").read_text(encoding="utf-8"))
    email = policy["validation_confusion"]["email"]
    return {
        "policy_version": policy["policy_version"],
        "T_warn": policy["T_warn"],
        "blocking_enabled": policy["blocking_enabled"],
        "highest_legitimate_validation_email_risk": policy["selection"]["highest_legitimate_email_risk"],
        "selection_subset": policy["selection"]["subset"],
        "validation": {
            "emails": email["n"],
            "misdirected": email["positives"],
            "legitimate": email["legitimate"],
            "warned_mistakes": email["true_positives"],
            "false_interventions": email["false_positives"],
            "warnings": policy["validation_confusion"]["warnings"],
            "blocks": policy["validation_confusion"]["blocks"],
            "independent_of_selection": False,
        },
    }


def latency_reference(latency_path: Path) -> dict:
    """The recorded AC05 measurement, read as-is. It is never rewritten."""
    stored = json.loads(Path(latency_path).read_text(encoding="utf-8"))
    return {
        "path": str(latency_path),
        "measured_calls": stored["measured_calls"],
        "statuses": stored["statuses"],
        "client_p50_ms": stored["client_p50_ms"],
        "client_p95_ms": stored["client_p95_ms"],
        "client_p99_ms": stored["client_p99_ms"],
        "target_p95_ms": stored["target_p95_ms"],
        "cold_start_seconds": stored["cold_start_seconds"],
        "environment": stored["environment"],
    }


def build_all(features_dir: Path, policy_dir: Path, latency_path: Path) -> dict:
    payload = build_reference(features_dir)
    payload["policy_reference"] = policy_reference(policy_dir)
    payload["latency_reference"] = latency_reference(latency_path)
    return payload


def write_once(payload: dict, path: Path) -> None:
    """Write a JSON record that is never overwritten. Sorted keys keep the file deterministic."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
