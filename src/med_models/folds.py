"""Chronological cross-validation folds.

Weeks are split into contiguous blocks. A family is assigned by its latest
draft, so every draft in the family shares one fold and a test fold never
trains on a later block.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from med_models.version import N_FOLDS, ModelError


def week_start(moment) -> pd.Timestamp:
    current = moment.astimezone(moment.tzinfo)
    monday = current - timedelta(days=current.weekday())
    return pd.Timestamp(year=monday.year, month=monday.month, day=monday.day, tz="UTC")


def assign_folds(audit: pd.DataFrame, n_folds: int = N_FOLDS) -> pd.DataFrame:
    """Return one row per draft with fold id and the week used to assign it."""
    drafts = (
        audit.groupby("draft_id", sort=False)
        .agg(family_id=("family_id", "first"), sent_at=("sent_at", "first"), positive=("positive", "any"))
        .reset_index()
    )
    family_time = drafts.groupby("family_id", sort=False)["sent_at"].max()
    family_week = family_time.map(week_start)
    weeks = sorted(family_week.unique())
    if len(weeks) < n_folds:
        raise ModelError(f"Need at least {n_folds} train weeks, found {len(weeks)}")
    edges = [round(index * len(weeks) / n_folds) for index in range(n_folds + 1)]
    week_to_fold = {}
    boundaries = []
    for fold, (start, end) in enumerate(zip(edges, edges[1:])):
        block = weeks[start:end]
        for week in block:
            week_to_fold[week] = fold
        boundaries.append(
            {
                "fold": fold,
                "week_start": block[0].strftime("%Y-%m-%d"),
                "week_end": block[-1].strftime("%Y-%m-%d"),
                "n_weeks": len(block),
            }
        )
    assigned = family_week.map(week_to_fold)
    drafts["fold"] = drafts["family_id"].map(assigned).astype(int)
    drafts["assignment_week"] = drafts["family_id"].map(family_week)
    summary = []
    for item in boundaries:
        group = drafts.loc[drafts["fold"] == item["fold"]]
        item = dict(item)
        item["n_drafts"] = int(len(group))
        item["n_positive_emails"] = int(group["positive"].sum())
        item["n_families"] = int(group["family_id"].nunique())
        item["min_sent_at"] = min(group["sent_at"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        item["max_sent_at"] = max(group["sent_at"]).strftime("%Y-%m-%dT%H:%M:%SZ")
        summary.append(item)
    drafts.attrs["boundaries"] = summary
    return drafts


def expanding_tests(draft_folds: pd.DataFrame) -> list[tuple[int, np.ndarray, np.ndarray]]:
    """Yield (test fold, train draft ids, test draft ids) using only earlier folds to train."""
    splits = []
    folds = sorted(draft_folds["fold"].unique())
    for test_fold in folds[1:]:
        train_ids = draft_folds.loc[draft_folds["fold"] < test_fold, "draft_id"].to_numpy()
        test_ids = draft_folds.loc[draft_folds["fold"] == test_fold, "draft_id"].to_numpy()
        if len(train_ids) == 0 or len(test_ids) == 0:
            raise ModelError(f"Fold {test_fold} has an empty train or test block")
        splits.append((int(test_fold), train_ids, test_ids))
    return splits
