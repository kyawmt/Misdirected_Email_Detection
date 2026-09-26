"""Rebuild published validation drafts as API requests.

Only validation subsets are allowed. The frozen test subsets are refused, so
latency and parity checks cannot touch them. Labels, scenarios, and families
are never copied into the request.
"""

from __future__ import annotations

import pandas as pd

from med_data.calendar import FROZEN_SUBSETS
from med_api.version import SNAPSHOT_ID

ALLOWED_SUBSETS = ("validation_product_like", "validation_diagnostic")


class FixtureError(ValueError):
    pass


def request_from_draft(dataset, draft_id: str) -> dict:
    drafts = dataset.drafts
    draft = drafts.loc[drafts["draft_id"] == draft_id]
    if draft.empty:
        raise FixtureError(f"Unknown draft {draft_id}")
    draft = draft.iloc[0]
    subset = str(draft["subset"])
    if subset in FROZEN_SUBSETS:
        raise FixtureError(f"Refusing to build an API request from frozen subset {subset}")
    if subset not in ALLOWED_SUBSETS:
        raise FixtureError(f"API fixtures come from validation subsets only, not {subset}")
    contacts = dataset.contacts.set_index("contact_id")
    rows = dataset.draft_recipients.loc[dataset.draft_recipients["draft_id"] == draft_id].sort_values("recipient_order")
    payload = {role: [] for role in ("to", "cc", "bcc")}
    for row in rows.itertuples(index=False):
        person = contacts.loc[row.contact_id]
        payload[str(row.role)].append({"address": str(person["email_address"]), "display_name": str(person["display_name"])})
    sender = contacts.loc[draft["sender_contact_id"]]
    moment = pd.Timestamp(draft["sent_at"]).tz_convert("UTC")
    return {
        "draft_timestamp": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sender": {"address": str(sender["email_address"]), "display_name": str(sender["display_name"])},
        **payload,
        "subject": str(draft["subject"]),
        "body": str(draft["body"]),
        "context_snapshot_id": SNAPSHOT_ID,
        "draft_reference": f"fixture-{draft_id}",
    }


def validation_draft_ids(dataset, subset: str = "validation_product_like") -> list[str]:
    if subset not in ALLOWED_SUBSETS:
        raise FixtureError(f"Unsupported subset {subset}")
    chosen = dataset.drafts.loc[dataset.drafts["subset"] == subset].sort_values(["sent_at", "draft_id"], kind="mergesort")
    return chosen["draft_id"].astype(str).tolist()


def example_draft_ids(dataset, validation_scores: pd.DataFrame) -> dict[str, str]:
    """Pick example validation drafts by rule from the policy's validation table.

    - warn: the warned misdirected draft with the lowest email risk score, which
      is the draft whose score set `T_warn` when the selection rule landed on one
    - allow: the allowed routine draft at the median email risk score
    - first_contact: a legitimate first-contact draft (S03 or S06), the allowed
      one with the highest score if any is allowed, otherwise the lowest-scoring

    Scenario and label fields select examples offline. They never enter a request.
    """
    scores = validation_scores.copy()
    scores["draft_id"] = scores["draft_id"].astype(str)
    scores["warned"] = scores["warned"].astype(bool)
    scores["misdirected"] = scores["misdirected"].astype(bool)
    scenarios = dataset.drafts.set_index("draft_id")["scenario_id"].astype(str)
    scores["scenario_id"] = scores["draft_id"].map(scenarios)
    picks = {}
    warned = scores.loc[scores["warned"] & scores["misdirected"]].sort_values(["email_risk", "draft_id"])
    if warned.empty:
        raise FixtureError("No warned misdirected validation draft")
    picks["warn"] = str(warned.iloc[0]["draft_id"])
    routine = scores.loc[~scores["warned"] & ~scores["misdirected"] & (scores["scenario_id"] == "routine")]
    routine = routine.sort_values(["email_risk", "draft_id"])
    if routine.empty:
        raise FixtureError("No allowed routine validation draft")
    picks["allow"] = str(routine.iloc[len(routine) // 2]["draft_id"])
    first = scores.loc[~scores["misdirected"] & scores["scenario_id"].isin(["S03", "S06"])]
    if first.empty:
        raise FixtureError("No legitimate first-contact validation draft")
    allowed = first.loc[~first["warned"]].sort_values(["email_risk", "draft_id"], ascending=[False, True])
    chosen = allowed if not allowed.empty else first.sort_values(["email_risk", "draft_id"])
    picks["first_contact"] = str(chosen.iloc[0]["draft_id"])
    return picks
