"""Phase 4 model contract: columns, folds, rules, and reload."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from med_features.schema import FEATURE_COLUMNS, FEATURE_SPEC_VERSION
from med_models.data import FORBIDDEN_COLUMNS, load_model_table, model_matrix
from med_models.estimators import LogisticModel
from med_models.folds import assign_folds
from med_models.metrics import email_table
from med_models.package import load_model, save_model
from med_models.experiments import _select
from med_models.preprocess import CountLogScaler
from med_models.rules import rules_scores
from med_models.version import MODEL_VERSION, ModelError

ROOT = Path(__file__).resolve().parents[1]


def test_model_matrix_rejects_audit_columns():
    frame = _feature_frame(2)
    frame["scenario_id"] = "S01"
    frame["split"] = "train"
    frame["intended"] = False
    frame["role"] = "bcc"
    with pytest.raises(ModelError, match="audit"):
        model_matrix(frame, ["pair_outbound_count", "sender_history_available"])
    assert "scenario_id" in FORBIDDEN_COLUMNS
    assert "family_id" in FORBIDDEN_COLUMNS


def test_scaler_fits_on_train_rows_only():
    train = _feature_frame(4)
    train["pair_outbound_count"] = [0, 10, 20, 30]
    holdout = _feature_frame(2)
    holdout["pair_outbound_count"] = [1000, 1000]
    columns = ["pair_outbound_count", "sender_history_available"]
    scaler = CountLogScaler(columns).fit(train)
    assert scaler.n_samples_seen_ == len(train)
    transformed = scaler.transform(holdout)
    logged = np.log1p(train["pair_outbound_count"].to_numpy(dtype=float))
    assert scaler.mean_[0] == pytest.approx(logged.mean())
    assert transformed.shape == (2, 2)


def test_folds_are_chronological_and_keep_families_together():
    moments = [datetime(2024, 7, 1, tzinfo=timezone.utc) + timedelta(days=7 * index) for index in range(8)]
    audit = pd.DataFrame(
        {
            "draft_id": ["d0", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7"],
            "contact_id": ["c"] * 9,
            "family_id": ["f0", "f0", "f0", "f2", "f3", "f4", "f5", "f6", "f7"],
            "sent_at": [moments[0], moments[0], moments[5], moments[1], moments[2], moments[3], moments[4], moments[6], moments[7]],
            "positive": [False, True, False, False, True, False, False, True, False],
        }
    )
    assigned = assign_folds(audit, n_folds=4)
    assert assigned.groupby("family_id")["fold"].nunique().max() == 1
    family_folds = assigned.groupby("family_id")["fold"].first()
    assert family_folds["f0"] == assigned.loc[assigned["draft_id"] == "d1", "fold"].iloc[0]
    week_by_fold = assigned.groupby("fold")["assignment_week"].agg(["min", "max"])
    for fold in range(3):
        assert week_by_fold.loc[fold, "max"] < week_by_fold.loc[fold + 1, "min"]


def test_published_train_folds_keep_families_whole():
    _frame, audit = load_model_table(ROOT / "artifacts" / "med-features-v1", ROOT / "data" / "med-synth-v2", "train")
    assigned = assign_folds(audit)
    assert assigned.groupby("family_id")["fold"].nunique().max() == 1
    week_by_fold = assigned.groupby("fold")["assignment_week"].agg(["min", "max"])
    for fold in range(int(assigned["fold"].max())):
        assert week_by_fold.loc[fold, "max"] < week_by_fold.loc[fold + 1, "min"]


def test_email_risk_is_the_max_and_two_mistakes_count_once():
    audit = pd.DataFrame(
        {
            "draft_id": ["d1", "d1", "d1"],
            "family_id": ["fam", "fam", "fam"],
            "scenario_id": ["S08", "S08", "S08"],
            "sent_at": [datetime(2024, 8, 1, tzinfo=timezone.utc)] * 3,
            "positive": [True, True, False],
            "addressed_recipient_count": [3, 3, 3],
        }
    )
    emails = email_table(audit, np.array([0.2, 0.9, 0.4]))
    assert emails.loc[0, "score"] == pytest.approx(0.9)
    assert bool(emails.loc[0, "positive"]) is True
    assert len(emails) == 1


def test_rules_match_the_hand_calculation():
    frame = _feature_frame(3)
    frame.loc[0, "sender_history_available"] = 1
    frame.loc[0, "pair_outbound_count"] = 0
    frame.loc[0, "co_support_applicable"] = 1
    frame.loc[0, "co_partner_fraction"] = 0
    frame.loc[0, "near_name_count"] = 1
    frame.loc[1, "sender_history_available"] = 1
    frame.loc[1, "pair_outbound_count"] = 0
    frame.loc[1, "co_support_applicable"] = 0
    frame.loc[1, "near_name_count"] = 0
    frame.loc[2, "sender_history_available"] = 0
    frame.loc[2, "pair_outbound_count"] = 0
    frame.loc[2, "near_name_count"] = 2
    scores = rules_scores(frame)
    assert scores[0] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(1 / 3)
    assert scores[2] == pytest.approx(1 / 3)


def test_logistic_training_is_deterministic_and_round_trips(tmp_path):
    frame = _feature_frame(12)
    frame["pair_outbound_count"] = np.arange(12)
    frame["recipient_novel_to_sender"] = [1, 0] * 6
    y = np.array([0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1])
    columns = ["sender_history_available", "pair_outbound_count", "recipient_novel_to_sender"]
    first = LogisticModel(columns, C=1.0, class_weight=None).fit(frame, y)
    second = LogisticModel(columns, C=1.0, class_weight=None).fit(frame, y)
    assert np.allclose(first.estimator.coef_, second.estimator.coef_)
    metadata = {
        "kind": "logistic",
        "ablation": "behavior_only",
        "run_name": "logistic_toy",
        "config": {"C": 1.0, "class_weight": "unweighted"},
        "feature_columns": columns,
        "full_feature_columns": list(FEATURE_COLUMNS),
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "feature_schema_sha256": "test",
        "text_transformer_sha256": "test",
        "dataset_version": "med-synth-v2",
        "dataset_checksums": {},
        "training_subset": "train",
        "data_dir_name": "med-synth-v2",
        "folds": [],
        "seed": 20260926,
        "sklearn_version": "test",
        "numpy_version": "test",
        "scores_are": "risk_scores",
        "calibration": "not_fit",
        "thresholds": "not_selected",
    }
    path = tmp_path / "model.joblib"
    save_model(path, first, metadata)
    loaded = load_model(path)
    assert loaded.model.scaler.n_samples_seen_ == 12
    alone = loaded.score_frame(frame.iloc[[3]])
    batch = loaded.score_frame(frame)
    assert alone[0] == pytest.approx(batch[3])
    import joblib

    payload = joblib.load(path)
    payload["metadata"]["model_version"] = "med-model-v0"
    joblib.dump(payload, path)
    with pytest.raises(ModelError, match="version"):
        load_model(path)


def test_unobserved_recency_is_filled_with_the_train_median_then_logged():
    frame = _feature_frame(4)
    frame["pair_recency_observed"] = [1, 1, 0, 1]
    frame["pair_recency_days"] = [2.0, 6.0, 3650.0, 4.0]
    columns = ["pair_recency_days", "pair_recency_observed"]
    scaler = CountLogScaler(columns, standardize=False).fit(frame)
    assert scaler.recency_fill_ == pytest.approx(4.0)
    logged = scaler.transform(frame)
    assert logged[2, 0] == pytest.approx(np.log1p(4.0))
    assert logged[0, 0] == pytest.approx(np.log1p(2.0))
    floored = CountLogScaler(columns, standardize=False, recency_floor_days=1.0).fit(frame)
    frame.loc[0, "pair_recency_days"] = 0.01
    floored = CountLogScaler(columns, standardize=False, recency_floor_days=1.0).fit(frame)
    assert floored.transform(frame)[0, 0] == pytest.approx(np.log1p(1.0))


def test_selection_tie_break_uses_training_fold_mean():
    def run(name, validation_ap, cv_mean):
        return {
            "name": name,
            "kind": "logistic",
            "ablation": "behavior_only",
            "eligible": True,
            "simplicity": 1,
            "cv": {"mean": cv_mean},
            "validation_product_like": {
                "email": {
                    "average_precision": validation_ap,
                    "bootstrap": {"average_precision": {"low": 0.2, "high": 1.0}},
                }
            },
        }

    chosen = _select([run("higher_validation", 0.9, 0.50), run("higher_cv", 0.6, 0.80)])
    assert chosen == "higher_cv"


def test_score_query_matches_batch_and_scoring_view():
    from med_data.io import read_dataset
    from med_data.views import scoring_view
    from med_features.profiles import EventHistory, directory_from_dataset, history_index_from_dataset
    from med_features.text_model import FittedText
    from med_features.transform import events_from_scoring_view, query_from_dataset, query_from_scoring_view, transform_draft
    from med_models.package import load_model

    dataset = read_dataset(ROOT / "data" / "med-synth-v2")
    text = FittedText.load(ROOT / "artifacts" / "med-features-v1" / "text_transformer.joblib")
    index = history_index_from_dataset(dataset)
    index.bind(text)
    directory = directory_from_dataset(dataset)
    loaded = load_model(ROOT / "artifacts" / "med-model-v1" / "model.joblib")
    drafts = dataset.drafts
    for subset in ("train", "validation_product_like", "validation_diagnostic"):
        ids = drafts.loc[drafts["subset"] == subset, "draft_id"].head(2).tolist()
        matrix = pd.read_csv(ROOT / "artifacts" / "med-features-v1" / f"features_{subset}.csv")
        for draft_id in ids:
            single = loaded.score_query(directory, index, text, query_from_dataset(dataset, draft_id))
            stored = matrix.loc[matrix["draft_id"] == draft_id].sort_values("recipient_order")
            batch = loaded.score_frame(stored)
            assert np.allclose(single["risk_score"].to_numpy(), batch)
            view = scoring_view(dataset, draft_id)
            viewed = transform_draft(
                directory,
                EventHistory(events_from_scoring_view(view), text),
                text,
                query_from_scoring_view(view),
            )
            assert np.allclose(loaded.score_frame(viewed), batch)


def test_published_model_reloads_without_refitting():
    from med_models.package import load_model

    loaded = load_model(ROOT / "artifacts" / "med-model-v1" / "model.joblib")
    assert loaded.metadata["model_version"] == MODEL_VERSION
    assert loaded.metadata["thresholds"] == "not_selected"
    assert loaded.metadata["calibration"] == "not_fit"
    if loaded.metadata["ablation"] == "behavior_only":
        assert "content_cosine" not in loaded.feature_columns
    frame, _audit = load_model_table(
        ROOT / "artifacts" / "med-features-v1",
        ROOT / "data" / "med-synth-v2",
        "validation_product_like",
    )
    sample = frame.iloc[:4]
    first = loaded.score_frame(sample)
    second = loaded.score_frame(sample)
    assert np.allclose(first, second)
    if loaded.metadata["kind"] == "logistic":
        assert loaded.model.scaler.n_samples_seen_ == 2320


def test_frozen_subset_is_refused():
    with pytest.raises(ModelError, match="frozen"):
        load_model_table(ROOT / "artifacts" / "med-features-v1", ROOT / "data" / "med-synth-v2", "test_product_like")
    with pytest.raises(ModelError, match="frozen"):
        load_model_table(ROOT / "artifacts" / "med-features-v1", ROOT / "data" / "med-synth-v2", "test_diagnostic")


def test_model_sources_do_not_export_frozen_features():
    root = ROOT / "src" / "med_models"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "features_test_product_like" not in text
    assert "features_test_diagnostic" not in text
    assert "FROZEN_SUBSETS" in text


def _feature_frame(rows: int) -> pd.DataFrame:
    data = {name: np.zeros(rows) for name in FEATURE_COLUMNS}
    data["feature_spec_version"] = [FEATURE_SPEC_VERSION] * rows
    data["draft_id"] = [f"d{index}" for index in range(rows)]
    data["contact_id"] = ["c"] * rows
    data["recipient_order"] = [0] * rows
    data["sender_history_available"] = np.ones(rows)
    return pd.DataFrame(data)
