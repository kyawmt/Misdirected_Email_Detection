"""Published table columns.

Model-visible fields are the only columns a later scoring step may read.
Labels, scenario ids, corruption metadata, and split names are audit columns.
"""

CONTACTS_COLUMNS = [
    "contact_id",
    "display_name",
    "email_address",
    "domain",
    "is_internal",
    "department",
    "directory_visible_from",
    "dataset_version",
]

MESSAGES_COLUMNS = [
    "message_id",
    "thread_id",
    "family_id",
    "sender_contact_id",
    "sent_at",
    "subject",
    "body",
    "body_hash",
    "message_kind",
    "generator_topic",
    "split",
    "dataset_version",
]

MESSAGE_RECIPIENT_COLUMNS = [
    "message_id",
    "contact_id",
    "role",
    "recipient_order",
]

DRAFTS_COLUMNS = [
    "draft_id",
    "family_id",
    "source_message_id",
    "sender_contact_id",
    "sent_at",
    "subject",
    "body",
    "body_hash",
    "split",
    "subset",
    "scenario_id",
    "scenario_variant",
    "generator_topic",
    "withheld_contact_id",
    "is_counterfactual",
    "is_walkthrough",
    "label_source",
    "dataset_version",
]

DRAFT_RECIPIENT_COLUMNS = [
    "draft_id",
    "contact_id",
    "role",
    "recipient_order",
]

LABEL_COLUMNS = [
    "draft_id",
    "contact_id",
    "intended",
    "label_source",
    "label_confidence",
    "scenario_id",
    "stipulation",
    "dataset_version",
]

FEEDBACK_COLUMNS = [
    "feedback_id",
    "draft_id",
    "contact_id",
    "reviewer_id",
    "submitted_at",
    "asserted_intended",
    "confidence",
    "review_status",
    "notes",
    "dataset_version",
]

MANIFEST_COLUMNS = [
    "dataset_version",
    "draft_id",
    "family_id",
    "split",
    "subset",
    "sent_at",
    "scenario_id",
    "scenario_variant",
    "is_misdirected_email",
    "is_walkthrough",
    "frozen",
]

INVALID_FIXTURE_COLUMNS = [
    "fixture_id",
    "category",
    "reason",
    "detail",
    "expected_status",
    "dataset_version",
]

# Columns that must not be passed to a later model as features.
MODEL_INPUT_DENYLIST = frozenset(
    {
        "family_id",
        "source_message_id",
        "split",
        "subset",
        "scenario_id",
        "scenario_variant",
        "generator_topic",
        "withheld_contact_id",
        "is_counterfactual",
        "is_walkthrough",
        "label_source",
        "label_confidence",
        "intended",
        "stipulation",
        "dataset_version",
        "body_hash",
        "message_kind",
        "thread_id",
        "is_misdirected_email",
        "frozen",
        "feedback_id",
        "reviewer_id",
        "asserted_intended",
        "confidence",
        "review_status",
        "notes",
        "submitted_at",
        "fixture_id",
        "category",
        "reason",
        "detail",
        "expected_status",
    }
)

TABLES = {
    "contacts": CONTACTS_COLUMNS,
    "messages": MESSAGES_COLUMNS,
    "message_recipients": MESSAGE_RECIPIENT_COLUMNS,
    "drafts": DRAFTS_COLUMNS,
    "draft_recipients": DRAFT_RECIPIENT_COLUMNS,
    "labels": LABEL_COLUMNS,
    "reviewer_feedback": FEEDBACK_COLUMNS,
    "split_manifest": MANIFEST_COLUMNS,
    "invalid_fixtures": INVALID_FIXTURE_COLUMNS,
}

ROLES = frozenset({"to", "cc", "bcc"})
MESSAGE_KINDS = frozenset({"composed", "reply"})
LABEL_SOURCES = frozenset({"synthetic_stipulated"})
LABEL_CONFIDENCE = frozenset({"certain"})
FEEDBACK_CONFIDENCE = frozenset({"certain", "uncertain"})
REVIEW_STATUS = frozenset({"pending_review", "accepted", "rejected"})
SCENARIO_IDS = frozenset({"S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "routine"})

# Directory and communication fields a scorer may see for one draft.
MODEL_VISIBLE_SENDER_FIELDS = (
    "contact_id",
    "display_name",
    "email_address",
    "domain",
    "is_internal",
    "department",
    "directory_visible_from",
)
