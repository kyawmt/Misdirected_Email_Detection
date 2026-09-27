"""Curated examples and the compose directory, from published fictional tables.

Examples come from the validation subsets only and are chosen by the rules in
`med_ui.config.EXAMPLE_RULES`, applied to the policy's stored validation
decisions. Validation draft ids come first from the structural split
manifest (ids and subset names only). The drafts, recipients, and labels
tables are then streamed one record at a time, and only records with a
validation id are kept, so no frozen test record (including every
walkthrough draft) ever enters a table in memory. The CSV parser still has to
read past each frozen record to find the next one; it is dropped at once.
Asking for a frozen-subset draft raises before any lookup.

Scenario, variant, and label columns select examples and fill the "About this
example" story. They never enter the compose form or a request.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from med_api.fixtures import request_from_draft
from med_data.calendar import FROZEN_SUBSETS
from med_ui.config import (
    DESIRED_OUTCOMES,
    EXAMPLE_RULES,
    EXAMPLE_SUBSETS,
    EXPLORATION_SCORES_FILE,
    FAILURE_BASE_EXAMPLE,
    SCENARIO_STORIES,
    SENDER_DOMAIN,
    VALIDATION_EVALUATION_FILE,
    ExampleRule,
)
from med_ui.presentation import DraftForm


class ExampleError(ValueError):
    pass


class FrozenSubsetError(ExampleError):
    pass


@dataclass(frozen=True)
class StoryRecipient:
    address: str
    display_name: str
    intended: bool
    stipulation: str


@dataclass(frozen=True)
class ExampleStory:
    """The fictional story behind an example. Shown beside the form; never model input."""

    scenario_id: str
    scenario_name: str
    summary: str
    desired: str
    recipients: tuple[StoryRecipient, ...]
    recorded: tuple[str, ...]


@dataclass(frozen=True)
class CuratedExample:
    rule: ExampleRule
    draft_id: str
    subset: str
    stored_email_risk: float
    form: DraftForm
    story: ExampleStory


@dataclass
class Catalog:
    contacts: pd.DataFrame
    examples: dict[str, CuratedExample]
    unmatched: dict[str, str]
    subset_of: dict[str, str]
    drafts: pd.DataFrame
    draft_recipients: pd.DataFrame

    def form_for(self, draft_id: str) -> DraftForm:
        """The compose fields of a validation draft. Frozen-subset drafts raise before any lookup."""
        subset = self.subset_of.get(draft_id)
        if subset is None:
            raise ExampleError(f"Unknown draft {draft_id}")
        if subset in FROZEN_SUBSETS:
            raise FrozenSubsetError(f"Refusing a draft from frozen subset {subset}")
        if subset not in EXAMPLE_SUBSETS:
            raise ExampleError(f"Examples come from validation subsets only, not {subset}")
        request = request_from_draft(
            SimpleNamespace(contacts=self.contacts, drafts=self.drafts, draft_recipients=self.draft_recipients),
            draft_id,
        )
        return DraftForm(
            draft_timestamp=request["draft_timestamp"],
            sender=request["sender"]["address"],
            to=tuple(item["address"] for item in request["to"]),
            cc=tuple(item["address"] for item in request["cc"]),
            bcc=tuple(item["address"] for item in request["bcc"]),
            subject=request["subject"],
            body=request["body"],
        )


def _read(path: Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, **kwargs)


def stream_rows(path: Path, keep_ids: set[str]) -> pd.DataFrame:
    """Records of a draft-keyed table whose `draft_id` is in `keep_ids`, read one record at a time.

    Other records are discarded as soon as they are parsed; they never enter
    the returned table or any other retained structure.
    """
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        position = header.index("draft_id")
        kept = [row for row in reader if row[position] in keep_ids]
    return pd.DataFrame(kept, columns=header, dtype=str)


def validation_ids(data_dir: Path) -> tuple[dict[str, str], set[str]]:
    """Subset of every draft id from the structural manifest, and the validation ids to keep."""
    manifest = _read(Path(data_dir) / "split_manifest.csv", usecols=["draft_id", "subset"])
    subset_of = dict(zip(manifest["draft_id"], manifest["subset"], strict=True))
    keep = {draft for draft, subset in subset_of.items() if subset in EXAMPLE_SUBSETS and subset not in FROZEN_SUBSETS}
    return subset_of, keep


def load_contacts(data_dir: Path) -> pd.DataFrame:
    contacts = _read(Path(data_dir) / "contacts.csv")
    contacts["is_internal"] = contacts["is_internal"].map({"true": True, "false": False})
    contacts["directory_visible_from"] = pd.to_datetime(contacts["directory_visible_from"], utc=True)
    return contacts


def load_catalog(data_dir: Path, policy_dir: Path) -> Catalog:
    data_dir, policy_dir = Path(data_dir), Path(policy_dir)
    contacts = load_contacts(data_dir)
    subset_of, keep = validation_ids(data_dir)
    # Only validation records are kept; frozen test records never enter a table.
    drafts = stream_rows(data_dir / "drafts.csv", keep)
    if not set(drafts["subset"]) <= set(EXAMPLE_SUBSETS):
        raise ExampleError("The drafts table disagrees with the split manifest")
    drafts["sent_at"] = pd.to_datetime(drafts["sent_at"], utc=True)
    recipients = stream_rows(data_dir / "draft_recipients.csv", keep)
    recipients["recipient_order"] = recipients["recipient_order"].astype(int)
    labels = stream_rows(data_dir / "labels.csv", keep)
    scores = pd.read_csv(policy_dir / EXPLORATION_SCORES_FILE, float_precision="round_trip")
    evaluation = json.loads((policy_dir / VALIDATION_EVALUATION_FILE).read_text(encoding="utf-8"))
    catalog = Catalog(
        contacts=contacts,
        examples={},
        unmatched={},
        subset_of=subset_of,
        drafts=drafts,
        draft_recipients=recipients,
    )
    for rule in EXAMPLE_RULES:
        try:
            draft_id, email_risk = select_draft(rule, drafts, recipients, scores)
        except ExampleError as error:
            catalog.unmatched[rule.key] = str(error)
            continue
        scenario_id = str(drafts.loc[drafts["draft_id"] == draft_id, "scenario_id"].iloc[0])
        catalog.examples[rule.key] = CuratedExample(
            rule=rule,
            draft_id=draft_id,
            subset=rule.subset,
            stored_email_risk=email_risk,
            form=catalog.form_for(draft_id),
            story=_story(scenario_id, draft_id, contacts, labels, evaluation),
        )
    return catalog


def select_draft(rule: ExampleRule, drafts: pd.DataFrame, recipients: pd.DataFrame, scores: pd.DataFrame) -> tuple[str, float]:
    """Apply one rule to the stored validation decisions. Returns (draft id, stored email risk score)."""
    if rule.subset in FROZEN_SUBSETS:
        raise FrozenSubsetError(f"Rule {rule.key} names frozen subset {rule.subset}")
    candidates = drafts.loc[
        (drafts["subset"] == rule.subset)
        & drafts["scenario_id"].isin(rule.scenario_ids)
        & drafts["scenario_variant"].isin(rule.variants),
        ["draft_id"],
    ]
    table = scores.loc[:, ["draft_id", "email_risk", "misdirected", "warned"]].copy()
    table["draft_id"] = table["draft_id"].astype(str)
    chosen = candidates.merge(table, on="draft_id", how="inner")
    chosen = chosen.loc[
        (chosen["misdirected"].astype(bool) == rule.misdirected)
        & (chosen["warned"].astype(bool) == (rule.stored_decision == "warn"))
    ].copy()
    if chosen.empty:
        raise ExampleError(f"No {rule.subset} draft matches rule {rule.key}")
    counts = recipients.groupby("draft_id").size()
    chosen["recipients"] = chosen["draft_id"].map(counts).fillna(0).astype(int)
    if rule.pick == "median":
        ordered = chosen.sort_values(["email_risk", "draft_id"], kind="mergesort")
        row = ordered.iloc[len(ordered) // 2]
    elif rule.pick == "highest":
        row = chosen.sort_values(["email_risk", "draft_id"], ascending=[False, True], kind="mergesort").iloc[0]
    elif rule.pick == "fewest_recipients_highest":
        row = chosen.sort_values(["recipients", "email_risk", "draft_id"], ascending=[True, False, True], kind="mergesort").iloc[0]
    else:
        raise ExampleError(f"Unknown pick {rule.pick}")
    return str(row["draft_id"]), float(row["email_risk"])


def _story(scenario_id: str, draft_id: str, contacts: pd.DataFrame, labels: pd.DataFrame, evaluation: dict) -> ExampleStory:
    name, summary = SCENARIO_STORIES.get(scenario_id, (scenario_id, ""))
    people = contacts.set_index("contact_id")
    rows = labels.loc[labels["draft_id"] == draft_id]
    recipients = tuple(
        StoryRecipient(
            address=str(people.loc[row.contact_id, "email_address"]),
            display_name=str(people.loc[row.contact_id, "display_name"]),
            intended=row.intended == "true",
            stipulation=str(row.stipulation),
        )
        for row in rows.itertuples(index=False)
    )
    return ExampleStory(
        scenario_id=scenario_id,
        scenario_name=name,
        summary=summary,
        desired=DESIRED_OUTCOMES.get(scenario_id, ""),
        recipients=recipients,
        recorded=tuple(recorded_outcomes(evaluation, scenario_id)),
    )


def recorded_outcomes(evaluation: dict, scenario_id: str) -> list[str]:
    """Recorded validation outcomes for one scenario, from the stored evaluation."""
    lines = []
    for subset in EXAMPLE_SUBSETS:
        slices = evaluation["subsets"].get(subset, {}).get("slices", {}).get("email_by_scenario", [])
        for item in slices:
            if item["slice"] != scenario_id:
                continue
            parts = []
            if item["misdirected"]:
                parts.append(f"warned {item['warned_misdirected']} of {item['misdirected']} misdirected")
            if item["legitimate"]:
                parts.append(f"warned {item['warned_legitimate']} of {item['legitimate']} legitimate")
            lines.append(f"{subset}: " + ", ".join(parts))
    return lines


# ----------------------------------------------------------------- directory


def display_names(contacts: pd.DataFrame) -> dict[str, str]:
    return {
        str(address).strip().casefold(): str(name)
        for address, name in zip(contacts["email_address"], contacts["display_name"], strict=True)
    }


def visible_contacts(contacts: pd.DataFrame, moment: pd.Timestamp | None) -> pd.DataFrame:
    """Contacts listed in the directory at the draft timestamp (all of them if it does not parse)."""
    if moment is None:
        return contacts
    return contacts.loc[contacts["directory_visible_from"] <= moment]


def internal_senders(contacts: pd.DataFrame, moment: pd.Timestamp | None) -> pd.DataFrame:
    visible = visible_contacts(contacts, moment)
    return visible.loc[visible["is_internal"].astype(bool) & (visible["domain"] == SENDER_DOMAIN)]


def contact_label(address: str, names: dict[str, str]) -> str:
    name = names.get(address.strip().casefold())
    return f"{name} <{address}>" if name else address


# ------------------------------------------------------ failure demonstrations


def unknown_address_form(catalog: Catalog) -> DraftForm:
    """The base example with its first To address shortened until it is not in the directory."""
    form = catalog.examples[FAILURE_BASE_EXAMPLE].form
    known = set(display_names(catalog.contacts))
    local, domain = form.to[0].split("@", 1)
    candidate = form.to[0]
    while candidate.casefold() in known and len(local) > 1:
        local = local[:-1]
        candidate = f"{local}@{domain}"
    if candidate.casefold() in known:
        raise ExampleError("Could not derive an address outside the directory")
    return DraftForm(**{**form.__dict__, "to": (candidate,) + form.to[1:]})


def invalid_address_form(catalog: Catalog) -> DraftForm:
    """The base example with "@" in its first To address replaced by ".", a malformed address."""
    form = catalog.examples[FAILURE_BASE_EXAMPLE].form
    return DraftForm(**{**form.__dict__, "to": (form.to[0].replace("@", "."),) + form.to[1:]})
