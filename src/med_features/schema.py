"""Feature matrix contract for the feature specification in `med_features.version`.

Key columns identify a recipient row. They are not model inputs.
Feature columns are the only values a later model may read.
"""

from __future__ import annotations

from med_features.version import FEATURE_SPEC_VERSION

# Days. The recent window is [cutoff - 28 days, cutoff).
RECENT_WINDOW_DAYS = 28
# Used when no earlier pair message exists. It is not a measured age.
RECENCY_FALLBACK_DAYS = 3650.0
# Lifetime rates divide by the sender's observed span, floored at one day.
SPAN_FLOOR_DAYS = 1.0
# A draft is short when content unigrams after preprocessing are below this.
SHORT_TOKEN_MAX = 8
# Display-name Levenshtein similarity that counts as a near identity.
NEAR_NAME_THRESHOLD = 0.8
# A term must appear in at least this many fit documents.
MIN_DF = 2

KEY_COLUMNS = (
    "draft_id",
    "contact_id",
    "recipient_order",
    "feature_spec_version",
)

# Stable order. Later training and serving must use this sequence.
FEATURE_COLUMNS = (
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
    "addressed_recipient_count",
    "co_support_applicable",
    "co_joint_message_count",
    "co_partner_fraction",
    "co_focus_conditional_fraction",
    "co_focus_history_available",
    "name_similarity_max",
    "address_similarity_max",
    "contact_similarity_observed",
    "near_name_count",
    "content_cosine",
    "content_similarity_observed",
    "pair_text_message_count",
    "draft_raw_token_count",
    "draft_text_empty",
    "draft_text_short",
    "draft_text_oov",
    "draft_subject_blank",
    "draft_body_blank",
)

INTEGER_FEATURES = frozenset(
    {
        "sender_outbound_count",
        "sender_history_available",
        "pair_outbound_count",
        "pair_inbound_count",
        "pair_outbound_count_28d",
        "pair_inbound_count_28d",
        "pair_recency_observed",
        "recipient_novel_to_sender",
        "domain_outbound_count",
        "domain_novel_to_sender",
        "domain_seen_in_history",
        "recipient_is_internal",
        "addressed_recipient_count",
        "co_support_applicable",
        "co_joint_message_count",
        "co_focus_history_available",
        "contact_similarity_observed",
        "near_name_count",
        "content_similarity_observed",
        "pair_text_message_count",
        "draft_raw_token_count",
        "draft_text_empty",
        "draft_text_short",
        "draft_text_oov",
        "draft_subject_blank",
        "draft_body_blank",
    }
)

FLOAT_FEATURES = frozenset(
    {
        "sender_history_span_days",
        "pair_outbound_rate_per_day",
        "pair_recency_days",
        "co_partner_fraction",
        "co_focus_conditional_fraction",
        "name_similarity_max",
        "address_similarity_max",
        "content_cosine",
    }
)

INDICATOR_FEATURES = frozenset(
    {
        "sender_history_available",
        "pair_recency_observed",
        "recipient_novel_to_sender",
        "domain_novel_to_sender",
        "domain_seen_in_history",
        "recipient_is_internal",
        "co_support_applicable",
        "co_focus_history_available",
        "contact_similarity_observed",
        "content_similarity_observed",
        "draft_text_empty",
        "draft_text_short",
        "draft_text_oov",
        "draft_subject_blank",
        "draft_body_blank",
    }
)

COUNT_FEATURES = INTEGER_FEATURES - INDICATOR_FEATURES

# Subsets the feature build may materialize. Frozen test subsets stay out.
EXPORT_SUBSETS = (
    "train",
    "validation_product_like",
    "validation_diagnostic",
)

MATRIX_COLUMNS = KEY_COLUMNS + FEATURE_COLUMNS


class FeatureError(ValueError):
    """A draft cannot be transformed under the feature contract."""


def feature_dtype(name: str) -> str:
    if name in INTEGER_FEATURES:
        return "int64"
    if name in FLOAT_FEATURES:
        return "float64"
    raise FeatureError(f"Unknown feature {name}")
