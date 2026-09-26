"""Feature groups for the recorded ablations.

Column order always follows FEATURE_COLUMNS. Behavior-only drops the three
content-cosine columns. Draft-length indicators stay, because they are evidence
limits rather than the cosine itself. Drop-content removes every text-derived
column, the draft-length indicators included.
"""

from med_features.schema import FEATURE_COLUMNS

RELATIONSHIP = (
    "sender_outbound_count",
    "sender_history_available",
    "sender_history_span_days",
    "pair_outbound_count",
    "pair_inbound_count",
    "pair_outbound_count_28d",
    "pair_inbound_count_28d",
    "pair_outbound_rate_per_day",
    "pair_recency_days",
    "pair_recency_observed",
    "recipient_novel_to_sender",
    "domain_outbound_count",
    "domain_novel_to_sender",
    "domain_seen_in_history",
    "recipient_is_internal",
)

CO_RECIPIENT = (
    "addressed_recipient_count",
    "co_support_applicable",
    "co_joint_message_count",
    "co_partner_fraction",
    "co_focus_conditional_fraction",
    "co_focus_history_available",
)

SIMILARITY = (
    "name_similarity_max",
    "address_similarity_max",
    "contact_similarity_observed",
    "near_name_count",
)

CONTENT_CORE = (
    "content_cosine",
    "content_similarity_observed",
    "pair_text_message_count",
)

TEXT_FLAGS = (
    "draft_raw_token_count",
    "draft_text_empty",
    "draft_text_short",
    "draft_text_oov",
    "draft_subject_blank",
    "draft_body_blank",
)

# Counts take log1p before a logistic model standardizes them.
LOG_COUNTS = (
    "sender_outbound_count",
    "pair_outbound_count",
    "pair_inbound_count",
    "pair_outbound_count_28d",
    "pair_inbound_count_28d",
    "domain_outbound_count",
    "addressed_recipient_count",
    "co_joint_message_count",
    "near_name_count",
    "pair_text_message_count",
    "draft_raw_token_count",
)

# Extended in med-model-v2 so a selected C is not stopped by the grid edge.
# A larger C weakens regularization; it does not fix collinearity.
C_GRID = (0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0)
TREE_GRID = (
    {"max_depth": 2, "min_samples_leaf": 20},
    {"max_depth": 2, "min_samples_leaf": 50},
    {"max_depth": 3, "min_samples_leaf": 20},
    {"max_depth": 3, "min_samples_leaf": 50},
    {"max_depth": 4, "min_samples_leaf": 20},
    {"max_depth": 4, "min_samples_leaf": 50},
)


def ordered(names: tuple[str, ...] | list[str]) -> list[str]:
    wanted = set(names)
    return [name for name in FEATURE_COLUMNS if name in wanted]


def ablation_columns(ablation: str) -> list[str]:
    """Return the feature list for one recorded ablation."""
    if ablation == "all":
        return list(FEATURE_COLUMNS)
    if ablation == "behavior_only":
        return [column for column in FEATURE_COLUMNS if column not in CONTENT_CORE]
    if ablation == "drop_relationship":
        return [column for column in FEATURE_COLUMNS if column not in RELATIONSHIP]
    if ablation == "drop_similarity":
        return [column for column in FEATURE_COLUMNS if column not in SIMILARITY]
    if ablation == "drop_content":
        return [column for column in FEATURE_COLUMNS if column not in CONTENT_CORE + TEXT_FLAGS]
    if ablation == "content_only":
        return ordered(CONTENT_CORE + TEXT_FLAGS)
    raise KeyError(ablation)


ABLATIONS = (
    "all",
    "behavior_only",
    "drop_content",
    "drop_relationship",
    "drop_similarity",
    "content_only",
)
