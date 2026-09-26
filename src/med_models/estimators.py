"""Estimators for the recorded comparison.

Logistic regression standardizes after log1p. The tree uses the same log1p and
no scaling. Both are fit only on the rows passed in, which the experiment
runner limits to training folds or the full training subset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from med_models.preprocess import CountLogScaler
from med_models.rules import fusion_scores, rules_scores
from med_models.version import SEED, ModelError


class ScoreModel:
    """A fitted scorer. predict returns risk scores, not calibrated probabilities."""

    kind = "base"

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError

    def novelty(self) -> dict:
        return {"available": False}


class AlwaysAllow(ScoreModel):
    kind = "always_allow"

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(frame), dtype=np.float64)


class RulesModel(ScoreModel):
    kind = "rules"

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return rules_scores(frame)

    def novelty(self) -> dict:
        return {
            "available": True,
            "kind": "rule_definition",
            "statement": (
                "Zero outbound mail raises the relationship component only when the sender "
                "has other outbound history. A cold sender scores 0 on that component. "
                "The component is one of three, so novelty does not set the whole score."
            ),
        }


class FusionModel(ScoreModel):
    kind = "fusion"

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return fusion_scores(frame)


class LogisticModel(ScoreModel):
    kind = "logistic"

    def __init__(self, columns: list[str], C: float, class_weight: str | None, recency_floor_days: float | None = None):
        self.columns = list(columns)
        self.C = float(C)
        self.class_weight = class_weight
        self.recency_floor_days = recency_floor_days
        self.scaler = CountLogScaler(self.columns, standardize=True, recency_floor_days=recency_floor_days)
        self.estimator = LogisticRegression(
            C=self.C,
            class_weight=class_weight,
            solver="lbfgs",
            max_iter=1000,
            random_state=SEED,
        )

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> "LogisticModel":
        self.scaler.fit(frame)
        self.estimator.fit(self.scaler.transform(frame), np.asarray(y).astype(int))
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return _positive_proba(self.estimator, self.scaler.transform(frame))

    def novelty(self) -> dict:
        if "recipient_novel_to_sender" not in self.columns:
            return {"available": False, "reason": "feature not in this ablation"}
        index = self.columns.index("recipient_novel_to_sender")
        coefficient = float(self.estimator.coef_[0, index])
        order = np.argsort(-np.abs(self.estimator.coef_[0]))
        largest = [
            {"feature": self.columns[int(index)], "coefficient": float(self.estimator.coef_[0, int(index)])}
            for index in order[:8]
        ]
        return {
            "available": True,
            "kind": "standardized_coefficient",
            "coefficient": coefficient,
            "sign": "positive" if coefficient > 0 else "negative" if coefficient < 0 else "zero",
            "largest_coefficients": largest,
            "note": "Coefficients share collinear count features and are not separate effects.",
        }


class TreeModel(ScoreModel):
    """One depth-limited tree.

    A single tree is the challenger because its splits can be listed. A boosted
    ensemble would hide the novelty check the comparison has to report.
    class_weight is fixed at balanced and is not part of the six-point grid.
    """

    kind = "tree"

    def __init__(self, columns: list[str], max_depth: int, min_samples_leaf: int):
        self.columns = list(columns)
        self.max_depth = int(max_depth)
        self.min_samples_leaf = int(min_samples_leaf)
        self.scaler = CountLogScaler(self.columns, standardize=False)
        self.estimator = DecisionTreeClassifier(
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            class_weight="balanced",
            random_state=SEED,
        )

    def fit(self, frame: pd.DataFrame, y: np.ndarray) -> "TreeModel":
        self.scaler.fit(frame)
        self.estimator.fit(self.scaler.transform(frame), np.asarray(y).astype(int))
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return _positive_proba(self.estimator, self.scaler.transform(frame))

    def novelty(self) -> dict:
        if "recipient_novel_to_sender" not in self.columns:
            return {"available": False, "reason": "feature not in this ablation"}
        index = self.columns.index("recipient_novel_to_sender")
        tree = self.estimator.tree_
        used = sorted({int(feature) for feature in tree.feature if feature >= 0})
        splits = []
        for node, feature in enumerate(tree.feature):
            if int(feature) == index:
                splits.append(
                    {
                        "node": int(node),
                        "threshold": float(tree.threshold[node]),
                        "n_node_samples": int(tree.n_node_samples[node]),
                    }
                )
        return {
            "available": True,
            "kind": "tree_splits",
            "uses_feature": index in used,
            "importance": float(self.estimator.feature_importances_[index]),
            "splits": splits,
        }


def _positive_proba(estimator, matrix: np.ndarray) -> np.ndarray:
    if not hasattr(estimator, "classes_"):
        raise ModelError("Estimator is not fit")
    proba = estimator.predict_proba(matrix)
    classes = [int(label) for label in estimator.classes_]
    if 1 not in classes:
        return np.zeros(matrix.shape[0], dtype=np.float64)
    return proba[:, classes.index(1)].astype(np.float64)
