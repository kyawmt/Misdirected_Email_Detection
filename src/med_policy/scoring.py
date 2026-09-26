"""Recipient score tables for the frozen model.

Validation tables come from the published feature matrices. The frozen test
subsets have no published matrices, so their table is computed in memory with
the saved transformer and the existing history cutoff. Neither path fits
anything. Label, family, and scenario columns are joined for offline metrics
only; the model sees the feature columns alone.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from med_data.io import read_dataset, verify_files
from med_features.profiles import directory_from_dataset, history_index_from_dataset
from med_features.schema import FeatureError
from med_features.text_model import FittedText
from med_features.transform import query_from_dataset, transform_draft
from med_models.data import load_model_table, verify_feature_artifact
from med_models.rules import rules_scores
from med_models.version import ModelError
from med_policy.version import TEST_SUBSETS, PolicyError

# A first contact for the same sender: no pair history, recency unobserved.
# Same rewrite as the Phase 4 paired check.
FIRST_CONTACT_REWRITE = (
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
    # A first contact has no pair text, so the content fields take their fallbacks too.
    ("content_cosine", 0.0),
    ("content_similarity_observed", 0),
    ("pair_text_message_count", 0),
)

TABLE_COLUMNS = (
    "subset",
    "draft_id",
    "contact_id",
    "recipient_order",
    "family_id",
    "scenario_id",
    "positive",
    "assessed",
    "addressed_recipient_count",
    "recipient_is_internal",
    "recipient_novel_to_sender",
    "pair_recency_days",
    "risk_score",
    "rules_score",
    "risk_score_as_first_contact",
)


def as_first_contact(frame: pd.DataFrame) -> pd.DataFrame:
    altered = frame.copy()
    for name, value in FIRST_CONTACT_REWRITE:
        altered[name] = value
    return altered


def published_table(features_dir: Path, data_dir: Path, model, subset: str) -> pd.DataFrame:
    """Score a published validation matrix. Frozen subsets are refused upstream."""
    if subset in TEST_SUBSETS:
        raise PolicyError(f"Refusing to read frozen subset {subset} from published features")
    frame, audit = load_model_table(features_dir, data_dir, subset)
    return _assemble(subset, frame, audit, model)


def in_memory_table(features_dir: Path, data_dir: Path, model, subsets: tuple[str, ...]) -> tuple[pd.DataFrame, dict]:
    """Compute features in memory with the frozen transformer, then score.

    Nothing is written to disk and no estimator or vectorizer is fit. A draft
    that raises a feature or model error becomes an unassessed placeholder row.
    """
    verify_feature_artifact(features_dir)
    verify_files(data_dir)
    dataset = read_dataset(data_dir)
    transformer = FittedText.load(features_dir / "text_transformer.joblib")
    directory = directory_from_dataset(dataset)
    index = history_index_from_dataset(dataset)
    index.bind(transformer)
    labels = dataset.labels.loc[:, ["draft_id", "contact_id", "intended"]]
    drafts = dataset.drafts
    tables = []
    failures = {}
    for subset in subsets:
        chosen = drafts.loc[drafts["subset"] == subset].sort_values(["sent_at", "draft_id"], kind="mergesort")
        frames = []
        failed = []
        for draft_id in chosen["draft_id"].tolist():
            try:
                frames.append(transform_draft(directory, index, transformer, query_from_dataset(dataset, draft_id)))
            except (FeatureError, ModelError) as error:
                failed.append({"draft_id": draft_id, "error": str(error)})
        failures[subset] = failed
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        audit = frame[["draft_id", "contact_id"]].merge(labels, on=["draft_id", "contact_id"], how="left")
        if audit["intended"].isna().any():
            raise PolicyError(f"{subset} has a recipient row without a label")
        meta = chosen.loc[:, ["draft_id", "family_id", "scenario_id"]]
        audit = audit.merge(meta, on="draft_id", how="left")
        audit["positive"] = ~audit["intended"].astype(bool)
        table = _assemble(subset, frame, audit, model)
        if failed:
            table = pd.concat([table, _unassessed_rows(subset, failed, chosen, labels)], ignore_index=True)
        tables.append(table)
    return pd.concat(tables, ignore_index=True), failures


def _assemble(subset: str, frame: pd.DataFrame, audit: pd.DataFrame, model) -> pd.DataFrame:
    scores = model.score_frame(frame)
    rewritten = model.score_frame(as_first_contact(frame))
    table = pd.DataFrame(
        {
            "subset": subset,
            "draft_id": frame["draft_id"].astype(str).to_numpy(),
            "contact_id": frame["contact_id"].astype(str).to_numpy(),
            "recipient_order": frame["recipient_order"].to_numpy(dtype=np.int64),
            "family_id": audit["family_id"].astype(str).to_numpy(),
            "scenario_id": audit["scenario_id"].astype(str).to_numpy(),
            "positive": audit["positive"].to_numpy(dtype=bool),
            "assessed": True,
            "addressed_recipient_count": frame["addressed_recipient_count"].to_numpy(dtype=np.int64),
            "recipient_is_internal": frame["recipient_is_internal"].to_numpy(dtype=np.int64),
            "recipient_novel_to_sender": frame["recipient_novel_to_sender"].to_numpy(dtype=np.int64),
            "pair_recency_days": frame["pair_recency_days"].to_numpy(dtype=np.float64),
            "risk_score": np.asarray(scores, dtype=np.float64),
            "rules_score": rules_scores(frame),
            "risk_score_as_first_contact": np.asarray(rewritten, dtype=np.float64),
        }
    )
    if not np.isfinite(table["risk_score"]).all():
        raise PolicyError(f"{subset} produced a non-finite risk score")
    return table.loc[:, list(TABLE_COLUMNS)]


def _unassessed_rows(subset, failed, chosen, labels) -> pd.DataFrame:
    """One placeholder per failed draft. An unassessed positive is not a detection."""
    rows = []
    for item in failed:
        draft = chosen.loc[chosen["draft_id"] == item["draft_id"]].iloc[0]
        positive = bool((~labels.loc[labels["draft_id"] == item["draft_id"], "intended"].astype(bool)).any())
        rows.append(
            {
                "subset": subset,
                "draft_id": item["draft_id"],
                "contact_id": "",
                "recipient_order": 0,
                "family_id": str(draft["family_id"]),
                "scenario_id": str(draft["scenario_id"]),
                "positive": positive,
                "assessed": False,
                "addressed_recipient_count": 0,
                "recipient_is_internal": 0,
                "recipient_novel_to_sender": 0,
                "pair_recency_days": np.nan,
                "risk_score": np.nan,
                "rules_score": np.nan,
                "risk_score_as_first_contact": np.nan,
            }
        )
    return pd.DataFrame(rows, columns=list(TABLE_COLUMNS))
