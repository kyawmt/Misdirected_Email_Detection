"""Invariants for a feature matrix.

These checks lock the missing-value contract. They do not score detection quality.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from med_data.schema import MODEL_INPUT_DENYLIST
from med_features.schema import (
    COUNT_FEATURES,
    FEATURE_COLUMNS,
    FEATURE_SPEC_VERSION,
    FLOAT_FEATURES,
    INDICATOR_FEATURES,
    KEY_COLUMNS,
    MATRIX_COLUMNS,
    NEAR_NAME_THRESHOLD,
    RECENCY_FALLBACK_DAYS,
    SHORT_TOKEN_MAX,
    SPAN_FLOOR_DAYS,
)

FORBIDDEN_FEATURE_NAMES = set(MODEL_INPUT_DENYLIST) | {
    "role",
    "bcc",
    "cc",
    "to",
    "message_id",
    "withheld_contact_id",
    "draft_id",
    "contact_id",
    "recipient_order",
}


def schema_problems() -> list[str]:
    problems = []
    if set(FEATURE_COLUMNS) & FORBIDDEN_FEATURE_NAMES:
        problems.append("A feature column collides with an audit field or identifier")
    if set(FLOAT_FEATURES) - set(FEATURE_COLUMNS):
        problems.append("Float feature list is not inside the feature columns")
    if tuple(KEY_COLUMNS + FEATURE_COLUMNS) != MATRIX_COLUMNS:
        problems.append("Matrix column order drifted")
    if len(FEATURE_COLUMNS) != len(set(FEATURE_COLUMNS)):
        problems.append("Feature names are not unique")
    return problems


def validate_feature_frame(frame: pd.DataFrame) -> list[str]:
    """Return human-readable problems. An empty list means the frame is usable."""
    problems = schema_problems()
    if list(frame.columns) != list(MATRIX_COLUMNS):
        problems.append("Column order does not match the feature schema")
        return problems
    if frame.empty:
        return problems
    if frame[list(FEATURE_COLUMNS)].isna().any().any():
        problems.append("Feature matrix contains missing values")
    values = frame[list(FEATURE_COLUMNS)].to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        problems.append("Feature matrix contains a non-finite value")
    if not (frame["feature_spec_version"] == FEATURE_SPEC_VERSION).all():
        problems.append("Feature spec version is not med-features-v1")
    for name in INDICATOR_FEATURES:
        if not frame[name].isin([0, 1]).all():
            problems.append(f"{name} is not a 0/1 indicator")
    for name in COUNT_FEATURES:
        if (frame[name] < 0).any():
            problems.append(f"{name} has a negative count")
    for name in (
        "co_partner_fraction",
        "co_focus_conditional_fraction",
        "name_similarity_max",
        "address_similarity_max",
        "content_cosine",
    ):
        column = frame[name]
        if ((column < 0) | (column > 1)).any():
            problems.append(f"{name} is outside [0, 1]")
    problems.extend(_relationship_problems(frame))
    return problems


def _relationship_problems(frame: pd.DataFrame) -> list[str]:
    problems = []
    available = frame["sender_history_available"] == 1
    if not (available == (frame["sender_outbound_count"] > 0)).all():
        problems.append("sender_history_available does not match the outbound count")
    if (frame.loc[~available, "sender_history_span_days"] != 0).any():
        problems.append("Missing sender history must use span fallback 0")
    if (frame.loc[~available, "pair_outbound_rate_per_day"] != 0).any():
        problems.append("Missing sender history must use rate fallback 0")
    if available.any():
        span = frame.loc[available, "sender_history_span_days"]
        if (span < SPAN_FLOOR_DAYS).any():
            problems.append("Observed sender span is below the one-day floor")
        rate = frame.loc[available, "pair_outbound_count"] / span
        if not np.allclose(rate, frame.loc[available, "pair_outbound_rate_per_day"]):
            problems.append("Pair rate does not match count divided by sender span")
    observed_recency = frame["pair_recency_observed"] == 1
    pair_events = frame["pair_outbound_count"] + frame["pair_inbound_count"]
    if not (observed_recency == (pair_events > 0)).all():
        problems.append("Recency observed flag does not match pair message counts")
    if (frame.loc[~observed_recency, "pair_recency_days"] != RECENCY_FALLBACK_DAYS).any():
        problems.append("Unobserved recency must use the documented fallback")
    if observed_recency.any() and (frame.loc[observed_recency, "pair_recency_days"] <= 0).any():
        problems.append("Observed recency must be strictly positive")
    if not (frame["recipient_novel_to_sender"] == (frame["pair_outbound_count"] == 0).astype(int)).all():
        problems.append("Recipient novelty does not match zero outbound mail")
    if not (frame["domain_novel_to_sender"] == (frame["domain_outbound_count"] == 0).astype(int)).all():
        problems.append("Domain novelty does not match zero outbound mail to that domain")
    if (frame["pair_outbound_count_28d"] > frame["pair_outbound_count"]).any():
        problems.append("28-day outbound count exceeds lifetime outbound count")
    if (frame["pair_inbound_count_28d"] > frame["pair_inbound_count"]).any():
        problems.append("28-day inbound count exceeds lifetime inbound count")
    applicable = frame["co_support_applicable"] == 1
    if not (applicable == (frame["addressed_recipient_count"] >= 2)).all():
        problems.append("Co-support applicability does not match recipient count")
    if (frame.loc[~applicable, "co_joint_message_count"] != 0).any():
        problems.append("Single-recipient drafts must leave joint counts at the fallback")
    if (frame.loc[~applicable, "co_partner_fraction"] != 0).any():
        problems.append("Single-recipient drafts must leave partner fraction undefined")
    if (frame.loc[~applicable, "co_focus_conditional_fraction"] != 0).any():
        problems.append("Conditional co-support is undefined for a single recipient")
    focus = frame["co_focus_history_available"] == 1
    if not (focus == (frame["pair_outbound_count"] > 0)).all():
        problems.append("Focus history flag does not match outbound pair count")
    if (frame.loc[~focus, "co_focus_conditional_fraction"] != 0).any():
        problems.append("Conditional co-support requires outbound history with the recipient")
    if applicable.any() and focus.any():
        both = applicable & focus
        if both.any():
            expected = frame.loc[both, "co_joint_message_count"] / frame.loc[both, "pair_outbound_count"]
            if not np.allclose(expected, frame.loc[both, "co_focus_conditional_fraction"]):
                problems.append("Conditional co-support fraction does not match the joint count")
    similar = frame["contact_similarity_observed"] == 1
    if (frame.loc[~similar, ["name_similarity_max", "address_similarity_max", "near_name_count"]] != 0).any().any():
        problems.append("Unobserved contact similarity must use fallback 0")
    if similar.any():
        near = frame.loc[similar, "near_name_count"] > 0
        names = frame.loc[similar, "name_similarity_max"]
        if near.any() and (names.loc[near] < NEAR_NAME_THRESHOLD).any():
            problems.append("Near-name count disagrees with the name similarity maximum")
        if (~near).any() and (names.loc[~near] >= NEAR_NAME_THRESHOLD).any():
            problems.append("A name at or above the near threshold was not counted")
    content = frame["content_similarity_observed"] == 1
    if (frame.loc[~content, "content_cosine"] != 0).any():
        problems.append("Unobserved content similarity must use cosine fallback 0")
    if content.any():
        if (frame.loc[content, "pair_text_message_count"] < 1).any():
            problems.append("Observed content similarity requires pair text")
        if (frame.loc[content, "draft_text_empty"] != 0).any() or (frame.loc[content, "draft_text_oov"] != 0).any():
            problems.append("Empty or out-of-vocabulary drafts cannot have an observed cosine")
    empty = frame["draft_text_empty"] == 1
    if not (empty == ((frame["draft_subject_blank"] == 1) & (frame["draft_body_blank"] == 1))).all():
        problems.append("Empty-text flag does not match blank subject and body")
    if (frame.loc[empty, "draft_text_oov"] != 0).any():
        problems.append("An empty draft is not out of vocabulary")
    if (frame.loc[empty, "draft_raw_token_count"] != 0).any():
        problems.append("An empty draft must have no content tokens")
    short = frame["draft_raw_token_count"] < SHORT_TOKEN_MAX
    if not (frame["draft_text_short"] == short.astype(int)).all():
        problems.append("Short-text flag does not match the token threshold")
    if (frame.loc[frame["draft_text_oov"] == 1, "draft_text_empty"] != 0).any():
        problems.append("Out-of-vocabulary text must be non-empty")
    if frame["pair_text_message_count"].map(lambda value: not math.isfinite(value)).any():
        problems.append("Pair text count is not finite")
    return problems
