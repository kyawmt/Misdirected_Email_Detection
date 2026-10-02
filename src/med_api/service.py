"""Assessment service: normalize, call assess_draft, map the result.

The cutoff, the maximum aggregation, and the model live in
`med_policy.decision`. This module only validates input, builds the
`DraftQuery`, applies a timeout, and shapes the response. Reason codes are
descriptive context from the feature row. They never change the decision.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from med_data.text import body_hash
from med_features.transform import DraftQuery
from med_policy.decision import assess_draft
from med_api.context import ApiPaths, ScoringContext, load_context
from med_api.normalize import InvalidInput, NormalizedRequest, Unavailable, normalize_request
from med_api.version import API_CONTRACT_VERSION, MODE, SNAPSHOT_ID, scoring_timeout_seconds

LOGGER = logging.getLogger("med_api")

# Plain-language text, kept to the sentences in the input/output specification.
CODE_TEXT = {
    "UNUSUAL_RECIPIENT_COMBINATION": "These addressees have little support as a group in the available prior communication.",
    "LOOKALIKE_CONTACT_CONTEXT": "A similar contact identity and other context warrant review; similarity alone is not a mistake finding.",
    "LIMITED_RELATIONSHIP_HISTORY": "Little or no prior communication is available; an evidence limitation, not a verdict.",
    "EXTERNAL_RECIPIENT": "The address is outside the fictional organization; context, not proof of a mistake.",
    "LIMITED_TEXT": "Little text is available for content assessment; an evidence limitation.",
    "CONTENT_RELATIONSHIP_MISMATCH": "This draft differs from prior topics exchanged with this recipient.",
}
BEHAVIOR_NOTE = "Risk scores come from sender-recipient history, recency, co-recipient support, and contact similarity."
NO_CONTENT_NOTE = "Draft-text similarity was not used by this model."
CONTENT_NOTE = "Draft-text similarity to earlier mail with each recipient was also an input to this model."
CONTENT_FEATURES = ("content_cosine", "content_similarity_observed", "pair_text_message_count")


def model_note(feature_columns) -> str:
    """Describe the inputs of the loaded model. The note never depends on the draft."""
    uses_content = any(name in feature_columns for name in CONTENT_FEATURES)
    return f"{BEHAVIOR_NOTE} {CONTENT_NOTE if uses_content else NO_CONTENT_NOTE}"
SCORE_NOTE = "Scores are risk scores, not probabilities."
ALLOW_NOTE = "Allow means no intervention under this policy. It does not guarantee that every recipient is correct."
WARN_NOTE = "Warn asks the sender to review the flagged recipients. It is not a finding about the sender's intent."
LOG_FIELDS = (
    "event",
    "request_id",
    "status",
    "category",
    "decision",
    "duration_ms",
    "contract_version",
    "model_version",
    "feature_spec_version",
    "policy_version",
    "recipient_count",
    "flagged_count",
)
REGISTRY_LIMIT = 10_000
# One fixed sentence for an unexpected failure. It never repeats the error, which could quote the draft.
UNEXPECTED_MESSAGE = "Scoring could not complete"
FEEDBACK_LABELS = ("intended", "unintended")


def format_log_record(record: dict) -> str:
    """One JSON line with allow-listed fields only. Never subject, body, names, or addresses."""
    return json.dumps({key: record[key] for key in LOG_FIELDS if key in record}, sort_keys=True)


class AssessmentService:
    def __init__(self, paths: ApiPaths):
        self.paths = paths
        self.context: ScoringContext | None = None
        self.load_error: str | None = None
        self._registry: OrderedDict[str, dict[str, str]] = OrderedDict()
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="med-api-score")

    # ------------------------------------------------------------ lifecycle

    def load(self) -> None:
        try:
            self.context = load_context(self.paths)
            self.load_error = None
        except Exception as error:  # readiness reports the reason; scoring stays unavailable
            self.context = None
            self.load_error = f"{type(error).__name__}: {error}"

    def ready(self) -> tuple[bool, dict]:
        if self.context is None:
            return False, {"ready": False, "contract_version": API_CONTRACT_VERSION, "reason": self.load_error or "not loaded"}
        return True, {
            "ready": True,
            "contract_version": API_CONTRACT_VERSION,
            "snapshot_id": self.context.snapshot_id,
            **self.context.versions,
            "T_warn": self.context.bundle.t_warn,
            "blocking_enabled": False,
            "load_seconds": round(self.context.load_seconds, 3),
        }

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------ assess

    def assess(self, payload) -> tuple[int, dict]:
        started = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex}"
        reference = payload.get("draft_reference") if isinstance(payload, dict) and isinstance(payload.get("draft_reference"), str) else None
        context = self.context
        try:
            if context is None:
                # Input errors still come first; then the missing bundle, whatever the lookup says.
                try:
                    normalize_request(payload, {}, frozenset(), SNAPSHOT_ID)
                except Unavailable:
                    pass
                raise Unavailable("The scoring bundle is not loaded")
            request = normalize_request(payload, context.address_index, context.internal_ids, context.snapshot_id)
            _require_visible(context, request)
        except InvalidInput as error:
            return self._failure(request_id, reference, "invalid_input", str(error), started, context, 0)
        except Unavailable as error:
            return self._failure(request_id, reference, "unavailable", str(error), started, context, 0)
        except Exception:  # a defect while reading the request must still fail closed, with the contract body
            return self._failure(request_id, reference, "unavailable", UNEXPECTED_MESSAGE, started, context, 0)

        try:
            query = _query(request_id, request)
            future = self._pool.submit(
                assess_draft,
                context.bundle,
                context.directory,
                context.history,
                context.transformer,
                query,
                include_features=True,
            )
            try:
                result = future.result(timeout=scoring_timeout_seconds())
            except FutureTimeout:
                future.cancel()
                return self._failure(request_id, reference, "unavailable", "Scoring timed out", started, context, len(request.recipients))
            if result["status"] != "assessed":
                return self._failure(request_id, reference, "unavailable", UNEXPECTED_MESSAGE, started, context, len(request.recipients))
            body = self._assessed(request_id, request, result, context, started)
            self._remember(request_id, request)
            self._log(body, len(request.recipients), len(body["flagged_recipients"]))
            return 200, body
        except Exception:
            # Any other error in scoring or in building the response is not an allow. The body carries no
            # draft text, no error text, no stack trace, no decision, and no score; the log record keeps
            # only its allow-listed fields.
            return self._failure(request_id, reference, "unavailable", UNEXPECTED_MESSAGE, started, context, len(request.recipients))

    def _assessed(self, request_id: str, request: NormalizedRequest, result: dict, context: ScoringContext, started: float) -> dict:
        frame = result["feature_rows"]
        rows = frame.set_index("contact_id")
        scores = {item["contact_id"]: item["risk_score"] for item in result["recipient_scores"]}
        flagged_ids = set(result["flagged_recipient_ids"])
        recipients = []
        for person in request.recipients:
            row = rows.loc[person.contact_id]
            flagged = person.contact_id in flagged_ids
            recipients.append(
                {
                    "address": person.address,
                    "display_name": person.display_name,
                    "roles": list(person.roles),
                    "risk_score": float(scores[person.contact_id]),
                    "flagged": flagged,
                    "reason_codes": _codes(_context_codes(row) + _content_codes(context, frame, person.contact_id)) if flagged else [],
                    "evidence_limitations": _codes(_limitations(row)),
                }
            )
        flagged_addresses = [item["address"] for item in recipients if item["flagged"]]
        explanation = [
            model_note(context.bundle.model.feature_columns),
            SCORE_NOTE,
            WARN_NOTE if result["decision"] == "warn" else ALLOW_NOTE,
        ]
        body = {
            "request_id": request_id,
            "contract_version": API_CONTRACT_VERSION,
            "status": "assessed",
            "mode": MODE,
            "decision": result["decision"],
            "email_risk_score": float(result["email_risk"]),
            "flagged_recipients": flagged_addresses,
            "recipients": recipients,
            "explanation": explanation,
            "provenance": {
                **context.versions,
                "T_warn": context.bundle.t_warn,
                "blocking_enabled": False,
                "snapshot_id": context.snapshot_id,
                "effective_cutoff": request.draft_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "history_rule": "sent mail strictly earlier than the cutoff",
            },
        }
        if request.draft_reference is not None:
            body["draft_reference"] = request.draft_reference
        body["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return body

    def _failure(self, request_id, reference, category, message, started, context, recipient_count) -> tuple[int, dict]:
        body = {
            "request_id": request_id,
            "contract_version": API_CONTRACT_VERSION,
            "status": "unable_to_assess",
            "category": category,
            "message": message,
            "mode": MODE,
            "decision": None,
            "email_risk_score": None,
            "flagged_recipients": None,
            "recipients": None,
        }
        if reference is not None:
            body["draft_reference"] = reference
        if context is not None:
            body["provenance"] = {**context.versions, "snapshot_id": context.snapshot_id}
        body["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        self._log(body, recipient_count, 0)
        return (422 if category == "invalid_input" else 503), body

    def _log(self, body: dict, recipient_count: int, flagged_count: int) -> None:
        record = {
            "event": "assessment",
            "request_id": body["request_id"],
            "status": body["status"],
            "duration_ms": body["duration_ms"],
            "contract_version": API_CONTRACT_VERSION,
            "recipient_count": recipient_count,
            "flagged_count": flagged_count,
        }
        if body["status"] == "assessed":
            record["decision"] = body["decision"]
        else:
            record["category"] = body["category"]
        for key in ("model_version", "feature_spec_version", "policy_version"):
            value = (body.get("provenance") or {}).get(key)
            if value is not None:
                record[key] = value
        LOGGER.info(format_log_record(record))

    def _remember(self, request_id: str, request: NormalizedRequest) -> None:
        with self._lock:
            self._registry[request_id] = {person.address: person.contact_id for person in request.recipients}
            while len(self._registry) > REGISTRY_LIMIT:
                self._registry.popitem(last=False)

    # ------------------------------------------------------------ feedback

    def feedback(self, payload) -> tuple[int, dict]:
        """Append one reviewed label. Never read by /assess; never trains or moves the cutoff."""

        def invalid(message: str):
            return 422, {"contract_version": API_CONTRACT_VERSION, "status": "rejected", "category": "invalid_input", "message": message}

        if not isinstance(payload, dict) or set(payload) != {"request_id", "recipient", "label"}:
            return invalid("Feedback needs exactly request_id, recipient, and label")
        request_id, recipient, label = payload["request_id"], payload["recipient"], payload["label"]
        if label not in FEEDBACK_LABELS:
            return invalid("label must be intended or unintended")
        if not isinstance(request_id, str) or not isinstance(recipient, str):
            return invalid("request_id and recipient must be strings")
        with self._lock:
            recipients = self._registry.get(request_id)
        if recipients is None:
            return invalid("Unknown request_id")
        contact_id = recipients.get(recipient.strip().casefold())
        if contact_id is None:
            return invalid("That recipient was not on the assessment")
        versions = self.context.versions if self.context else {}
        line = {
            "received_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "request_id": request_id,
            "contact_id": contact_id,
            "label": label,
            "contract_version": API_CONTRACT_VERSION,
            **versions,
        }
        path = Path(self.paths.feedback)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, sort_keys=True) + "\n")
        return 200, {"contract_version": API_CONTRACT_VERSION, "status": "recorded", "request_id": request_id}


def _require_visible(context: ScoringContext, request: NormalizedRequest) -> None:
    """A contact listed in the directory only after the cutoff is not known at the cutoff (A8)."""
    ids = [request.sender_contact_id] + [person.contact_id for person in request.recipients]
    for contact_id in ids:
        if context.directory.require(contact_id).visible_from > request.draft_timestamp:
            raise Unavailable("A contact is not in the directory at the draft timestamp")


def _query(request_id: str, request: NormalizedRequest) -> DraftQuery:
    """No family exclusion: the client has no family. The draft's own body is excluded from history."""
    own = body_hash(request.body) if request.body else ""
    return DraftQuery(
        draft_id=request_id,
        sent_at=request.draft_timestamp,
        sender_contact_id=request.sender_contact_id,
        subject=request.subject,
        body=request.body,
        recipients=tuple((person.contact_id, person.order) for person in request.recipients),
        exclude_family_id=None,
        exclude_body_hashes=frozenset({own}) if own else frozenset(),
    )


