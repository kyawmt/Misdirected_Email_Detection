"""History visible to a draft.

A draft may use only sent messages strictly earlier than its timestamp.
Messages in its family, and earlier copies of its non-empty text, are excluded
so a clean twin or a same-text source cannot answer the assessment.
"""

import pandas as pd

from med_data.text import body_hash


def family_body_hashes(messages: pd.DataFrame, family_id: str, draft_body: str) -> set[str]:
    hashes = set(messages.loc[messages["family_id"] == family_id, "body_hash"].tolist())
    own = body_hash(draft_body)
    if own:
        hashes.add(own)
    hashes.discard("")
    return hashes


def visible_history(dataset, draft_id: str) -> pd.DataFrame:
    drafts = dataset.drafts
    matched = drafts.loc[drafts["draft_id"] == draft_id]
    if matched.empty:
        raise KeyError(draft_id)
    draft = matched.iloc[0]
    messages = dataset.messages
    cutoff = draft["sent_at"]
    mask = messages["sent_at"] < cutoff
    mask &= messages["family_id"] != draft["family_id"]
    blocked = family_body_hashes(messages, draft["family_id"], draft["body"])
    if blocked:
        mask &= ~messages["body_hash"].isin(blocked)
    history = messages.loc[mask].sort_values(["sent_at", "message_id"], kind="mergesort")
    return history.reset_index(drop=True)
