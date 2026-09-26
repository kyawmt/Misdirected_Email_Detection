"""Load feature matrices and join labels for offline metrics.

The frame passed to an estimator contains only the requested feature columns.
Audit fields stay in a side table used for folds, family bootstrap, and reports.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from med_data.calendar import parse_ts
from med_features.build import read_features
from med_features.schema import FEATURE_COLUMNS, FEATURE_SPEC_VERSION, MATRIX_COLUMNS
from med_models.version import ModelError

FROZEN_SUBSETS = frozenset({"test_product_like", "test_diagnostic"})
ALLOWED_SUBSETS = frozenset({"train", "validation_product_like", "validation_diagnostic"})
FORBIDDEN_COLUMNS = frozenset(
    {
        "intended",
        "role",
        "scenario_id",
        "scenario_variant",
        "split",
        "subset",
        "family_id",
        "stipulation",
        "label_source",
        "label_confidence",
        "is_counterfactual",
        "is_walkthrough",
        "withheld_contact_id",
        "generator_topic",
        "frozen",
        "is_misdirected_email",
    }
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_feature_artifact(features_dir: Path) -> dict:
    """Check the published feature-artifact manifest before any model reads it."""
    manifest_path = features_dir / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("feature_spec_version") != FEATURE_SPEC_VERSION:
        raise ModelError(
            f"Feature artifact is {manifest.get('feature_spec_version')}, expected {FEATURE_SPEC_VERSION}"
        )
    for name, meta in manifest["files"].items():
        path = features_dir / name
        if sha256_file(path) != meta["sha256"]:
            raise ModelError(f"Checksum mismatch for {name}")
    return manifest


def load_model_table(features_dir: Path, data_dir: Path, subset: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (feature frame, audit frame) for one non-frozen subset.

    The feature frame has the matrix columns only. The audit frame carries the
    label, family, time, and scenario used for evaluation and is not a model input.
    """
    if subset in FROZEN_SUBSETS:
        raise ModelError(f"Refusing to load frozen subset {subset}")
    if subset not in ALLOWED_SUBSETS:
        raise ModelError(f"Unknown subset {subset}")
    verify_feature_artifact(features_dir)
    frame = read_features(features_dir / f"features_{subset}.csv")
    if list(frame.columns) != list(MATRIX_COLUMNS):
        raise ModelError(f"features_{subset}.csv columns do not match the feature schema")
    if not (frame["feature_spec_version"] == FEATURE_SPEC_VERSION).all():
        raise ModelError(f"Feature spec version on a row does not match {FEATURE_SPEC_VERSION}")
    leaked = set(frame.columns) & FORBIDDEN_COLUMNS
    if leaked:
        raise ModelError(f"Feature matrix contains audit columns: {sorted(leaked)}")
    audit = _audit(data_dir, frame, subset)
    return frame, audit


def model_matrix(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Select model columns and reject audit fields."""
    leaked = set(frame.columns) & FORBIDDEN_COLUMNS
    if leaked:
        raise ModelError(f"Refusing audit columns in a model frame: {sorted(leaked)}")
    missing = [name for name in columns if name not in frame.columns]
    if missing:
        raise ModelError(f"Model frame is missing features: {missing}")
    unknown = [name for name in columns if name not in FEATURE_COLUMNS]
    if unknown:
        raise ModelError(f"Unknown model features: {unknown}")
    ordered = [name for name in FEATURE_COLUMNS if name in columns]
    if ordered != list(columns):
        raise ModelError("Feature columns are out of schema order")
    return frame.loc[:, ordered]


def _as_bool(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    mapped = values.astype(str).str.lower().map({"true": True, "false": False, "1": True, "0": False})
    return mapped


def _audit(data_dir: Path, frame: pd.DataFrame, subset: str) -> pd.DataFrame:
    drafts = pd.read_csv(
        data_dir / "drafts.csv",
        usecols=["draft_id", "family_id", "sent_at", "scenario_id", "scenario_variant", "subset"],
    )
    labels = pd.read_csv(data_dir / "labels.csv", usecols=["draft_id", "contact_id", "intended"])
    labels["intended"] = _as_bool(labels["intended"])
    if labels["intended"].isna().any():
        raise ModelError("A label is not true or false")
    draft_part = drafts.loc[drafts["subset"] == subset, ["draft_id", "family_id", "sent_at", "scenario_id", "scenario_variant"]]
    if set(frame["draft_id"]) - set(draft_part["draft_id"]):
        raise ModelError(f"{subset} feature rows include a draft from another subset")
    merged = frame[["draft_id", "contact_id"]].merge(labels, on=["draft_id", "contact_id"], how="left")
    if merged["intended"].isna().any():
        raise ModelError("A feature row has no label")
    merged = merged.merge(draft_part, on="draft_id", how="left")
    if merged["family_id"].isna().any():
        raise ModelError("A feature row has no family")
    merged["sent_at"] = merged["sent_at"].map(parse_ts)
    merged["positive"] = ~merged["intended"]
    return merged
