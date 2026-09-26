"""Shared draft-to-feature transform.

Batch export and single-draft scoring both call `transform_draft`. The row
builder does not read labels, scenario ids, splits, roles, or withheld contacts.
Role is intentionally absent: a Bcc address is not a feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from scipy.sparse import vstack

from med_data.history import family_body_hashes
from med_features.preprocess import document_text, is_blank, unigrams
from med_features.profiles import EventHistory, HistoryEvent, as_utc
from med_features.schema import (
    FEATURE_COLUMNS,
    FEATURE_SPEC_VERSION,
    FLOAT_FEATURES,
    MATRIX_COLUMNS,
    RECENCY_FALLBACK_DAYS,
    RECENT_WINDOW_DAYS,
    SHORT_TOKEN_MAX,
    SPAN_FLOOR_DAYS,
    FeatureError,
)


@dataclass(frozen=True)
class DraftQuery:
    """One assessment. Exclusion fields filter history; they are not features."""

    draft_id: str
    sent_at: object
    sender_contact_id: str
    subject: str
    body: str
    recipients: tuple[tuple[str, int], ...]
    exclude_family_id: str | None = None
    exclude_body_hashes: frozenset[str] = frozenset()


def query_from_dataset(dataset, draft_id: str) -> DraftQuery:
    """Build a query from model-visible draft fields plus history exclusions.

    `family_id` and body hashes are used only to drop leaked copies. They are
    not copied onto the feature row.
    """
    matched = dataset.drafts.loc[dataset.drafts["draft_id"] == draft_id]
    if matched.empty:
        raise FeatureError(f"Unknown draft {draft_id}")
    draft = matched.iloc[0]
    recipient_rows = dataset.draft_recipients.loc[dataset.draft_recipients["draft_id"] == draft_id]
    recipient_rows = recipient_rows.sort_values("recipient_order", kind="mergesort")
    recipients = tuple(
        (str(row.contact_id), int(row.recipient_order)) for row in recipient_rows.itertuples(index=False)
    )
    hashes = family_body_hashes(dataset.messages, str(draft["family_id"]), str(draft["body"]))
    hashes.discard("")
    return DraftQuery(
        draft_id=str(draft_id),
        sent_at=draft["sent_at"],
        sender_contact_id=str(draft["sender_contact_id"]),
        subject=str(draft["subject"]),
        body=str(draft["body"]),
        recipients=recipients,
        exclude_family_id=str(draft["family_id"]),
        exclude_body_hashes=frozenset(hashes),
    )


def query_from_scoring_view(view: dict) -> DraftQuery:
    """Draft fields from a scoring view. History exclusions are already applied."""
    features = view["features"]
    recipients = tuple(
        (str(person["contact_id"]), int(person["recipient_order"])) for person in features["recipients"]
    )
    sent_at = features["sent_at"]
    return DraftQuery(
        draft_id=str(view["draft_id"]),
        sent_at=sent_at,
        sender_contact_id=str(features["sender"]["contact_id"]),
        subject=str(features["subject"]),
        body=str(features["body"]),
        recipients=recipients,
    )


def events_from_scoring_view(view: dict) -> list[HistoryEvent]:
    """History events from a Phase 2 scoring view. The view is already filtered."""
    events = []
    for item in view["features"]["history"]:
        sender = item["sender"]
        recipient_ids = tuple(str(person["contact_id"]) for person in item["recipients"])
        domains = tuple(dict.fromkeys(str(person["domain"]) for person in item["recipients"]))
        events.append(
            HistoryEvent(
                message_id=str(item["message_id"]),
                sent_at=as_utc(item["sent_at"]) if not isinstance(item["sent_at"], str) else _parse(item["sent_at"]),
                sender_contact_id=str(sender["contact_id"]),
                sender_domain=str(sender["domain"]),
                subject=str(item["subject"]),
                body=str(item["body"]),
                recipient_ids=recipient_ids,
                recipient_domains=domains,
            )
        )
    return events


def transform_draft(directory, history, transformer, query: DraftQuery) -> pd.DataFrame:
    """One row per addressed recipient, in recipient_order."""
    rows = build_rows(directory, history, transformer, query)
    frame = pd.DataFrame(rows, columns=list(MATRIX_COLUMNS))
    return _typed(frame)


def transform_drafts(directory, history, transformer, queries: list[DraftQuery]) -> pd.DataFrame:
    """Same columns as `transform_draft`, stacked in query order."""
    rows = []
    for query in queries:
        rows.extend(build_rows(directory, history, transformer, query))
    if not rows:
        return _typed(pd.DataFrame(columns=list(MATRIX_COLUMNS)))
    return _typed(pd.DataFrame(rows, columns=list(MATRIX_COLUMNS)))


def build_rows(directory, history, transformer, query: DraftQuery) -> list[dict]:
    if not query.recipients:
        raise FeatureError(f"Draft {query.draft_id} has no recipients")
    contact_ids = [contact_id for contact_id, _ in query.recipients]
    if len(contact_ids) != len(set(contact_ids)):
        raise FeatureError(f"Draft {query.draft_id} repeats a recipient")
    directory.require(query.sender_contact_id)
    cutoff = as_utc(query.sent_at)
    family = query.exclude_family_id or None
    hashes = frozenset(item for item in query.exclude_body_hashes if item)
    window_start = cutoff - timedelta(days=RECENT_WINDOW_DAYS)
    sender_positions = history.outbound_positions(query.sender_contact_id, None, cutoff, family, hashes)
    sender_count = len(sender_positions)
    sender_available = int(sender_count > 0)
    if sender_available:
        earliest = history.sent_at_at(sender_positions[0])
        span = max((cutoff - earliest).total_seconds() / 86400.0, SPAN_FLOOR_DAYS)
    else:
        span = 0.0
    group = set(contact_ids)
    focus_positions = {contact_id: [] for contact_id in contact_ids}
    partners = {contact_id: set() for contact_id in contact_ids}
    joint_counts = {contact_id: 0 for contact_id in contact_ids}
    domain_outbound: dict[str, int] = {}
    for pos in sender_positions:
        recipients = history.recipients_at(pos)
        overlap = {contact_id for contact_id in recipients if contact_id in group}
        for contact_id in overlap:
            focus_positions[contact_id].append(pos)
            others = overlap - {contact_id}
            if others:
                joint_counts[contact_id] += 1
                partners[contact_id].update(others)
        for domain in history.domains_at(pos):
            domain_outbound[domain] = domain_outbound.get(domain, 0) + 1
    draft_document = document_text(query.subject, query.body)
    draft_vector = transformer.vectorizer.transform([draft_document])
    raw_tokens = unigrams(draft_document)
    subject_blank = int(is_blank(query.subject))
    body_blank = int(is_blank(query.body))
    text_empty = int(subject_blank and body_blank)
    text_oov = int(not text_empty and draft_vector.nnz == 0)
    text_short = int(len(raw_tokens) < SHORT_TOKEN_MAX)
    applicable = int(len(contact_ids) >= 2)
    others_count = len(contact_ids) - 1
    rows = []
    for contact_id, order in query.recipients:
        entry = directory.require(contact_id)
        outbound = focus_positions[contact_id]
        inbound = history.pair_positions(contact_id, query.sender_contact_id, None, cutoff, family, hashes)
        outbound_28 = _count_since(history, outbound, window_start)
        inbound_28 = _count_since(history, inbound, window_start)
        pair_times = [history.sent_at_at(pos) for pos in outbound]
        pair_times.extend(history.sent_at_at(pos) for pos in inbound)
        if pair_times:
            recency = (cutoff - max(pair_times)).total_seconds() / 86400.0
            recency_observed = 1
        else:
            recency = RECENCY_FALLBACK_DAYS
            recency_observed = 0
        outbound_count = len(outbound)
        domain_count = int(domain_outbound.get(entry.domain, 0))
        if applicable and others_count:
            partner_fraction = len(partners[contact_id]) / others_count
        else:
            partner_fraction = 0.0
        focus_available = int(outbound_count > 0)
        if applicable and focus_available:
            conditional = joint_counts[contact_id] / outbound_count
        else:
            conditional = 0.0
        text_positions = _unique_sorted(history, list(outbound) + list(inbound))
        cosine, text_count = _content_cosine(draft_vector, history, text_positions)
        content_observed = int(draft_vector.nnz > 0 and text_count > 0 and cosine >= 0.0)
        if draft_vector.nnz == 0 or text_count == 0:
            cosine = 0.0
            content_observed = 0
        similarity = directory.similarity(contact_id, cutoff)
        rate = (outbound_count / span) if sender_available else 0.0
        values = {
            "sender_outbound_count": sender_count,
            "sender_history_available": sender_available,
            "sender_history_span_days": span,
            "pair_outbound_count": outbound_count,
            "pair_inbound_count": len(inbound),
            "pair_outbound_count_28d": outbound_28,
            "pair_inbound_count_28d": inbound_28,
            "pair_outbound_rate_per_day": rate,
            "pair_recency_days": recency,
            "pair_recency_observed": recency_observed,
            "recipient_novel_to_sender": int(outbound_count == 0),
            "domain_outbound_count": domain_count,
            "domain_novel_to_sender": int(domain_count == 0),
            "domain_seen_in_history": int(history.domain_seen(entry.domain, cutoff, family, hashes)),
            "recipient_is_internal": int(entry.is_internal),
            "addressed_recipient_count": len(contact_ids),
            "co_support_applicable": applicable,
            "co_joint_message_count": joint_counts[contact_id] if applicable else 0,
            "co_partner_fraction": partner_fraction,
            "co_focus_conditional_fraction": conditional,
            "co_focus_history_available": focus_available,
            "name_similarity_max": similarity["name_similarity_max"],
            "address_similarity_max": similarity["address_similarity_max"],
            "contact_similarity_observed": similarity["contact_similarity_observed"],
            "near_name_count": similarity["near_name_count"],
            "content_cosine": cosine,
            "content_similarity_observed": content_observed,
            "pair_text_message_count": text_count,
            "draft_raw_token_count": len(raw_tokens),
            "draft_text_empty": text_empty,
            "draft_text_short": text_short,
            "draft_text_oov": text_oov,
            "draft_subject_blank": subject_blank,
            "draft_body_blank": body_blank,
        }
        row = {
            "draft_id": query.draft_id,
            "contact_id": contact_id,
            "recipient_order": int(order),
            "feature_spec_version": FEATURE_SPEC_VERSION,
        }
        row.update(values)
        rows.append(row)
    return rows


def _count_since(history, positions, window_start) -> int:
    return sum(1 for pos in positions if history.sent_at_at(pos) >= window_start)


def _unique_sorted(history, positions: list[int]) -> list[int]:
    unique = list(dict.fromkeys(positions))
    unique.sort(key=lambda pos: (history.sent_at_at(pos), pos))
    return unique


def _content_cosine(draft_vector, history, positions: list[int]) -> tuple[float, int]:
    usable = []
    for pos in positions:
        row = history.vector_at(pos)
        if row.nnz:
            usable.append(row)
    text_count = len(usable)
    if draft_vector.nnz == 0 or text_count == 0:
        return 0.0, text_count
    stacked = vstack(usable, format="csr")
    centroid = np.asarray(stacked.mean(axis=0)).ravel()
    norm = float(np.linalg.norm(centroid))
    if norm == 0.0:
        return 0.0, text_count
    draft = np.asarray(draft_vector.toarray()).ravel()
    value = float(np.dot(draft, centroid) / norm)
    if not np.isfinite(value):
        raise FeatureError("Content cosine is not finite")
    if value < 0.0:
        if value > -1e-9:
            value = 0.0
        else:
            raise FeatureError("Content cosine is negative")
    if value > 1.0:
        if value < 1.0 + 1e-9:
            value = 1.0
        else:
            raise FeatureError("Content cosine is above 1")
    return value, text_count


def _typed(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    typed = frame.copy()
    for name in FEATURE_COLUMNS:
        if name in FLOAT_FEATURES:
            typed[name] = typed[name].astype("float64")
        else:
            typed[name] = typed[name].astype("int64")
    typed["recipient_order"] = typed["recipient_order"].astype("int64")
    return typed.loc[:, list(MATRIX_COLUMNS)]


def _parse(value: str):
    from med_data.calendar import parse_ts

    return parse_ts(value)