def _limitations(row) -> list[str]:
    codes = []
    if int(row["recipient_novel_to_sender"]) == 1 or int(row["pair_recency_observed"]) == 0:
        codes.append("LIMITED_RELATIONSHIP_HISTORY")
    if int(row["draft_text_empty"]) == 1 or int(row["draft_text_short"]) == 1 or int(row["draft_text_oov"]) == 1:
        codes.append("LIMITED_TEXT")
    return codes


def _context_codes(row) -> list[str]:
    codes = []
    if int(row["recipient_is_internal"]) == 0:
        codes.append("EXTERNAL_RECIPIENT")
    if int(row["near_name_count"]) >= 1:
        codes.append("LOOKALIKE_CONTACT_CONTEXT")
    if int(row["co_support_applicable"]) == 1 and np.isclose(float(row["co_partner_fraction"]), 0.0):
        codes.append("UNUSUAL_RECIPIENT_COMBINATION")
    return codes


def content_sensitive(model, frame, contact_id: str, reference: float | None, t_warn: float) -> bool:
    """True when this recipient's warning depends on low draft-text similarity.

    The recipient must have an observed content cosine below the typical train
    value. Its row is rescored with only `content_cosine` raised to that value;
    if the rescored risk falls below `T_warn`, the low content similarity is
    part of why this recipient was flagged. This reads the frozen model, not
    its coefficients, and never changes the decision.
    """
    if reference is None or "content_cosine" not in model.feature_columns:
        return False
    row = frame.loc[frame["contact_id"] == contact_id]
    if row.empty or int(row["content_similarity_observed"].iloc[0]) != 1:
        return False
    if float(row["content_cosine"].iloc[0]) >= reference:
        return False
    typical = row.copy()
    typical["content_cosine"] = reference
    return float(model.score_frame(typical)[0]) < t_warn


def _content_codes(context: ScoringContext, frame, contact_id: str) -> list[str]:
    if content_sensitive(context.bundle.model, frame, contact_id, context.content_reference, context.bundle.t_warn):
        return ["CONTENT_RELATIONSHIP_MISMATCH"]
    return []


def _codes(codes: list[str]) -> list[dict]:
    return [{"code": code, "text": CODE_TEXT[code]} for code in codes]
