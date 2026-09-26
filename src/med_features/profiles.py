"""Point-in-time directory and sent-mail index.

The index can be rebuilt when new sent mail arrives. Rebuilding does not refit
the text transformer. A draft sees only messages strictly earlier than its
cutoff, minus the family and copied-body exclusions supplied on the query.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from med_features.preprocess import document_text
from med_features.schema import NEAR_NAME_THRESHOLD, FeatureError
from med_features.similarity import local_part, normalize_name, normalized_similarity

UTC = timezone.utc


def as_utc(value) -> datetime:
    if isinstance(value, str):
        from med_data.calendar import parse_ts

        return parse_ts(value)
    if isinstance(value, datetime):
        current = value
    else:
        current = value.to_pydatetime()
    if current.tzinfo is None:
        raise FeatureError("Timestamp lacks a timezone")
    return current.astimezone(UTC)


@dataclass(frozen=True)
class DirectoryEntry:
    contact_id: str
    display_name: str
    email_address: str
    domain: str
    is_internal: bool
    visible_from: datetime
    name_key: str
    local_part: str


class Directory:
    """Contacts a scorer may compare, filtered by directory_visible_from."""

    def __init__(self, entries: list[DirectoryEntry]):
        ordered = sorted(entries, key=lambda entry: entry.contact_id)
        self.entries = ordered
        self.by_id = {entry.contact_id: index for index, entry in enumerate(ordered)}
        size = len(ordered)
        self.name_similarity = np.zeros((size, size), dtype=np.float64)
        self.address_similarity = np.zeros((size, size), dtype=np.float64)
        for left in range(size):
            for right in range(left + 1, size):
                name_score = normalized_similarity(ordered[left].name_key, ordered[right].name_key)
                address_score = normalized_similarity(ordered[left].local_part, ordered[right].local_part)
                self.name_similarity[left, right] = self.name_similarity[right, left] = name_score
                self.address_similarity[left, right] = self.address_similarity[right, left] = address_score

    def require(self, contact_id: str) -> DirectoryEntry:
        index = self.by_id.get(contact_id)
        if index is None:
            raise FeatureError(f"Contact {contact_id} is not in the directory profile")
        return self.entries[index]

    def candidate_ids(self, contact_id: str, cutoff: datetime) -> list[str]:
        """Other contacts already listed in the directory at the cutoff."""
        entry = self.require(contact_id)
        moment = as_utc(cutoff)
        chosen = []
        for candidate in self.entries:
            if candidate.visible_from > moment:
                continue
            if candidate.contact_id == entry.contact_id:
                continue
            if candidate.email_address == entry.email_address:
                continue
            chosen.append(candidate.contact_id)
        return chosen

    def similarity(self, contact_id: str, cutoff: datetime) -> dict:
        entry = self.require(contact_id)
        ids = self.candidate_ids(contact_id, cutoff)
        if not ids:
            return {
                "name_similarity_max": 0.0,
                "address_similarity_max": 0.0,
                "contact_similarity_observed": 0,
                "near_name_count": 0,
            }
        own = self.by_id[entry.contact_id]
        name_scores = []
        address_scores = []
        near = 0
        for candidate_id in ids:
            other = self.by_id[candidate_id]
            name_score = float(self.name_similarity[own, other])
            address_score = float(self.address_similarity[own, other])
            name_scores.append(name_score)
            address_scores.append(address_score)
            if name_score >= NEAR_NAME_THRESHOLD:
                near += 1
        return {
            "name_similarity_max": max(name_scores),
            "address_similarity_max": max(address_scores),
            "contact_similarity_observed": 1,
            "near_name_count": near,
        }


def directory_from_dataset(dataset) -> Directory:
    entries = []
    for row in dataset.contacts.itertuples(index=False):
        email = str(row.email_address)
        entries.append(
            DirectoryEntry(
                contact_id=str(row.contact_id),
                display_name=str(row.display_name),
                email_address=email,
                domain=str(row.domain),
                is_internal=bool(row.is_internal),
                visible_from=as_utc(row.directory_visible_from),
                name_key=normalize_name(str(row.display_name)),
                local_part=local_part(email),
            )
        )
    return Directory(entries)


class HistoryIndex:
    """Sent mail ordered by time, with pair and domain postings."""

    def __init__(self, frames: dict):
        self.message_ids = frames["message_ids"]
        self.sent_at = frames["sent_at"]
        self.sender_ids = frames["sender_ids"]
        self.sender_domains = frames["sender_domains"]
        self.family_ids = frames["family_ids"]
        self.body_hashes = frames["body_hashes"]
        self.recipient_ids = frames["recipient_ids"]
        self.recipient_domains = frames["recipient_domains"]
        self.texts = frames["texts"]
        self.by_sender = frames["by_sender"]
        self.pairs = frames["pairs"]
        self.domain_touch = frames["domain_touch"]
        self.vectors = None

    def bind(self, transformer) -> None:
        """Transform stored texts with an already fitted vectorizer."""
        matrix = transformer.vectorizer.transform(self.texts)
        if matrix.shape[0] != len(self.message_ids):
            raise FeatureError("Vector row count does not match the history index")
        self.vectors = matrix

    def outbound_positions(self, sender: str, start, cutoff, family: str | None, hashes: frozenset[str]) -> list[int]:
        return self._window(self.by_sender.get(sender, []), start, cutoff, family, hashes)

    def pair_positions(
        self,
        sender: str,
        recipient: str,
        start,
        cutoff,
        family: str | None,
        hashes: frozenset[str],
    ) -> list[int]:
        return self._window(self.pairs.get((sender, recipient), []), start, cutoff, family, hashes)

    def domain_seen(self, domain: str, cutoff, family: str | None, hashes: frozenset[str]) -> bool:
        positions = self.domain_touch.get(domain, [])
        hi = bisect_left(positions, cutoff, key=lambda pos: self.sent_at[pos])
        for pos in positions[:hi]:
            if family is not None and self.family_ids[pos] == family:
                continue
            hashed = self.body_hashes[pos]
            if hashed and hashed in hashes:
                continue
            return True
        return False

    def sent_at_at(self, pos: int) -> datetime:
        return self.sent_at[pos]

    def recipients_at(self, pos: int) -> tuple[str, ...]:
        return self.recipient_ids[pos]

    def domains_at(self, pos: int) -> tuple[str, ...]:
        return self.recipient_domains[pos]

    def vector_at(self, pos: int):
        if self.vectors is None:
            raise FeatureError("History index has no text vectors")
        return self.vectors.getrow(pos)

    def visible_message_ids(self, cutoff, family: str | None, hashes: frozenset[str]) -> list[str]:
        hi = bisect_left(self.sent_at, cutoff)
        chosen = []
        for pos in range(hi):
            if family is not None and self.family_ids[pos] == family:
                continue
            hashed = self.body_hashes[pos]
            if hashed and hashed in hashes:
                continue
            chosen.append(self.message_ids[pos])
        return chosen

    def _window(self, positions: list[int], start, cutoff, family: str | None, hashes: frozenset[str]) -> list[int]:
        if not positions:
            return []
        lo = 0 if start is None else bisect_left(positions, start, key=lambda pos: self.sent_at[pos])
        hi = bisect_left(positions, cutoff, key=lambda pos: self.sent_at[pos])
        if family is None and not hashes:
            return positions[lo:hi]
        chosen = []
        for pos in positions[lo:hi]:
            if family is not None and self.family_ids[pos] == family:
                continue
            hashed = self.body_hashes[pos]
            if hashed and hashed in hashes:
                continue
            chosen.append(pos)
        return chosen


def history_index_from_dataset(dataset) -> HistoryIndex:
    directory = {str(row.contact_id): str(row.domain) for row in dataset.contacts.itertuples(index=False)}
    recipients: dict[str, list[tuple[int, str]]] = {}
    for row in dataset.message_recipients.itertuples(index=False):
        recipients.setdefault(str(row.message_id), []).append((int(row.recipient_order), str(row.contact_id)))
    messages = dataset.messages.sort_values(["sent_at", "message_id"], kind="mergesort")
    message_ids = []
    sent_at = []
    sender_ids = []
    sender_domains = []
    family_ids = []
    body_hashes = []
    recipient_ids = []
    recipient_domains = []
    texts = []
    by_sender: dict[str, list[int]] = {}
    pairs: dict[tuple[str, str], list[int]] = {}
    domain_touch: dict[str, list[int]] = {}
    for row in messages.itertuples(index=False):
        pos = len(message_ids)
        message_id = str(row.message_id)
        sender = str(row.sender_contact_id)
        sender_domain = directory.get(sender, "")
        people = tuple(contact_id for _, contact_id in sorted(recipients.get(message_id, [])))
        domains = tuple(dict.fromkeys(directory.get(contact_id, "") for contact_id in people if directory.get(contact_id, "")))
        message_ids.append(message_id)
        sent_at.append(as_utc(row.sent_at))
        sender_ids.append(sender)
        sender_domains.append(sender_domain)
        family_ids.append(str(row.family_id))
        body_hashes.append(str(row.body_hash or ""))
        recipient_ids.append(people)
        recipient_domains.append(domains)
        texts.append(document_text(str(row.subject), str(row.body)))
        by_sender.setdefault(sender, []).append(pos)
        for contact_id in people:
            pairs.setdefault((sender, contact_id), []).append(pos)
        touched = list(domains)
        if sender_domain and sender_domain not in touched:
            touched.append(sender_domain)
        for domain in touched:
            domain_touch.setdefault(domain, []).append(pos)
    return HistoryIndex(
        {
            "message_ids": message_ids,
            "sent_at": sent_at,
            "sender_ids": sender_ids,
            "sender_domains": sender_domains,
            "family_ids": family_ids,
            "body_hashes": body_hashes,
            "recipient_ids": recipient_ids,
            "recipient_domains": recipient_domains,
            "texts": texts,
            "by_sender": by_sender,
            "pairs": pairs,
            "domain_touch": domain_touch,
        }
    )


@dataclass(frozen=True)
class HistoryEvent:
    message_id: str
    sent_at: datetime
    sender_contact_id: str
    sender_domain: str
    subject: str
    body: str
    recipient_ids: tuple[str, ...]
    recipient_domains: tuple[str, ...]
    family_id: str = ""
    body_hash: str = ""


class EventHistory:
    """History already filtered to what one draft is allowed to see.

    Scoring views arrive this way. The index path filters first and can also
    be read through the same row builder by adapting positions, but this
    object is the allow-list boundary: it has no family table of its own.
    """

    def __init__(self, events: list[HistoryEvent], transformer):
        self.events = sorted(events, key=lambda event: (event.sent_at, event.message_id))
        self.sent_at = [event.sent_at for event in self.events]
        self.texts = [document_text(event.subject, event.body) for event in self.events]
        self.vectors = transformer.vectorizer.transform(self.texts) if self.events else None
        self.by_sender: dict[str, list[int]] = {}
        self.pairs: dict[tuple[str, str], list[int]] = {}
        self.domain_touch: dict[str, list[int]] = {}
        for pos, event in enumerate(self.events):
            self.by_sender.setdefault(event.sender_contact_id, []).append(pos)
            for contact_id in event.recipient_ids:
                self.pairs.setdefault((event.sender_contact_id, contact_id), []).append(pos)
            touched = list(event.recipient_domains)
            if event.sender_domain and event.sender_domain not in touched:
                touched.append(event.sender_domain)
            for domain in touched:
                self.domain_touch.setdefault(domain, []).append(pos)

    def outbound_positions(self, sender: str, start, cutoff, family: str | None, hashes: frozenset[str]) -> list[int]:
        return self._window(self.by_sender.get(sender, []), start, cutoff, family, hashes)

    def pair_positions(self, sender, recipient, start, cutoff, family, hashes) -> list[int]:
        return self._window(self.pairs.get((sender, recipient), []), start, cutoff, family, hashes)

    def domain_seen(self, domain: str, cutoff, family: str | None, hashes: frozenset[str]) -> bool:
        for pos in self.domain_touch.get(domain, []):
            if self.sent_at[pos] >= cutoff:
                break
            if family is not None and self.events[pos].family_id == family:
                continue
            hashed = self.events[pos].body_hash
            if hashed and hashed in hashes:
                continue
            return True
        return False

    def sent_at_at(self, pos: int) -> datetime:
        return self.sent_at[pos]

    def recipients_at(self, pos: int) -> tuple[str, ...]:
        return self.events[pos].recipient_ids

    def domains_at(self, pos: int) -> tuple[str, ...]:
        return self.events[pos].recipient_domains

    def vector_at(self, pos: int):
        return self.vectors.getrow(pos)

    def _window(self, positions, start, cutoff, family, hashes) -> list[int]:
        if not positions:
            return []
        lo = 0 if start is None else bisect_left(positions, start, key=lambda pos: self.sent_at[pos])
        hi = bisect_left(positions, cutoff, key=lambda pos: self.sent_at[pos])
        chosen = []
        for pos in positions[lo:hi]:
            event = self.events[pos]
            if family is not None and event.family_id == family:
                continue
            if event.body_hash and event.body_hash in hashes:
                continue
            chosen.append(pos)
        return chosen
