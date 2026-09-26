"""Save and load a selected model without refitting."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from med_features.schema import FEATURE_COLUMNS, FEATURE_SPEC_VERSION
from med_features.transform import transform_draft
from med_models.data import model_matrix, sha256_file
from med_models.version import MODEL_VERSION, ModelError


def save_model(path: Path, model, metadata: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = dict(metadata)
    metadata["model_version"] = MODEL_VERSION
    joblib.dump({"metadata": metadata, "model": model}, path)


def load_model(path: Path):
    payload = joblib.load(path)
    metadata = payload["metadata"]
    if metadata.get("model_version") != MODEL_VERSION:
        raise ModelError(f"Model version {metadata.get('model_version')} does not match {MODEL_VERSION}")
    if metadata.get("feature_spec_version") != FEATURE_SPEC_VERSION:
        raise ModelError(
            f"Feature spec {metadata.get('feature_spec_version')} does not match {FEATURE_SPEC_VERSION}"
        )
    if list(metadata.get("full_feature_columns", [])) != list(FEATURE_COLUMNS):
        raise ModelError("Saved feature schema does not match the installed feature columns")
    return LoadedModel(metadata, payload["model"])


class LoadedModel:
    def __init__(self, metadata: dict, model):
        self.metadata = metadata
        self.model = model
        self.feature_columns = list(metadata["feature_columns"])

    def score_frame(self, frame: pd.DataFrame) -> np.ndarray:
        if "feature_spec_version" in frame.columns:
            versions = set(frame["feature_spec_version"].astype(str))
            if versions != {FEATURE_SPEC_VERSION}:
                raise ModelError(f"Frame feature spec {versions} does not match {FEATURE_SPEC_VERSION}")
        matrix = model_matrix(frame, self.feature_columns)
        return self.model.predict(matrix)

    def score_query(self, directory, history, text_transformer, query) -> pd.DataFrame:
        """Score one draft through the shared feature transform, then this model."""
        frame = transform_draft(directory, history, text_transformer, query)
        scored = frame.loc[:, ["draft_id", "contact_id", "recipient_order"]].copy()
        scored["risk_score"] = self.score_frame(frame)
        return scored


def artifact_metadata(features_dir: Path, data_dir: Path, selected: dict, folds: list[dict]) -> dict:
    manifest = json.loads((features_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    fit_meta = json.loads((features_dir / "fit_metadata.json").read_text(encoding="utf-8"))
    import numpy
    import sklearn

    return {
        "model_version": MODEL_VERSION,
        "kind": selected["kind"],
        "ablation": selected["ablation"],
        "run_name": selected["name"],
        "config": selected["config"],
        "feature_columns": selected["features"],
        "full_feature_columns": list(FEATURE_COLUMNS),
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "feature_schema_sha256": manifest["files"]["feature_schema.json"]["sha256"],
        "text_transformer_sha256": manifest["files"]["text_transformer.joblib"]["sha256"],
        "dataset_version": fit_meta["dataset_version"],
        "dataset_checksums": fit_meta["dataset_checksums"],
        "training_subset": "train",
        "data_dir_name": data_dir.name,
        "folds": folds,
        "seed": selected.get("seed", fit_meta.get("seed")),
        "sklearn_version": sklearn.__version__,
        "numpy_version": numpy.__version__,
        "scores_are": "risk_scores",
        "calibration": "not_fit",
        "thresholds": "not_selected",
    }


def file_sha256(path: Path) -> str:
    return sha256_file(path)
