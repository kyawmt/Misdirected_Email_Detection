"""Train-only transforms for logistic regression and the tree.

Counts and recency take log1p. When recency was not observed, the 3650-day
fallback is replaced with the median observed recency from the fitting rows
before the log. A diagnostic model can also floor recency at one day so a
one-minute generator gap is not a separate signal. Logistic regression then
standardizes. The tree does not. Nothing is fit on validation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from med_models.groups import LOG_COUNTS

LOG_COLUMNS = LOG_COUNTS + ("pair_recency_days",)


class CountLogScaler:
    """Train-only recency imputation, log1p, and optional z-scoring."""

    def __init__(self, columns: list[str], *, standardize: bool = True, recency_floor_days: float | None = None):
        self.columns = list(columns)
        self.standardize = standardize
        self.recency_floor_days = recency_floor_days
        self.log_index = [index for index, name in enumerate(self.columns) if name in LOG_COLUMNS]
        self.recency_index = self.columns.index("pair_recency_days") if "pair_recency_days" in self.columns else None
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self.recency_fill_: float | None = None
        self.n_samples_seen_: int = 0

    def fit(self, frame: pd.DataFrame) -> "CountLogScaler":
        self.recency_fill_ = _recency_fill(frame)
        values = self._logged(frame)
        self.mean_ = values.mean(axis=0)
        scale = values.std(axis=0)
        scale[scale == 0] = 1.0
        self.scale_ = scale
        self.n_samples_seen_ = int(values.shape[0])
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("CountLogScaler is not fit")
        values = self._logged(frame)
        if not self.standardize:
            return values
        return (values - self.mean_) / self.scale_

    def _logged(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame.loc[:, self.columns].to_numpy(dtype=np.float64, copy=True)
        if self.recency_index is not None and self.recency_fill_ is not None and "pair_recency_observed" in frame.columns:
            missing = frame["pair_recency_observed"].to_numpy() == 0
            values[missing, self.recency_index] = self.recency_fill_
        if self.recency_index is not None and self.recency_floor_days is not None:
            values[:, self.recency_index] = np.maximum(values[:, self.recency_index], self.recency_floor_days)
        if self.log_index:
            values[:, self.log_index] = np.log1p(np.clip(values[:, self.log_index], 0, None))
        return values


def _recency_fill(frame: pd.DataFrame) -> float | None:
    if "pair_recency_days" not in frame.columns or "pair_recency_observed" not in frame.columns:
        return None
    observed = frame["pair_recency_observed"].to_numpy() == 1
    if not observed.any():
        return 0.0
    return float(np.median(frame["pair_recency_days"].to_numpy(dtype=np.float64)[observed]))
