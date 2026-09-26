"""Deterministic fictional mailbox and labeled assessment drafts.

Sent messages are the communication record. Counterfactual mistakes are drafts
only: they are not inserted into sent history, so a later draft cannot learn
the mistake as if it had been sent. Clean twins of a corrupted draft stay in
the same family, split, and subset.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from med_data.calendar import (
    ASSESSMENT_SPLITS,
    FROZEN_SUBSETS,
    format_ts,
    split_bounds,
    split_for,
    weeks_in,
    iter_weeks,
)
from med_data.roster import (
    DIRECTORY_OPEN,
    ELLIOT,
    FIRST_NAMES,
    JORDAN,
    LAST_NAMES,
    LEE,
    LOOKALIKE_PAIRS,
    MAYA,
    NOAH,
    PARTNER_BRANDS,
    PLANS,
    PROJECT_BCC,
    PROJECT_CC,
    PROJECT_TO,
    PRYA,
    QUINN,
    RESTRICTED_TOPICS,
    RINA,
    SAM,
    VENDORS,
    Contact,
    Lane,
    SplitPlan,
    core_contacts,
)
from med_data.schema import (
    CONTACTS_COLUMNS,
    DRAFT_RECIPIENT_COLUMNS,
    DRAFTS_COLUMNS,
    FEEDBACK_COLUMNS,
    INVALID_FIXTURE_COLUMNS,
    LABEL_COLUMNS,
    MANIFEST_COLUMNS,
    MESSAGE_RECIPIENT_COLUMNS,
    MESSAGES_COLUMNS,
)
from med_data.templates import render, render_reply
from med_data.text import body_hash
from med_data.version import DATASET_VERSION, GENERATOR_VERSION, SEED

LABEL_SOURCE = "synthetic_stipulated"


@dataclass
class Dataset:
    contacts: pd.DataFrame
    messages: pd.DataFrame
    message_recipients: pd.DataFrame
    drafts: pd.DataFrame
    draft_recipients: pd.DataFrame
    labels: pd.DataFrame
    reviewer_feedback: pd.DataFrame
    split_manifest: pd.DataFrame
    invalid_fixtures: pd.DataFrame
    seed: int
    summary: dict


def generate_dataset(seed: int = SEED) -> Dataset:
    builder = _Builder(seed)
    return builder.build()


def spread_take(items: list, count: int) -> list:
    if count == 0:
        return []
    if count > len(items):
        raise ValueError(f"Need {count} items but only {len(items)} are available")
    if count == len(items):
        return list(items)
    step = len(items) / count
    chosen = []
    used: set[int] = set()
    for index in range(count):
        cursor = int(index * step)
        while cursor in used:
            cursor += 1
        if cursor >= len(items):
            raise ValueError("Unable to spread a sample without replacement")
        used.add(cursor)
        chosen.append(items[cursor])
    return chosen


def _has(message: dict, contact_id: str) -> bool:
    return any(row["contact_id"] == contact_id for row in message["recipients"])


def _has_role(message: dict, role: str) -> bool:
    return any(row["role"] == role for row in message["recipients"])


def _project_group_with_bcc(message: dict) -> bool:
    forbidden = (*VENDORS, *(pair[1] for pair in LOOKALIKE_PAIRS))
    return (
        _has_role(message, "cc")
        and _has_role(message, "bcc")
        and not any(_has(message, contact) for contact in forbidden)
    )


class _Builder:
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.contacts: dict[str, Contact] = {}
        self.messages: list[dict] = []
        self.drafts: list[dict] = []
        self.feedback: list[dict] = []
        self.pools: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
        self.used: set[str] = set()
        self.timestamps: set[datetime] = set()
        self.restricted = dict(RESTRICTED_TOPICS)
        self.msg_i = 0
        self.draft_i = 0
        self.feedback_i = 0
        self.ticket_i = 0
        self.name_i = 0
        self.gen_i = 0
        self.brand_i = 0
        self.s04_people: list[str] = []
        self.s07_by_split: dict[str, list[str]] = {}
        self.facilities_people: list[str] = []

    def build(self) -> Dataset:
        self._load_core_contacts()
        self._create_facilities_pool()
        self._emit_routine()
        for split in ASSESSMENT_SPLITS:
            self._emit_split_scenarios(split)
        self._emit_walkthrough()
        self._emit_feedback()
        return self._assemble()

    def _load_core_contacts(self) -> None:
        for contact in core_contacts():
            self._add_contact(contact)

    def _add_contact(self, contact: Contact) -> None:
        if contact.contact_id in self.contacts:
            raise RuntimeError(f"Duplicate contact id {contact.contact_id}")
        if contact.email_address in {row.email_address for row in self.contacts.values()}:
            raise RuntimeError(f"Duplicate email {contact.email_address}")
        self.contacts[contact.contact_id] = contact

    def _invent(self, *, hint: str, department: str, domain: str, visible: datetime) -> Contact:
        first = FIRST_NAMES[self.name_i % len(FIRST_NAMES)]
        last = LAST_NAMES[self.name_i // len(FIRST_NAMES)]
        self.name_i += 1
        if self.name_i // len(FIRST_NAMES) >= len(LAST_NAMES):
            raise RuntimeError("Name bank exhausted")
        email = f"{first}.{last}@{domain}".lower()
        self.gen_i += 1
        contact = Contact(
            contact_id=f"c_{hint}_{self.gen_i:03d}",
            display_name=f"{first} {last}",
            email_address=email,
            domain=domain,
            is_internal=domain == "demo.example",
            department=department,
            directory_visible_from=visible,
        )
        self._add_contact(contact)
        return contact

    def _create_facilities_pool(self) -> None:
        for _ in range(4):
            contact = self._invent(
                hint="fac",
                department="Facilities",
                domain="demo.example",
                visible=DIRECTORY_OPEN,
            )
            self.s04_people.append(contact.contact_id)
            self.restricted[contact.contact_id] = frozenset({"facilities"})
        for split in ASSESSMENT_SPLITS:
            people = []
            count = PLANS[split].hard_negative.get("s07", 0) + PLANS[split].diagnostic_legitimate.get("s07", 0)
            for _ in range(count):
                contact = self._invent(
                    hint="fac",
                    department="Facilities",
                    domain="demo.example",
                    visible=DIRECTORY_OPEN,
                )
                people.append(contact.contact_id)
                self.restricted[contact.contact_id] = frozenset({"facilities", "kickoff"})
            self.s07_by_split[split] = people
        self.facilities_people = [SAM, "c_hana", *self.s04_people]
        for people in self.s07_by_split.values():
            self.facilities_people.extend(people)

    def _lanes(self) -> list[Lane]:
        lanes = [
            Lane(MAYA, PROJECT_TO, PROJECT_CC, (), "project_update", (0, 1, 2, 3, 4), repeats=8),
            # Intended Bcc on ordinary project mail. Without this, Bcc appears only on mistakes.
            Lane(MAYA, PROJECT_TO, PROJECT_CC, PROJECT_BCC, "project_update", (1, 3), repeats=2),
            Lane(MAYA, ("c_chris", NOAH, "c_elena"), ("c_marcus",), (), "budget", (1, 3), repeats=2),
            Lane(MAYA, (PRYA,), (QUINN,), (), "compensation", (0, 2, 4), repeats=2),
            Lane("c_noah", ("c_elena", "c_taylor", "c_lena"), (), (), "project_update", (0, 2, 4), repeats=2),
            Lane("c_elena", (NOAH, "c_taylor"), ("c_chris",), (), "project_update", (1, 3), repeats=2),
            Lane("c_taylor", (NOAH,), (), (), "project_update", (2,), repeats=2),
            Lane("c_alex_chan", ("c_avery", "c_devon"), (), (), "staffing", (1, 4), repeats=1),
            Lane("c_alex_chen", (MAYA,), (), (), "office_equipment", (4,), repeats=1),
            Lane(PRYA, (QUINN,), (), (), "compensation", (3,), repeats=1),
            Lane("c_chris", ("c_marcus",), (), (), "budget", (0, 3), repeats=1),
            Lane(SAM, ("c_hana",), (), (), "facilities", (4,), repeats=1),
        ]
        for intended, _lookalike in LOOKALIKE_PAIRS:
            lanes.append(Lane(MAYA, (intended,), (), (), "staffing", (0, 2, 4), repeats=2))
        for _intended, lookalike in LOOKALIKE_PAIRS:
            lanes.append(Lane(MAYA, (lookalike,), (), (), "office_equipment", (1, 3), repeats=2))
        for vendor in VENDORS:
            lanes.append(Lane(MAYA, (vendor,), (), (), "purchase_scheduling", (0, 2, 4), repeats=2))
        for index, person in enumerate(self.facilities_people):
            lanes.append(Lane(MAYA, (person,), (), (), "facilities", (index % 5,), repeats=1))
        return lanes

    def _emit_routine(self) -> None:
        lanes = self._lanes()
        for week in iter_weeks():
            for lane_index, lane in enumerate(lanes):
                for day in lane.days:
                    for copy_idx in range(lane.repeats):
                        moment = week + timedelta(days=day, minutes=9 * 60 + lane_index * 10 + copy_idx)
                        self._emit_composed(
                            sender=lane.sender,
                            to=lane.to,
                            cc=lane.cc,
                            bcc=lane.bcc,
                            when=moment,
                            topic=lane.topic,
                            selectable=True,
                        )

    def _next_message_id(self) -> str:
        self.msg_i += 1
        return f"m{self.msg_i:06d}"

    def _next_draft_id(self) -> str:
        self.draft_i += 1
        return f"d{self.draft_i:06d}"

    def _recipients(self, to: tuple[str, ...] | list[str], cc=(), bcc=()) -> list[dict]:
        rows = []
        order = 0
        for role, people in (("to", to), ("cc", cc), ("bcc", bcc)):
            for person in people:
                rows.append({"contact_id": person, "role": role, "recipient_order": order})
                order += 1
        if not rows:
            raise RuntimeError("A message needs at least one recipient")
        if len({row["contact_id"] for row in rows}) != len(rows):
            raise RuntimeError("Duplicate recipient on one message")
        return rows

    def _slots(self, sender: str, recipients: list[dict], when: datetime, ref: str) -> dict[str, str]:
        self.ticket_i += 1
        to_names = [
            self.contacts[row["contact_id"]].display_name.split()[0]
            for row in recipients
            if row["role"] == "to"
        ]
        if not to_names:
            to_names = [self.contacts[recipients[0]["contact_id"]].display_name.split()[0]]
        return {
            "sender_name": self.contacts[sender].display_name.split()[0],
            "to_names": ", ".join(to_names),
            "week": when.astimezone(when.tzinfo).strftime("%Y-%m-%d"),
            "ticket": f"T-{self.ticket_i:05d}",
            "ref": ref,
        }

    def _guard_directory(self, contact_id: str, when: datetime) -> None:
        contact = self.contacts[contact_id]
        if contact.directory_visible_from > when:
            raise RuntimeError(f"{contact_id} is not in the directory at {format_ts(when)}")

    def _guard_topic(self, recipients: list[dict], topic: str) -> None:
        for row in recipients:
            allowed = self.restricted.get(row["contact_id"])
            if allowed is not None and topic not in allowed:
                raise RuntimeError(f"{row['contact_id']} cannot be sent topic {topic}")

    def _store_message(
        self,
        *,
        message_id: str,
        sender: str,
        recipients: list[dict],
        when: datetime,
        topic: str,
        subject: str,
        body: str,
        kind: str,
        family_id: str,
        thread_id: str,
        selectable: bool,
    ) -> dict:
        self._guard_directory(sender, when)
        for row in recipients:
            self._guard_directory(row["contact_id"], when)
        self._guard_topic(recipients, topic)
        if when in self.timestamps:
            raise RuntimeError(f"Duplicate message timestamp {format_ts(when)}")
        self.timestamps.add(when)
        message = {
            "message_id": message_id,
            "thread_id": thread_id,
            "family_id": family_id,
            "sender_contact_id": sender,
            "sent_at": when,
            "subject": subject,
            "body": body,
            "message_kind": kind,
            "generator_topic": topic,
            "split": split_for(when),
            "selectable": selectable,
            "recipients": recipients,
        }
        self.messages.append(message)
        if selectable:
            self.pools[(message["split"], topic, sender)].append(message)
        return message

    def _emit_composed(
        self,
        *,
        sender: str,
        to,
        cc=(),
        bcc=(),
        when: datetime,
        topic: str,
        selectable: bool,
        subject: str | None = None,
        body: str | None = None,
        reply: bool = True,
    ) -> dict:
        recipients = self._recipients(to, cc, bcc)
        message_id = self._next_message_id()
        if subject is None or body is None:
            slots = self._slots(sender, recipients, when, message_id)
            rendered_subject, rendered_body = render(topic, self.rng, **slots)
            subject = rendered_subject if subject is None else subject
            body = rendered_body if body is None else body
        message = self._store_message(
            message_id=message_id,
            sender=sender,
            recipients=recipients,
            when=when,
            topic=topic,
            subject=subject,
            body=body,
            kind="composed",
            family_id=f"fam_{message_id}",
            thread_id=f"thr_{message_id}",
            selectable=selectable,
        )
        if reply:
            self._emit_reply(message)
        return message

    def _emit_reply(self, parent: dict) -> None:
        reply_sender = next(row["contact_id"] for row in parent["recipients"] if row["role"] == "to")
        recipients = self._recipients((parent["sender_contact_id"],))
        # Thirty seconds later keeps the reply off the one-minute grid used by composed mail.
        when = parent["sent_at"] + timedelta(seconds=30)
        if split_for(when) != parent["split"]:
            raise RuntimeError("Reply crossed a split boundary")
        message_id = self._next_message_id()
        slots = self._slots(reply_sender, recipients, when, message_id)
        slots["subject"] = parent["subject"]
        subject, body = render_reply(parent["generator_topic"], self.rng, **slots)
        self._store_message(
            message_id=message_id,
            sender=reply_sender,
            recipients=recipients,
            when=when,
            topic=parent["generator_topic"],
            subject=subject,
            body=body,
            kind="reply",
            family_id=f"fam_{message_id}",
            thread_id=parent["thread_id"],
            selectable=False,
        )

    def _add_draft(
        self,
        *,
        sender: str,
        recipients: list[dict],
        when: datetime,
        subject: str,
        body: str,
        subset: str,
        scenario_id: str,
        scenario_variant: str,
        topic: str,
        family_id: str,
        source_message_id: str = "",
        withheld: str = "",
        counterfactual: bool,
        walkthrough: bool = False,
    ) -> dict:
        if not recipients:
            raise RuntimeError("Draft has no recipients")
        if len({row["contact_id"] for row in recipients}) != len(recipients):
            raise RuntimeError("Draft repeats a recipient")
        self._guard_directory(sender, when)
        for row in recipients:
            self._guard_directory(row["contact_id"], when)
        if not self.contacts[sender].is_internal:
            raise RuntimeError("Assessment drafts are sent by the fictional organization")
        draft = {
            "draft_id": self._next_draft_id(),
            "family_id": family_id,
            "source_message_id": source_message_id,
            "sender_contact_id": sender,
            "sent_at": when,
            "subject": subject,
            "body": body,
            "split": split_for(when),
            "subset": subset,
            "scenario_id": scenario_id,
            "scenario_variant": scenario_variant,
            "generator_topic": topic,
            "withheld_contact_id": withheld,
            "is_counterfactual": counterfactual,
            "is_walkthrough": walkthrough,
            "recipients": recipients,
        }
        if draft["split"] == "warmup":
            raise RuntimeError("Warmup mail is history only")
        self.drafts.append(draft)
        return draft

    def _label_rows(self, recipients: list[dict], intended_ids: set[str], bad: str, good: str) -> list[dict]:
        labeled = []
        for row in recipients:
            intended = row["contact_id"] in intended_ids
            labeled.append(
                {
                    **row,
                    "intended": intended,
                    "stipulation": good if intended else bad,
                }
            )
        return labeled

    def _take(self, split: str, topic: str, sender: str, count: int, predicate=None) -> list[dict]:
        pool = [
            message
            for message in self.pools[(split, topic, sender)]
            if message["message_id"] not in self.used and (predicate is None or predicate(message))
        ]
        pool.sort(key=lambda message: (message["sent_at"], message["message_id"]))
        try:
            chosen = spread_take(pool, count)
        except ValueError as exc:
            raise RuntimeError(
                f"Pool {split}/{topic}/{sender} has {len(pool)} messages, need {count}"
            ) from exc
        for message in chosen:
            self.used.add(message["message_id"])
        return chosen

    def _special_times(self, split: str, count: int, hour: int, minute_base: int = 0) -> list[datetime]:
        weeks = weeks_in(split)
        if split == "test":
            weeks = weeks[:-1]
        if len(weeks) > count + 1:
            weeks = weeks[1:]
        chosen = spread_take(weeks, count)
        return [
            week + timedelta(days=2, hours=hour, minutes=minute_base + index)
            for index, week in enumerate(chosen)
        ]

    def _emit_split_scenarios(self, split: str) -> None:
        plan = PLANS[split]
        self._emit_clone_kind(split, plan, "s01", self._s01_sources(split, plan), self._s01_variant)
        self._emit_clone_kind(split, plan, "s02", self._s02_sources(split, plan), self._s02_variant)
        self._emit_clone_kind(split, plan, "s04", self._s04_sources(split, plan), self._s04_variant)
        self._emit_s08(split, plan)
        self._emit_little_bad(split, plan)
        self._emit_pool_legitimate(split, plan)
        self._emit_first_contacts(split, plan, "s03", "Program Delivery", "demo.example")
        self._emit_first_contacts(split, plan, "s06", "External Partner", None)
        self._emit_s07(split, plan)
        self._emit_cold_starts(split, plan)
        self._emit_little_ok(split, plan)
        self._emit_routine_drafts(split, plan)

    def _counts(self, plan: SplitPlan, kind: str) -> tuple[int, int]:
        return plan.misdirected.get(kind, 0), plan.diagnostic_misdirected.get(kind, 0)

    def _emit_clone_kind(self, split, plan, kind, sources, builder) -> None:
        product_n, diagnostic_n = self._counts(plan, kind)
        expected = product_n + diagnostic_n
        if len(sources) != expected:
            raise RuntimeError(f"{kind} source count {len(sources)} != {expected}")
        for index, source in enumerate(sources):
            if index < product_n:
                subset = plan.product_subset
                twin = False
            else:
                subset = plan.diagnostic_subset
                twin = True
            builder(source, subset=subset, twin=twin, ordinal=index)

    def _s01_sources(self, split: str, plan: SplitPlan) -> list[tuple[dict, tuple[str, str]]]:
        count = sum(self._counts(plan, "s01"))
        assigned: list[tuple[dict, tuple[str, str]] | None] = [None] * count
        for pair_index, pair in enumerate(LOOKALIKE_PAIRS):
            indexes = list(range(pair_index, count, len(LOOKALIKE_PAIRS)))
            if not indexes:
                continue
            intended, lookalike = pair
            found = self._take(
                split,
                "staffing",
                MAYA,
                len(indexes),
                lambda message, intended=intended, lookalike=lookalike: _has(message, intended)
                and not _has(message, lookalike),
            )
            for slot, source in zip(indexes, found):
                assigned[slot] = (source, pair)
        return assigned  # type: ignore[return-value]

    def _s01_variant(self, source_pair, *, subset, twin, ordinal) -> None:
        source, (intended, lookalike) = source_pair
        swapped = []
        for row in source["recipients"]:
            contact_id = lookalike if row["contact_id"] == intended else row["contact_id"]
            swapped.append({**row, "contact_id": contact_id})
        intended_ids = {row["contact_id"] for row in swapped if row["contact_id"] != lookalike}
        labeled = self._label_rows(
            swapped,
            intended_ids,
            "Stipulated lookalike replacement. Name similarity is not the label.",
            "Kept from the legitimate recipient list.",
        )
        self._draft_from_source(
            source,
            subset=subset,
            kind="s01",
            labeled=labeled,
            withheld=intended,
            twin=twin,
            topic="staffing",
        )

    def _s02_sources(self, split: str, plan: SplitPlan) -> list[dict]:
        count = sum(self._counts(plan, "s02"))
        return self._take(
            split,
            "budget",
            MAYA,
            count,
            lambda message: not any(_has(message, vendor) for vendor in VENDORS),
        )

    def _s02_variant(self, source, *, subset, twin, ordinal) -> None:
        vendor = VENDORS[ordinal % len(VENDORS)]
        rows = [
            *source["recipients"],
            {
                "contact_id": vendor,
                "role": "cc",
                "recipient_order": len(source["recipients"]),
            },
        ]
        intended_ids = {row["contact_id"] for row in source["recipients"]}
        labeled = self._label_rows(
            rows,
            intended_ids,
            "Stipulated accidental addition. External status is not the label.",
            "Kept from the legitimate recipient list.",
        )
        self._draft_from_source(
            source,
            subset=subset,
            kind="s02",
            labeled=labeled,
            withheld="",
            twin=twin,
            topic="budget",
        )

    def _s04_sources(self, split: str, plan: SplitPlan) -> list[dict]:
        count = sum(self._counts(plan, "s04"))
        return self._take(split, "compensation", MAYA, count)

    def _s04_variant(self, source, *, subset, twin, ordinal) -> None:
        person = self.s04_people[ordinal % len(self.s04_people)]
        rows = [{"contact_id": person, "role": "to", "recipient_order": 0}]
        labeled = self._label_rows(
            rows,
            set(),
            "Stipulated mismatch: familiar contact, compensation content intended for a people partner.",
            "",
        )
        self._draft_from_source(
            source,
            subset=subset,
            kind="s04",
            labeled=labeled,
            withheld=PRYA,
            twin=twin,
            topic="compensation",
        )

    def _draft_from_source(
        self,
        source,
        *,
        subset,
        kind,
        labeled,
        withheld,
        twin,
        topic,
        subject=None,
        body=None,
    ) -> None:
        scenario_id, variant = _meta(kind)
        self._add_draft(
            sender=source["sender_contact_id"],
            recipients=labeled,
            when=source["sent_at"],
            subject=source["subject"] if subject is None else subject,
            body=source["body"] if body is None else body,
            subset=subset,
            scenario_id=scenario_id,
            scenario_variant=variant,
            topic=topic,
            family_id=source["family_id"],
            source_message_id=source["message_id"],
            withheld=withheld,
            counterfactual=True,
        )
        if twin:
            self._add_clean_twin(source, subset, scenario_id)

    def _add_clean_twin(self, source, subset, scenario_id) -> None:
        labeled = [
            {
                **row,
                "intended": True,
                "stipulation": "Clean twin of a corrupted draft. Addressed recipients were intended.",
            }
            for row in source["recipients"]
        ]
        self._add_draft(
            sender=source["sender_contact_id"],
            recipients=labeled,
            when=source["sent_at"],
            subject=source["subject"],
            body=source["body"],
            subset=subset,
            scenario_id=scenario_id,
            scenario_variant="clean_twin",
            topic=source["generator_topic"],
            family_id=source["family_id"],
            source_message_id=source["message_id"],
            withheld="",
            counterfactual=False,
        )

    def _emit_s08(self, split: str, plan: SplitPlan) -> None:
        kinds = ("s08_cc", "s08_bcc", "s08_two")
        product_total = sum(plan.misdirected.get(kind, 0) for kind in kinds)
        diag_total = sum(plan.diagnostic_misdirected.get(kind, 0) for kind in kinds)
        all_count = plan.diagnostic_legitimate.get("s08_all", 0)
        # Reserve all-intended copies that already have a legitimate Bcc before corruptions draw from the pool.
        all_sources = (
            self._take(split, "project_update", MAYA, all_count, _project_group_with_bcc)
            if all_count
            else []
        )
        sources = self._take(
            split,
            "project_update",
            MAYA,
            product_total + diag_total,
            lambda message: _has_role(message, "cc")
            and not any(_has(message, contact) for contact in (*VENDORS, *(pair[1] for pair in LOOKALIKE_PAIRS))),
        )
        cursor = 0
        for kind in kinds:
            for ordinal in range(plan.misdirected.get(kind, 0)):
                self._s08_variant(sources[cursor], kind, plan.product_subset, twin=False, ordinal=ordinal)
                cursor += 1
            for ordinal in range(plan.diagnostic_misdirected.get(kind, 0)):
                self._s08_variant(sources[cursor], kind, plan.diagnostic_subset, twin=True, ordinal=ordinal)
                cursor += 1
        for source in all_sources:
            self._draft_as_sent(
                source,
                subset=plan.diagnostic_subset,
                scenario_id="S08",
                variant="all_intended",
                topic="project_update",
                stipulation="Stipulated all-intended group mail. Roles differ, and every recipient was intended.",
            )

    def _s08_variant(self, source, kind, subset, twin, ordinal) -> None:
        rows = [dict(row) for row in source["recipients"]]
        lookalike = LOOKALIKE_PAIRS[ordinal % len(LOOKALIKE_PAIRS)][1]
        vendor = VENDORS[ordinal % len(VENDORS)]
        if kind in {"s08_cc", "s08_two"}:
            rows.append({"contact_id": lookalike, "role": "cc", "recipient_order": len(rows)})
        if kind in {"s08_bcc", "s08_two"}:
            rows.append({"contact_id": vendor, "role": "bcc", "recipient_order": len(rows)})
        intended_ids = {row["contact_id"] for row in source["recipients"]}
        labeled = self._label_rows(
            rows,
            intended_ids,
            "Stipulated unintended recipient in a multi-recipient draft.",
            "Kept from the legitimate recipient list.",
        )
        self._draft_from_source(
            source,
            subset=subset,
            kind=kind,
            labeled=labeled,
            withheld="",
            twin=twin,
            topic="project_update",
        )

    def _emit_little_bad(self, split: str, plan: SplitPlan) -> None:
        product_n, diagnostic_n = self._counts(plan, "s09_little_bad")
        sources = self._s01_sources_raw(split, product_n + diagnostic_n)
        for index, (source, pair) in enumerate(sources):
            subset = plan.product_subset if index < product_n else plan.diagnostic_subset
            intended, lookalike = pair
            swapped = []
            for row in source["recipients"]:
                contact_id = lookalike if row["contact_id"] == intended else row["contact_id"]
                swapped.append({**row, "contact_id": contact_id})
            intended_ids = {row["contact_id"] for row in swapped if row["contact_id"] != lookalike}
            labeled = self._label_rows(
                swapped,
                intended_ids,
                "Stipulated unintended recipient. Empty text is not the label.",
                "Kept from the legitimate recipient list.",
            )
            self._draft_from_source(
                source,
                subset=subset,
                kind="s09_little_bad",
                labeled=labeled,
                withheld=intended,
                twin=subset == plan.diagnostic_subset,
                topic="little_text",
                body="",
            )

    def _s01_sources_raw(self, split: str, count: int) -> list[tuple[dict, tuple[str, str]]]:
        assigned: list[tuple[dict, tuple[str, str]] | None] = [None] * count
        for pair_index, pair in enumerate(LOOKALIKE_PAIRS):
            indexes = list(range(pair_index, count, len(LOOKALIKE_PAIRS)))
            if not indexes:
                continue
            intended, lookalike = pair
            found = self._take(
                split,
                "staffing",
                MAYA,
                len(indexes),
                lambda message, intended=intended, lookalike=lookalike: _has(message, intended)
                and not _has(message, lookalike),
            )
            for slot, source in zip(indexes, found):
                assigned[slot] = (source, pair)
        return assigned  # type: ignore[return-value]

    def _emit_pool_legitimate(self, split: str, plan: SplitPlan) -> None:
        if plan.diagnostic_subset is None:
            return
        internal_n = plan.diagnostic_legitimate.get("s05_internal", 0)
        external_n = plan.diagnostic_legitimate.get("s05_external", 0)
        for source in self._take(
            split,
            "project_update",
            MAYA,
            internal_n,
            lambda message: all(_has(message, person) for person in PROJECT_TO),
        ):
            self._draft_as_sent(
                source,
                subset=plan.diagnostic_subset,
                scenario_id="S05",
                variant="internal_project",
                topic="project_update",
                stipulation="Stipulated routine internal project mail. Every recipient was intended.",
            )
        for source in self._take(
            split,
            "purchase_scheduling",
            MAYA,
            external_n,
            lambda message: _has(message, LEE),
        ):
            self._draft_as_sent(
                source,
                subset=plan.diagnostic_subset,
                scenario_id="S05",
                variant="external_purchase",
                topic="purchase_scheduling",
                stipulation="Stipulated routine external scheduling mail. Every recipient was intended.",
            )

    def _draft_as_sent(self, source, *, subset, scenario_id, variant, topic, stipulation) -> None:
        labeled = [{**row, "intended": True, "stipulation": stipulation} for row in source["recipients"]]
        self._add_draft(
            sender=source["sender_contact_id"],
            recipients=labeled,
            when=source["sent_at"],
            subject=source["subject"],
            body=source["body"],
            subset=subset,
            scenario_id=scenario_id,
            scenario_variant=variant,
            topic=topic,
            family_id=source["family_id"],
            source_message_id=source["message_id"],
            withheld="",
            counterfactual=False,
        )

    def _emit_first_contacts(self, split, plan, kind, department, domain) -> None:
        product_n = plan.hard_negative.get(kind, 0)
        diag_n = plan.diagnostic_legitimate.get(kind, 0)
        total = product_n + diag_n
        if total == 0:
            return
        hour = 18 if kind == "s03" else 19
        times = self._special_times(split, total, hour)
        scenario_id, variant = _meta(kind)
        stipulation = (
            "Stipulated intended first direct contact."
            if kind == "s03"
            else "Stipulated intended first contact at a new external domain."
        )
        for index, moment in enumerate(times):
            if domain is None:
                address_domain = f"{PARTNER_BRANDS[self.brand_i]}.example"
                self.brand_i += 1
            else:
                address_domain = domain
            contact = self._invent(hint="new", department=department, domain=address_domain, visible=moment)
            subset = plan.product_subset if index < product_n else plan.diagnostic_subset
            message = self._emit_composed(
                sender=MAYA,
                to=(contact.contact_id,),
                when=moment,
                topic="introduction",
                selectable=False,
            )
            self._draft_as_sent(
                message,
                subset=subset,
                scenario_id=scenario_id,
                variant=variant,
                topic="introduction",
                stipulation=stipulation,
            )

    def _emit_s07(self, split, plan) -> None:
        people = self.s07_by_split[split]
        product_n = plan.hard_negative.get("s07", 0)
        if len(people) != product_n + plan.diagnostic_legitimate.get("s07", 0):
            raise RuntimeError("S07 roster does not match the quota")
        times = self._special_times(split, len(people), hour=20)
        for index, (person, moment) in enumerate(zip(people, times)):
            subset = plan.product_subset if index < product_n else plan.diagnostic_subset
            message = self._emit_composed(
                sender=MAYA,
                to=(person,),
                when=moment,
                topic="kickoff",
                selectable=False,
            )
            self._draft_as_sent(
                message,
                subset=subset,
                scenario_id="S07",
                variant="legitimate_topic_change",
                topic="kickoff",
                stipulation="Stipulated intended topic change with an established contact.",
            )

    def _emit_cold_starts(self, split, plan) -> None:
        product_n = plan.hard_negative.get("s09_cold", 0)
        diag_n = plan.diagnostic_legitimate.get("s09_cold", 0)
        total = product_n + diag_n
        if total == 0:
            return
        times = self._special_times(split, total, hour=21)
        for index, moment in enumerate(times):
            sender = self._invent(hint="cold", department="Operations", domain="demo.example", visible=moment)
            subset = plan.product_subset if index < product_n else plan.diagnostic_subset
            message = self._emit_composed(
                sender=sender.contact_id,
                to=(MAYA, NOAH),
                when=moment,
                topic="introduction",
                selectable=False,
            )
            self._draft_as_sent(
                message,
                subset=subset,
                scenario_id="S09",
                variant="cold_start_legitimate",
                topic="introduction",
                stipulation="Stipulated intended mail from a sender with no earlier messages.",
            )

    def _emit_little_ok(self, split, plan) -> None:
        product_n = plan.hard_negative.get("s09_little_ok", 0)
        diag_n = plan.diagnostic_legitimate.get("s09_little_ok", 0)
        total = product_n + diag_n
        if total == 0:
            return
        times = self._special_times(split, total, hour=21, minute_base=30)
        for index, moment in enumerate(times):
            message_id = self._next_message_id()
            if index % 2 == 0:
                subject, body = "", f"Thanks. Ref: {message_id}"
            else:
                subject, body = f"Confirming {message_id}", ""
            recipients = self._recipients((NOAH,))
            message = self._store_message(
                message_id=message_id,
                sender=MAYA,
                recipients=recipients,
                when=moment,
                topic="little_text",
                subject=subject,
                body=body,
                kind="composed",
                family_id=f"fam_{message_id}",
                thread_id=f"thr_{message_id}",
                selectable=False,
            )
            subset = plan.product_subset if index < product_n else plan.diagnostic_subset
            self._draft_as_sent(
                message,
                subset=subset,
                scenario_id="S09",
                variant="little_text_legitimate",
                topic="little_text",
                stipulation="Stipulated intended recipient. Empty or tiny text is not the label.",
            )

    def _emit_routine_drafts(self, split: str, plan: SplitPlan) -> None:
        eligible = []
        for (pool_split, _topic, sender), messages in self.pools.items():
            if pool_split != split:
                continue
            if not self.contacts[sender].is_internal:
                continue
            for message in messages:
                if message["message_id"] not in self.used:
                    eligible.append(message)
        eligible.sort(key=lambda message: (message["sent_at"], message["message_id"]))
        needed = plan.routine_count
        # Hold back a few canonical S05 messages, then fill the rest by spread.
        forced = []
        forced.extend(
            self._take_unused(
                eligible,
                5,
                lambda message: message["generator_topic"] == "project_update"
                and message["sender_contact_id"] == MAYA
                and all(_has(message, person) for person in PROJECT_TO),
            )
        )
        forced.extend(
            self._take_unused(
                eligible,
                5,
                lambda message: message["generator_topic"] == "purchase_scheduling"
                and message["sender_contact_id"] == MAYA
                and _has(message, LEE),
            )
        )
        forced.extend(
            self._take_unused(
                eligible,
                8,
                lambda message: _has_role(message, "bcc")
                and message["sender_contact_id"] == MAYA
                and all(_has(message, person) for person in PROJECT_TO),
            )
        )
        if len(forced) != 18:
            raise RuntimeError(f"{split} could not reserve routine S05 and legitimate Bcc examples")
        for message in forced:
            self.used.add(message["message_id"])
        remaining_pool = [message for message in eligible if message["message_id"] not in self.used]
        rest = spread_take(remaining_pool, needed - len(forced))
        for message in rest:
            self.used.add(message["message_id"])
        for message in [*forced, *rest]:
            scenario_id, variant = _routine_scenario(message)
            stipulation = (
                "Stipulated routine project or purchase mail. Every recipient was intended."
                if scenario_id == "S05"
                else "Routine sent mail addressed only to intended recipients."
            )
            self._draft_as_sent(
                message,
                subset=plan.product_subset,
                scenario_id=scenario_id,
                variant=variant,
                topic=message["generator_topic"],
                stipulation=stipulation,
            )

    def _take_unused(self, eligible: list[dict], count: int, predicate) -> list[dict]:
        matched = [message for message in eligible if message["message_id"] not in self.used and predicate(message)]
        return spread_take(matched, count)

    def _emit_walkthrough(self) -> None:
        week = weeks_in("test")[-1]
        plan = PLANS["test"]
        subset = plan.diagnostic_subset
        self._walk_sent(
            week + timedelta(days=0, hours=17),
            MAYA,
            PROJECT_TO,
            PROJECT_CC,
            (),
            "project_update",
            "S05",
            "internal_project",
            "Stipulated routine internal project mail. Every recipient was intended.",
        )
        self._walk_sent(
            week + timedelta(days=0, hours=17, minutes=10),
            MAYA,
            (LEE,),
            (),
            (),
            "purchase_scheduling",
            "S05",
            "external_purchase",
            "Stipulated routine external scheduling mail. Every recipient was intended.",
        )
        self._walk_counterfactual(
            when=week + timedelta(days=1, hours=17),
            sender=MAYA,
            to=("c_alex_chen",),
            cc=(),
            bcc=(),
            topic="staffing",
            scenario_id="S01",
            variant="lookalike_replacement",
            withheld="c_alex_chan",
            bad_ids={"c_alex_chen"},
            bad_text="Stipulated lookalike replacement. Name similarity is not the label.",
            good_text="Kept from the legitimate recipient list.",
        )
        self._walk_counterfactual(
            when=week + timedelta(days=1, hours=17, minutes=10),
            sender=MAYA,
            to=PROJECT_TO,
            cc=(LEE, *PROJECT_CC),
            bcc=(),
            topic="budget",
            scenario_id="S02",
            variant="added_external",
            withheld="",
            bad_ids={LEE},
            bad_text="Stipulated accidental addition. External status is not the label.",
            good_text="Kept from the legitimate recipient list.",
        )
        jordan = replace(JORDAN, directory_visible_from=week + timedelta(days=2, hours=17))
        self._add_contact(jordan)
        self._walk_sent(
            jordan.directory_visible_from,
            MAYA,
            (jordan.contact_id,),
            (),
            (),
            "introduction",
            "S03",
            "legitimate_first_contact",
            "Stipulated intended first direct contact.",
        )
        rina = replace(RINA, directory_visible_from=week + timedelta(days=2, hours=17, minutes=10))
        self._add_contact(rina)
        self._walk_sent(
            rina.directory_visible_from,
            MAYA,
            (rina.contact_id,),
            (),
            (),
            "introduction",
            "S06",
            "legitimate_new_domain",
            "Stipulated intended first contact at a new external domain.",
        )
        shared = week + timedelta(days=3, hours=17)
        self._walk_counterfactual(
            when=shared,
            sender=MAYA,
            to=(SAM,),
            cc=(),
            bcc=(),
            topic="compensation",
            scenario_id="S04",
            variant="familiar_topic_mismatch",
            withheld=PRYA,
            bad_ids={SAM},
            bad_text="Stipulated mismatch: familiar contact, compensation content intended for a people partner.",
            good_text="",
        )
        self._walk_sent(
            shared,
            MAYA,
            (SAM,),
            (),
            (),
            "kickoff",
            "S07",
            "legitimate_topic_change",
            "Stipulated intended topic change with an established contact.",
        )
        # 17:50 avoids the 17:20 reply to the kickoff sent at 17:00 the same day.
        self._walk_s08(week + timedelta(days=3, hours=17, minutes=50), subset)
        elliot_time = week + timedelta(days=4, hours=17)
        elliot = replace(ELLIOT, directory_visible_from=elliot_time)
        self._add_contact(elliot)
        self._walk_sent(
            elliot_time,
            elliot.contact_id,
            (MAYA, NOAH),
            (),
            (),
            "introduction",
            "S09",
            "cold_start_legitimate",
            "Stipulated intended mail from a sender with no earlier messages.",
        )
        little_ok_time = week + timedelta(days=4, hours=17, minutes=10)
        self._walk_little(
            little_ok_time,
            subject="",
            body_for=lambda message_id: f"Thanks. Ref: {message_id}",
            to=(NOAH,),
            scenario_id="S09",
            variant="little_text_legitimate",
            bad_ids=set(),
            bad_text="",
            good_text="Stipulated intended recipient. Empty or tiny text is not the label.",
            withheld="",
            counterfactual=False,
        )
        self._walk_little(
            week + timedelta(days=4, hours=17, minutes=20),
            subject="Headcount update",
            body_for=lambda _message_id: "",
            to=("c_alex_chen",),
            scenario_id="S09",
            variant="little_text_unintended",
            bad_ids={"c_alex_chen"},
            bad_text="Stipulated unintended recipient. Empty text is not the label.",
            good_text="",
            withheld="c_alex_chan",
            counterfactual=True,
        )

    def _walk_sent(self, when, sender, to, cc, bcc, topic, scenario_id, variant, stipulation) -> None:
        message = self._emit_composed(
            sender=sender,
            to=to,
            cc=cc,
            bcc=bcc,
            when=when,
            topic=topic,
            selectable=False,
        )
        self._draft_as_sent(
            message,
            subset="test_diagnostic",
            scenario_id=scenario_id,
            variant=variant,
            topic=topic,
            stipulation=stipulation,
        )
        self.drafts[-1]["is_walkthrough"] = True

    def _walk_counterfactual(
        self, *, when, sender, to, cc, bcc, topic, scenario_id, variant, withheld, bad_ids, bad_text, good_text
    ) -> None:
        recipients = self._recipients(to, cc, bcc)
        message_id = self._next_message_id()
        # The id is only a text token. Counterfactual walkthroughs are not sent.
        slots = self._slots(sender, recipients, when, message_id)
        subject, body = render(topic, self.rng, **slots)
        labeled = self._label_rows(
            recipients,
            {row["contact_id"] for row in recipients if row["contact_id"] not in bad_ids},
            bad_text,
            good_text,
        )
        self._add_draft(
            sender=sender,
            recipients=labeled,
            when=when,
            subject=subject,
            body=body,
            subset="test_diagnostic",
            scenario_id=scenario_id,
            scenario_variant=variant,
            topic=topic,
            family_id=f"fam_{message_id}",
            source_message_id="",
            withheld=withheld,
            counterfactual=True,
            walkthrough=True,
        )

    def _walk_s08(self, when, subset) -> None:
        recipients = self._recipients(PROJECT_TO, PROJECT_CC, PROJECT_BCC)
        anchor = self._next_message_id()
        slots = self._slots(MAYA, recipients, when, anchor)
        subject, body = render("project_update", self.rng, **slots)
        message = self._store_message(
            message_id=anchor,
            sender=MAYA,
            recipients=recipients,
            when=when,
            topic="project_update",
            subject=subject,
            body=body,
            kind="composed",
            family_id=f"fam_{anchor}",
            thread_id=f"thr_{anchor}",
            selectable=False,
        )
        self._emit_reply(message)
        family = message["family_id"]
        variants = [
            ("all_intended", recipients, set(), False),
            (
                "unintended_cc",
                recipients
                + [{"contact_id": "c_alex_chen", "role": "cc", "recipient_order": len(recipients)}],
                {"c_alex_chen"},
                True,
            ),
            (
                "unintended_bcc",
                recipients + [{"contact_id": LEE, "role": "bcc", "recipient_order": len(recipients)}],
                {LEE},
                True,
            ),
            (
                "two_unintended",
                recipients
                + [
                    {"contact_id": "c_alex_chen", "role": "cc", "recipient_order": len(recipients)},
                    {"contact_id": LEE, "role": "bcc", "recipient_order": len(recipients) + 1},
                ],
                {"c_alex_chen", LEE},
                True,
            ),
        ]
        base_ids = {row["contact_id"] for row in recipients}
        for variant, rows, bad_ids, counterfactual in variants:
            # Re-number orders in case of additions.
            ordered = []
            for index, row in enumerate(rows):
                ordered.append({**row, "recipient_order": index})
            labeled = self._label_rows(
                ordered,
                base_ids,
                "Stipulated unintended recipient in a multi-recipient draft.",
                "Stipulated all-intended group mail. Roles differ, and every recipient was intended."
                if variant == "all_intended"
                else "Kept from the legitimate recipient list.",
            )
            self._add_draft(
                sender=MAYA,
                recipients=labeled,
                when=when,
                subject=subject,
                body=body,
                subset=subset,
                scenario_id="S08",
                scenario_variant=variant,
                topic="project_update",
                family_id=family,
                source_message_id=anchor,
                withheld="",
                counterfactual=counterfactual,
                walkthrough=True,
            )

    def _walk_little(
        self, when, *, subject, body_for, to, scenario_id, variant, bad_ids, bad_text, good_text, withheld, counterfactual
    ) -> None:
        recipients = self._recipients(to)
        if counterfactual:
            token = self._next_message_id()
            body = body_for(token)
            labeled = self._label_rows(
                recipients,
                {row["contact_id"] for row in recipients if row["contact_id"] not in bad_ids},
                bad_text,
                good_text,
            )
            self._add_draft(
                sender=MAYA,
                recipients=labeled,
                when=when,
                subject=subject,
                body=body,
                subset="test_diagnostic",
                scenario_id=scenario_id,
                scenario_variant=variant,
                topic="little_text",
                family_id=f"fam_{token}",
                source_message_id="",
                withheld=withheld,
                counterfactual=True,
                walkthrough=True,
            )
            return
        message_id = self._next_message_id()
        body = body_for(message_id)
        message = self._store_message(
            message_id=message_id,
            sender=MAYA,
            recipients=recipients,
            when=when,
            topic="little_text",
            subject=subject,
            body=body,
            kind="composed",
            family_id=f"fam_{message_id}",
            thread_id=f"thr_{message_id}",
            selectable=False,
        )
        self._draft_as_sent(
            message,
            subset="test_diagnostic",
            scenario_id=scenario_id,
            variant=variant,
            topic="little_text",
            stipulation=good_text,
        )
        self.drafts[-1]["is_walkthrough"] = True

    def _emit_feedback(self) -> None:
        hosts = [
            draft
            for draft in self.drafts
            if draft["subset"] == "train" and draft["scenario_id"] in {"routine", "S05"}
        ]
        hosts.sort(key=lambda draft: (draft["sent_at"], draft["draft_id"]))
        if len(hosts) < 3:
            raise RuntimeError("Need three train drafts for illustrative feedback")
        train_end = split_bounds("train")[1]
        examples = [
            (hosts[0], "", "uncertain", "pending_review", "Reviewer could not tell whether the recipient was intended."),
            (hosts[1], "false", "certain", "pending_review", "Reviewer asserted a mistake, and the assertion is still pending."),
            (hosts[2], "true", "certain", "rejected", "Reviewer assertion was rejected and does not change the label."),
        ]
        for draft, asserted, confidence, status, notes in examples:
            submitted = draft["sent_at"] + timedelta(days=1)
            if submitted >= train_end:
                submitted = draft["sent_at"] + timedelta(hours=1)
            self.feedback_i += 1
            self.feedback.append(
                {
                    "feedback_id": f"fb_{self.feedback_i:04d}",
                    "draft_id": draft["draft_id"],
                    "contact_id": draft["recipients"][0]["contact_id"],
                    "reviewer_id": QUINN,
                    "submitted_at": submitted,
                    "asserted_intended": asserted,
                    "confidence": confidence,
                    "review_status": status,
                    "notes": notes,
                }
            )

    def _assemble(self) -> Dataset:
        contact_rows = [
            {
                "contact_id": contact.contact_id,
                "display_name": contact.display_name,
                "email_address": contact.email_address,
                "domain": contact.domain,
                "is_internal": contact.is_internal,
                "department": contact.department,
                "directory_visible_from": contact.directory_visible_from,
                "dataset_version": DATASET_VERSION,
            }
            for contact in self.contacts.values()
        ]
        message_rows = []
        message_recipient_rows = []
        for message in self.messages:
            message_rows.append(
                {
                    "message_id": message["message_id"],
                    "thread_id": message["thread_id"],
                    "family_id": message["family_id"],
                    "sender_contact_id": message["sender_contact_id"],
                    "sent_at": message["sent_at"],
                    "subject": message["subject"],
                    "body": message["body"],
                    "body_hash": body_hash(message["body"]),
                    "message_kind": message["message_kind"],
                    "generator_topic": message["generator_topic"],
                    "split": message["split"],
                    "dataset_version": DATASET_VERSION,
                }
            )
            for row in message["recipients"]:
                message_recipient_rows.append({"message_id": message["message_id"], **row})

        draft_rows = []
        draft_recipient_rows = []
        label_rows = []
        manifest_rows = []
        misdirected_ids = set()
        for draft in self.drafts:
            draft_rows.append(
                {
                    "draft_id": draft["draft_id"],
                    "family_id": draft["family_id"],
                    "source_message_id": draft["source_message_id"],
                    "sender_contact_id": draft["sender_contact_id"],
                    "sent_at": draft["sent_at"],
                    "subject": draft["subject"],
                    "body": draft["body"],
                    "body_hash": body_hash(draft["body"]),
                    "split": draft["split"],
                    "subset": draft["subset"],
                    "scenario_id": draft["scenario_id"],
                    "scenario_variant": draft["scenario_variant"],
                    "generator_topic": draft["generator_topic"],
                    "withheld_contact_id": draft["withheld_contact_id"],
                    "is_counterfactual": draft["is_counterfactual"],
                    "is_walkthrough": draft["is_walkthrough"],
                    "label_source": LABEL_SOURCE,
                    "dataset_version": DATASET_VERSION,
                }
            )
            unintended = False
            for row in draft["recipients"]:
                draft_recipient_rows.append(
                    {
                        "draft_id": draft["draft_id"],
                        "contact_id": row["contact_id"],
                        "role": row["role"],
                        "recipient_order": row["recipient_order"],
                    }
                )
                label_rows.append(
                    {
                        "draft_id": draft["draft_id"],
                        "contact_id": row["contact_id"],
                        "intended": row["intended"],
                        "label_source": LABEL_SOURCE,
                        "label_confidence": "certain",
                        "scenario_id": draft["scenario_id"],
                        "stipulation": row["stipulation"],
                        "dataset_version": DATASET_VERSION,
                    }
                )
                unintended = unintended or not row["intended"]
            if unintended:
                misdirected_ids.add(draft["draft_id"])
            manifest_rows.append(
                {
                    "dataset_version": DATASET_VERSION,
                    "draft_id": draft["draft_id"],
                    "family_id": draft["family_id"],
                    "split": draft["split"],
                    "subset": draft["subset"],
                    "sent_at": draft["sent_at"],
                    "scenario_id": draft["scenario_id"],
                    "scenario_variant": draft["scenario_variant"],
                    "is_misdirected_email": unintended,
                    "is_walkthrough": draft["is_walkthrough"],
                    "frozen": draft["subset"] in FROZEN_SUBSETS,
                }
            )

        contacts = _frame(contact_rows, CONTACTS_COLUMNS, ["contact_id"])
        messages = _frame(message_rows, MESSAGES_COLUMNS, ["sent_at", "message_id"])
        message_recipients = _frame(
            message_recipient_rows, MESSAGE_RECIPIENT_COLUMNS, ["message_id", "recipient_order"]
        )
        drafts = _frame(draft_rows, DRAFTS_COLUMNS, ["sent_at", "draft_id"])
        draft_recipients = _frame(draft_recipient_rows, DRAFT_RECIPIENT_COLUMNS, ["draft_id", "recipient_order"])
        labels = _frame(label_rows, LABEL_COLUMNS, ["draft_id", "contact_id"])
        feedback = _frame(
            [
                {**row, "dataset_version": DATASET_VERSION}
                for row in self.feedback
            ],
            FEEDBACK_COLUMNS,
            ["feedback_id"],
        )
        manifest = _frame(manifest_rows, MANIFEST_COLUMNS, ["sent_at", "draft_id"])
        invalid = _frame(_invalid_rows(), INVALID_FIXTURE_COLUMNS, ["fixture_id"])
        summary = _summary(manifest, messages)
        summary["seed"] = self.seed
        summary["generator_version"] = GENERATOR_VERSION
        summary["dataset_version"] = DATASET_VERSION
        return Dataset(
            contacts=contacts,
            messages=messages,
            message_recipients=message_recipients,
            drafts=drafts,
            draft_recipients=draft_recipients,
            labels=labels,
            reviewer_feedback=feedback,
            split_manifest=manifest,
            invalid_fixtures=invalid,
            seed=self.seed,
            summary=summary,
        )


def _meta(kind: str) -> tuple[str, str]:
    from med_data.roster import KIND_META

    return KIND_META[kind]


def _routine_scenario(message: dict) -> tuple[str, str]:
    if (
        message["sender_contact_id"] == MAYA
        and message["generator_topic"] == "project_update"
        and all(_has(message, person) for person in PROJECT_TO)
    ):
        return "S05", "internal_project"
    if (
        message["sender_contact_id"] == MAYA
        and message["generator_topic"] == "purchase_scheduling"
        and any(_has(message, vendor) for vendor in VENDORS)
    ):
        return "S05", "external_purchase"
    return "routine", "established_contact"


def _frame(rows: list[dict], columns: list[str], sort_by: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=columns)
    if frame.empty:
        return frame
    return frame.sort_values(sort_by, kind="mergesort").reset_index(drop=True)


def _summary(manifest: pd.DataFrame, messages: pd.DataFrame) -> dict:
    subsets = {}
    for subset, group in manifest.groupby("subset", sort=True):
        subsets[str(subset)] = {
            "drafts": int(len(group)),
            "misdirected": int(group["is_misdirected_email"].sum()),
            "legitimate": int((~group["is_misdirected_email"]).sum()),
        }
    return {
        "messages": int(len(messages)),
        "drafts": int(len(manifest)),
        "subsets": subsets,
    }


def _invalid_rows() -> list[dict]:
    rows = [
        (
            "inv_no_recipients",
            "invalid_input",
            "no_recipients",
            "To, Cc, and Bcc are all empty.",
        ),
        (
            "inv_malformed_address",
            "invalid_input",
            "malformed_address",
            "Recipient value 'alex.chen.demo.example' has no @ sign.",
        ),
        (
            "inv_unknown_snapshot",
            "unavailable",
            "unknown_snapshot",
            "Historical context reference 'snap-does-not-exist' cannot be resolved.",
        ),
        (
            "inv_too_many_recipients",
            "invalid_input",
            "too_many_recipients",
            "21 unique recipients exceed the supported maximum of 20.",
        ),
    ]
    return [
        {
            "fixture_id": fixture_id,
            "category": category,
            "reason": reason,
            "detail": detail,
            "expected_status": "unable_to_assess",
            "dataset_version": DATASET_VERSION,
        }
        for fixture_id, category, reason, detail in rows
    ]


