"""Scoring view of one draft.

The view is the Phase 2 boundary for later models: directory fields, the draft
text, addressed recipients, and earlier mail. Labels and generator metadata
are not included.
"""

from med_data.calendar import format_ts
from med_data.history import visible_history
from med_data.schema import MODEL_INPUT_DENYLIST, MODEL_VISIBLE_SENDER_FIELDS


def scoring_view(dataset, draft_id: str) -> dict:
    draft = dataset.drafts.loc[dataset.drafts["draft_id"] == draft_id].iloc[0]
    contacts = dataset.contacts.set_index("contact_id", drop=False)
    draft_recipients = dataset.draft_recipients
    draft_recipients = draft_recipients.loc[draft_recipients["draft_id"] == draft_id].sort_values(
        "recipient_order"
    )
    history = visible_history(dataset, draft_id)
    history_recipients = {
        message_id: group.sort_values("recipient_order")
        for message_id, group in dataset.message_recipients.groupby("message_id", sort=False)
    }
    return {
        "draft_id": draft_id,
        "features": {
            "sent_at": format_ts(draft["sent_at"]),
            "sender": _contact_payload(contacts, draft["sender_contact_id"]),
            "subject": draft["subject"],
            "body": draft["body"],
            "recipients": [
                _addressed(contacts, row) for _, row in draft_recipients.iterrows()
            ],
            "history": [
                _history_message(contacts, history_recipients, row) for _, row in history.iterrows()
            ],
        },
    }


def iter_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from iter_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_keys(item)


def denied_keys(value) -> set[str]:
    return set(iter_keys(value)) & set(MODEL_INPUT_DENYLIST)


def _contact_payload(contacts, contact_id: str) -> dict:
    contact = contacts.loc[contact_id]
    payload = {}
    for field in MODEL_VISIBLE_SENDER_FIELDS:
        cell = contact[field]
        if field == "directory_visible_from":
            cell = format_ts(cell)
        elif field == "is_internal":
            cell = bool(cell)
        payload[field] = cell
    return payload


def _addressed(contacts, row) -> dict:
    payload = _contact_payload(contacts, row["contact_id"])
    payload["role"] = row["role"]
    payload["recipient_order"] = int(row["recipient_order"])
    return payload


def _history_message(contacts, history_recipients, row) -> dict:
    recipients = history_recipients[row["message_id"]]
    return {
        "message_id": row["message_id"],
        "sent_at": format_ts(row["sent_at"]),
        "sender": _contact_payload(contacts, row["sender_contact_id"]),
        "subject": row["subject"],
        "body": row["body"],
        "recipients": [_addressed(contacts, item) for _, item in recipients.iterrows()],
    }
