"""Request normalizer, assumption A7.

Validates the Phase 1 input fields, merges repeated addresses across To, Cc,
and Bcc, and resolves addresses to directory contacts. It runs before
`transform_draft`, which refuses a repeated contact rather than merging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from med_api.version import (
    MAX_BODY_CHARS,
    MAX_RECIPIENTS,
    MAX_SUBJECT_CHARS,
    MIN_RECIPIENTS,
    ORGANIZATION_DOMAIN,
)

ALLOWED_FIELDS = frozenset(
    {"draft_timestamp", "sender", "to", "cc", "bcc", "subject", "body", "context_snapshot_id", "draft_reference"}
)
REQUIRED_FIELDS = ("draft_timestamp", "sender", "to", "cc", "bcc", "subject", "body", "context_snapshot_id")
ROLES = ("to", "cc", "bcc")
ENTRY_FIELDS = frozenset({"address", "display_name"})
# Substrings that mark a label, scenario, or score field. The normalizer rejects
# them by name and never reads their values.
DENIED_NAME_PARTS = (
    "label",
    "intended",
    "scenario",
    "split",
    "subset",
    "family",
    "score",
    "risk",
    "stipulation",
    "withheld",
    "counterfactual",
    "variant",
)
_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
_ADDRESS = re.compile(rf"^(?P<local>{_LOCAL})@(?P<domain>{_LABEL}(?:\.{_LABEL})*)$")


class InvalidInput(ValueError):
    """The request is malformed or unsupported."""


class Unavailable(LookupError):
    """The request is well formed but its context cannot be resolved."""


@dataclass(frozen=True)
class Recipient:
    address: str
    display_name: str
    roles: tuple[str, ...]
    order: int
    contact_id: str = ""


@dataclass(frozen=True)
class NormalizedRequest:
    draft_timestamp: datetime
    sender_address: str
    sender_contact_id: str
    subject: str
    body: str
    snapshot_id: str
    draft_reference: str | None
    recipients: tuple[Recipient, ...] = field(default_factory=tuple)


def denied_fields(payload) -> list[str]:
    """Every key, at any depth, whose name looks like a label, scenario, split, or score."""
    found = []

    def walk(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                name = str(key).casefold()
                if any(part in name for part in DENIED_NAME_PARTS):
                    found.append(".".join(path + [str(key)]))
                walk(item, path + [str(key)])
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, path + [str(index)])

    walk(payload, [])
    return found


def normalize_address(raw) -> str:
    if not isinstance(raw, str):
        raise InvalidInput("An address must be a string")
    address = raw.strip()
    if not address.isascii():
        raise InvalidInput("Addresses must be ASCII")
    match = _ADDRESS.match(address)
    if not match:
        raise InvalidInput("An address is malformed")
    domain = match.group("domain").casefold()
    if domain != "example" and not domain.endswith(".example"):
        raise InvalidInput("Only fictional .example addresses are accepted")
    return address.casefold()


def _entry(raw, where: str) -> tuple[str, str]:
    if isinstance(raw, str):
        return normalize_address(raw), ""
    if not isinstance(raw, dict):
        raise InvalidInput(f"{where} entries must be an address string or an object")
    extra = set(raw) - ENTRY_FIELDS
    if extra:
        raise InvalidInput(f"{where} entry has unsupported fields")
    if "address" not in raw:
        raise InvalidInput(f"{where} entry has no address")
    name = raw.get("display_name") or ""
    if not isinstance(name, str):
        raise InvalidInput(f"{where} display name must be a string")
    return normalize_address(raw["address"]), name.strip()


def parse_timestamp(raw) -> datetime:
    if not isinstance(raw, str):
        raise InvalidInput("draft_timestamp must be an ISO 8601 string")
    try:
        moment = datetime.fromisoformat(raw.strip())
    except ValueError as error:
        raise InvalidInput("draft_timestamp is not a valid ISO 8601 timestamp") from error
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise InvalidInput("draft_timestamp must include a timezone")
    return moment.astimezone(timezone.utc)


def normalize_request(
    payload,
    directory_index: dict[str, str],
    internal_ids: frozenset[str],
    snapshot_id: str,
) -> NormalizedRequest:
    """Validate, merge, then resolve against the loaded snapshot.

    Input errors are raised before any lookup. An unknown snapshot or an
    address missing from the directory raises Unavailable.
    """
    if not isinstance(payload, dict):
        raise InvalidInput("The request body must be a JSON object")
    denied = denied_fields(payload)
    if denied:
        raise InvalidInput("Label, scenario, split, family, or score fields are not accepted")
    unknown = set(payload) - ALLOWED_FIELDS
    if unknown:
        raise InvalidInput("The request has unsupported fields")
    missing = [name for name in REQUIRED_FIELDS if name not in payload]
    if missing:
        raise InvalidInput(f"Missing required fields: {', '.join(missing)}")
    moment = parse_timestamp(payload["draft_timestamp"])
    subject, body = payload["subject"], payload["body"]
    if not isinstance(subject, str) or not isinstance(body, str):
        raise InvalidInput("subject and body must be strings")
    if len(subject) > MAX_SUBJECT_CHARS:
        raise InvalidInput(f"subject exceeds {MAX_SUBJECT_CHARS} characters")
    if len(body) > MAX_BODY_CHARS:
        raise InvalidInput(f"body exceeds {MAX_BODY_CHARS} characters")
    reference = payload.get("draft_reference")
    if reference is not None and not isinstance(reference, str):
        raise InvalidInput("draft_reference must be a string")
    snapshot = payload["context_snapshot_id"]
    if not isinstance(snapshot, str):
        raise InvalidInput("context_snapshot_id must be a string")
    sender_address, _ = _entry(payload["sender"], "sender")

    merged: dict[str, dict] = {}
    for role in ROLES:
        entries = payload[role]
        if not isinstance(entries, list):
            raise InvalidInput(f"{role} must be a list")
        for raw in entries:
            address, name = _entry(raw, role)
            item = merged.get(address)
            if item is None:
                merged[address] = {"display_name": name, "roles": [role], "order": len(merged)}
            else:
                if role not in item["roles"]:
                    item["roles"].append(role)
                if not item["display_name"] and name:
                    item["display_name"] = name
    if len(merged) < MIN_RECIPIENTS:
        raise InvalidInput("At least one recipient is required")
    if len(merged) > MAX_RECIPIENTS:
        raise InvalidInput(f"At most {MAX_RECIPIENTS} unique recipients are accepted")

    sender_domain = sender_address.rsplit("@", 1)[1]
    if sender_domain != ORGANIZATION_DOMAIN:
        raise InvalidInput(f"The sender must be an internal {ORGANIZATION_DOMAIN} address")
    if snapshot != snapshot_id:
        raise Unavailable("The context snapshot is not available")
    sender_id = directory_index.get(sender_address)
    if sender_id is None:
        raise Unavailable("The sender is not in the context snapshot directory")
    if sender_id not in internal_ids:
        raise InvalidInput(f"The sender must be an internal {ORGANIZATION_DOMAIN} contact")

    recipients = []
    for address, item in merged.items():
        contact_id = directory_index.get(address)
        if contact_id is None:
            raise Unavailable("A recipient is not in the context snapshot directory")
        recipients.append(
            Recipient(
                address=address,
                display_name=item["display_name"],
                roles=tuple(item["roles"]),
                order=item["order"],
                contact_id=contact_id,
            )
        )
    return NormalizedRequest(
        draft_timestamp=moment,
        sender_address=sender_address,
        sender_contact_id=sender_id,
        subject=subject,
        body=body,
        snapshot_id=snapshot,
        draft_reference=reference,
        recipients=tuple(recipients),
    )
