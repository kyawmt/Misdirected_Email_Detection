"""Hand-written behavioral rules.

These formulas were fixed from the feature definitions before any validation
metric was computed. Each component is 0 or 1. No single component can make
the rules score 1. External domain and content cosine are not used.

relationship: the sender has sent mail before, and none of it addressed this
recipient. A cold sender does not score, because missing history is not evidence.

co_recipient: the draft has at least two recipients, and none of the other
current recipients share an earlier outbound message with this one.

similarity: at least one other visible contact has display-name similarity
at or above the 0.8 near-name threshold.

rules score = (relationship + co_recipient + similarity) / 3

The one fusion variant adds a content term and divides by 4. Content risk is
1 minus cosine when a cosine was measured, and 0 when it was not. That term
is the generator shortcut, so fusion is reported separately from behavior-only
selection. Reciprocal-rank fusion is not used: ranks depend on the other rows
in a batch, and a single draft would then score differently from the same draft
inside a batch.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def behavior_components(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    relationship = (
        (frame["sender_history_available"].to_numpy() == 1) & (frame["pair_outbound_count"].to_numpy() == 0)
    ).astype(np.float64)
    co_recipient = (
        (frame["co_support_applicable"].to_numpy() == 1) & (np.isclose(frame["co_partner_fraction"].to_numpy(), 0.0))
    ).astype(np.float64)
    similarity = (frame["near_name_count"].to_numpy() >= 1).astype(np.float64)
    return relationship, co_recipient, similarity


def content_component(frame: pd.DataFrame) -> np.ndarray:
    observed = frame["content_similarity_observed"].to_numpy() == 1
    return np.where(observed, 1.0 - frame["content_cosine"].to_numpy(dtype=np.float64), 0.0)


def rules_scores(frame: pd.DataFrame) -> np.ndarray:
    relationship, co_recipient, similarity = behavior_components(frame)
    return (relationship + co_recipient + similarity) / 3.0


def fusion_scores(frame: pd.DataFrame) -> np.ndarray:
    relationship, co_recipient, similarity = behavior_components(frame)
    return (relationship + co_recipient + similarity + content_component(frame)) / 4.0
