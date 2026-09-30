"""Validation-only access to the published dataset.

The monitor never keeps a row of a frozen test subset. Draft ids and their
subsets come from the structural split manifest (two columns only). Every
draft-keyed table is then streamed one record at a time and only validation
records are kept, so no frozen record enters a table. The CSV parser still
reads past a frozen record to find the next record boundary, because a quoted
body can hold newlines; it drops that record at once.

Labels are read here for one purpose only: the simulated reviewer in
`med_monitor.feedback`. No replay, drift, or alert code calls `read_labels`.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from med_api.fixtures import request_from_draft
from med_monitor.version import FROZEN_SUBSETS, VALIDATION_SUBSETS


class FrozenRowError(ValueError):
    """A frozen test subset draft was requested."""


class DataError(ValueError):
    """The published tables disagree with the split manifest."""


def read_features(path: str | Path) -> pd.DataFrame:
    """Feature CSVs are lossless; parse with round-trip precision."""
    return pd.read_csv(path, float_precision="round_trip")


def subsets_by_draft(data_dir: Path) -> dict[str, str]:
    """Subset of every draft, from the structural manifest. Only two columns are parsed."""
    subsets = {}
    with (Path(data_dir) / "split_manifest.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        draft_at, subset_at = header.index("draft_id"), header.index("subset")
        for row in reader:
            subsets[row[draft_at]] = row[subset_at]
    return subsets


def validation_ids(data_dir: Path) -> tuple[dict[str, str], set[str]]:
    """(subset of every draft, ids of the validation drafts the monitor may read)."""
    subset_of = subsets_by_draft(data_dir)
    keep = {draft for draft, subset in subset_of.items() if subset in VALIDATION_SUBSETS and subset not in FROZEN_SUBSETS}
    return subset_of, keep


def require_validation(draft_ids, subset_of: dict[str, str]) -> None:
    """Raise before any lookup when an id is frozen or is not a validation draft."""
    for draft_id in draft_ids:
        subset = subset_of.get(draft_id)
        if subset in FROZEN_SUBSETS:
            raise FrozenRowError(f"Refusing draft {draft_id} from frozen subset {subset}")
        if subset not in VALIDATION_SUBSETS:
            raise DataError(f"Draft {draft_id} is not a validation draft (subset {subset})")


def stream_rows(path: Path, keep_ids: set[str], *, key: str = "draft_id", columns: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Records of a draft-keyed table whose `key` is in `keep_ids`, read one record at a time.

    Other records are discarded as soon as they are parsed. With `columns`,
    only those columns of a kept record are retained.
    """
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        at = header.index(key)
        picked = list(range(len(header))) if columns is None else [header.index(name) for name in columns]
        kept = [[row[index] for index in picked] for row in reader if row[at] in keep_ids]
    return pd.DataFrame(kept, columns=[header[index] for index in picked], dtype=str)


def load_structure(data_dir: Path, keep: set[str]) -> pd.DataFrame:
    """draft_id, subset, sent_at, scenario_id, scenario_variant for validation drafts.

    The manifest also carries a misdirection flag; it is never retained here.
    """
    frame = stream_rows(
        Path(data_dir) / "split_manifest.csv",
        keep,
        columns=("draft_id", "subset", "sent_at", "scenario_id", "scenario_variant"),
    )
    frame["sent_at"] = pd.to_datetime(frame["sent_at"], utc=True)
    return frame


def load_contacts(data_dir: Path) -> pd.DataFrame:
    frame = pd.read_csv(Path(data_dir) / "contacts.csv", dtype=str, keep_default_na=False)
    return frame


def load_requests(data_dir: Path, draft_ids: list[str]) -> dict[str, dict]:
    """Phase 1 API requests for validation drafts. No draft reference, label, or scenario is sent."""
    data_dir = Path(data_dir)
    subset_of, _ = validation_ids(data_dir)
    wanted = set(draft_ids)
    require_validation(wanted, subset_of)
    drafts = stream_rows(data_dir / "drafts.csv", wanted)
    recipients = stream_rows(data_dir / "draft_recipients.csv", wanted)
    if set(drafts["subset"]) - set(VALIDATION_SUBSETS) or set(drafts["draft_id"]) != wanted:
        raise DataError("The drafts table disagrees with the split manifest")
    drafts["sent_at"] = pd.to_datetime(drafts["sent_at"], utc=True)
    recipients["recipient_order"] = recipients["recipient_order"].astype(int)
    dataset = SimpleNamespace(contacts=load_contacts(data_dir), drafts=drafts, draft_recipients=recipients)
    requests = {}
    for draft_id in sorted(wanted):
        payload = request_from_draft(dataset, draft_id)
        payload.pop("draft_reference", None)
        requests[draft_id] = payload
    return requests


def sender_population(data_dir: Path, draft_ids: set[str]) -> dict:
    """How many senders wrote the given validation drafts, and how concentrated they are."""
    data_dir = Path(data_dir)
    subset_of, _ = validation_ids(data_dir)
    require_validation(draft_ids, subset_of)
    frame = stream_rows(data_dir / "drafts.csv", set(draft_ids), columns=("draft_id", "sender_contact_id"))
    counts = Counter(frame["sender_contact_id"])
    largest = max(counts.values())
    return {
        "emails": int(len(frame)),
        "senders": len(counts),
        "largest_sender_emails": int(largest),
        "largest_sender_share": largest / len(frame),
    }


def read_labels(data_dir: Path, draft_ids: set[str]) -> dict[str, bool]:
    """Whether each validation draft is misdirected, from the stipulated recipient labels.

    Used only by the simulated reviewer. A draft is misdirected when any of its
    recipients is unintended.
    """
    data_dir = Path(data_dir)
    subset_of, _ = validation_ids(data_dir)
    require_validation(draft_ids, subset_of)
    labels = stream_rows(data_dir / "labels.csv", set(draft_ids), columns=("draft_id", "contact_id", "intended"))
    if not set(labels["draft_id"]) == set(draft_ids):
        raise DataError("A queued draft has no recipient label")
    unintended = labels.loc[labels["intended"].str.lower() == "false", "draft_id"]
    misdirected = set(unintended)
    return {draft_id: draft_id in misdirected for draft_id in sorted(draft_ids)}


def read_reviewer_feedback(data_dir: Path) -> pd.DataFrame:
    """Reviewer notes about non-frozen drafts. Records about frozen drafts are dropped as parsed."""
    data_dir = Path(data_dir)
    subset_of = subsets_by_draft(data_dir)
    keep = {draft for draft, subset in subset_of.items() if subset not in FROZEN_SUBSETS}
    frame = stream_rows(data_dir / "reviewer_feedback.csv", keep)
    frame["subset"] = frame["draft_id"].map(subset_of)
    return frame


def read_api_feedback(path: Path) -> list[dict]:
    """Click feedback lines written by POST /feedback. Contact ids, never addresses."""
    path = Path(path)
    if not path.exists():
        return []
    lines = []
    for text in path.read_text(encoding="utf-8").splitlines():
        text = text.strip()
        if text:
            lines.append(json.loads(text))
    return lines
