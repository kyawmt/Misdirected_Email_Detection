"""Pure presentation logic: form to request, response to display, stale results.

The Streamlit script renders what these functions return and nothing else,
so everything a user can read is testable without a browser. The functions
never score, never compare a score with a cutoff, and never add a reason code:
the decision, the flagged recipients, the codes, and the explanation sentences
are the API's.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

import pandas as pd

from med_ui.client import ApiResponse
from med_ui.config import (
    CODE_KINDS,
    EXPECTED_CONTRACT_VERSION,
    EXPECTED_SNAPSHOT_ID,
    ROLES,
)

SIMULATION_NOTE = "Simulation on fictional .example mail. Nothing is sent or stopped."
RISK_NOTE = "Every number here is a risk score from 0 to 1, not a calibrated likelihood of a mistake."
REASSESS_NOTE = "Removing a flagged recipient and reassessing is a new assessment. It may still warn."
STALE_HEADLINE = "The draft changed after the last assessment."
STALE_DETAIL = "That result no longer applies to this draft and is hidden. Assess again to get a new result."
UNABLE_HEADLINE = "Unable to assess. No decision was made."
DIRECTORY_SENTENCE = "This address is not in the directory snapshot, so the draft could not be assessed."
CATEGORY_TEXT = {
    "invalid_input": "Invalid input: the draft has a malformed or unsupported field.",
    "unavailable": "Unavailable: the service or its historical context could not assess this draft.",
    "unexpected_response": "The service sent a response this UI does not recognize, so nothing from it is shown.",
}
DIRECTORY_MESSAGES = ("not in the context snapshot directory", "not in the directory at the draft timestamp")
DECISION_LABELS = {"allow": "allow", "warn": "warn"}


# ------------------------------------------------------------------ the form


@dataclass(frozen=True)
class DraftForm:
    draft_timestamp: str
    sender: str
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()
    subject: str = ""
    body: str = ""


def split_addresses(text: str) -> tuple[str, ...]:
    """Typed addresses, separated by commas, semicolons, or new lines. The API normalizes them."""
    return tuple(part.strip() for part in re.split(r"[,;\n]", text or "") if part.strip())


def build_request(form: DraftForm, display_names: Mapping[str, str], snapshot_id: str = EXPECTED_SNAPSHOT_ID) -> dict:
    """The Phase 1 request for this form. Only request fields; no draft reference."""

    def entry(address: str) -> dict:
        name = display_names.get(address.strip().casefold())
        return {"address": address, "display_name": name} if name else {"address": address}

    request = {
        "draft_timestamp": form.draft_timestamp,
        "sender": entry(form.sender),
        "to": [entry(item) for item in form.to],
        "cc": [entry(item) for item in form.cc],
        "bcc": [entry(item) for item in form.bcc],
        "subject": form.subject,
        "body": form.body,
        "context_snapshot_id": snapshot_id,
    }
    return request


def fingerprint(request: dict) -> str:
    """Identity of a draft as sent. Any change to any field or recipient changes it."""
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()


def parse_timestamp(text: str) -> pd.Timestamp | None:
    """The draft timestamp for filtering the directory, or None if it has no timezone or does not parse."""
    try:
        moment = pd.Timestamp(str(text).strip())
    except (ValueError, TypeError):
        return None
    if moment is pd.NaT or moment.tzinfo is None:
        return None
    return moment.tz_convert("UTC")


# ------------------------------------------------------------- readiness


@dataclass(frozen=True)
class ReadinessView:
    ok: bool
    headline: str
    items: tuple[tuple[str, str], ...] = ()
    problem: str | None = None


def readiness_view(response: ApiResponse) -> ReadinessView:
    body = response.body or {}
    if not response.reached:
        return ReadinessView(False, "Scoring service unavailable. Assessment is disabled.", problem=response.error)
    if response.status_code != 200 or body.get("ready") is not True:
        return ReadinessView(
            False, "Scoring service is not ready. Assessment is disabled.", problem=str(body.get("reason") or f"HTTP {response.status_code}")
        )
    if body.get("contract_version") != EXPECTED_CONTRACT_VERSION or body.get("snapshot_id") != EXPECTED_SNAPSHOT_ID:
        return ReadinessView(
            False,
            "The service serves a different contract or snapshot than this UI expects. Assessment is disabled.",
            problem=f"contract {body.get('contract_version')}, snapshot {body.get('snapshot_id')}",
        )
    if body.get("blocking_enabled") is not False:
        return ReadinessView(False, "The service does not report blocking as disabled. Assessment is disabled.")
    items = (
        ("Contract", str(body["contract_version"])),
        ("Snapshot", str(body["snapshot_id"])),
        ("Model", str(body.get("model_version"))),
        ("Features", str(body.get("feature_spec_version"))),
        ("Policy", str(body.get("policy_version"))),
        ("T_warn (risk score cutoff)", repr(float(body["T_warn"]))),
        ("Blocking", "disabled"),
    )
    return ReadinessView(True, "Scoring service ready. Decisions are simulated.", items=items)


# ---------------------------------------------------------------- results


@dataclass(frozen=True)
class AssessmentRecord:
    """One API call and the draft it was made for."""

    fingerprint: str
    response: ApiResponse


@dataclass(frozen=True)
class CodeLine:
    kind: str
    code: str
    text: str


@dataclass(frozen=True)
class RecipientRow:
    address: str
    display_name: str
    roles: tuple[str, ...]
    risk_score: float
    risk_text: str
    flagged: bool
    codes: tuple[CodeLine, ...]
    limitations: tuple[CodeLine, ...]


@dataclass(frozen=True)
class ResultView:
    kind: str  # "empty", "stale", "assessed", or "unable"
    headline: str
    detail: tuple[str, ...] = ()
    decision: str | None = None
    email_risk_score: float | None = None
    email_risk_text: str | None = None
    t_warn: float | None = None
    margin_text: str | None = None
    recipients: tuple[RecipientRow, ...] = ()
    flagged: tuple[str, ...] = ()
    explanation: tuple[str, ...] = ()
    provenance: tuple[tuple[str, str], ...] = ()
    category: str | None = None
    message: str | None = None
    request_id: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def format_score(value: float) -> str:
    return f"{value:.7f}" if value >= 1e-3 else f"{value:.3e}"


def result_view(record: AssessmentRecord | None, current_fingerprint: str | None) -> ResultView:
    """What the result section shows for this record and the draft now in the form."""
    if record is None:
        return ResultView(kind="empty", headline="No assessment yet.")
    if current_fingerprint != record.fingerprint:
        return ResultView(kind="stale", headline=STALE_HEADLINE, detail=(STALE_DETAIL,))
    return response_view(record.response)


def response_view(response: ApiResponse) -> ResultView:
    body = response.body
    if not response.reached:
        return _unable("unavailable", f"The scoring service could not be reached ({response.error}).", None)
    if body is None:
        return _unable("unexpected_response", f"HTTP {response.status_code} with no JSON body.", None)
    if body.get("status") == "unable_to_assess":
        return _unable(str(body.get("category")), str(body.get("message") or ""), body.get("request_id"))
    if not _valid_assessed(response):
        return _unable("unexpected_response", f"HTTP {response.status_code}.", body.get("request_id"))
    recipients = tuple(_recipient_row(item) for item in body["recipients"])
    email_risk = float(body["email_risk_score"])
    provenance = body["provenance"]
    t_warn = float(provenance["T_warn"])
    decision = body["decision"]
    headline = f"Simulated decision: {DECISION_LABELS[decision]}"
    notes = [SIMULATION_NOTE, RISK_NOTE]
    if decision == "warn":
        notes.append(REASSESS_NOTE)
    return ResultView(
        kind="assessed",
        headline=headline,
        decision=decision,
        email_risk_score=email_risk,
        email_risk_text=format_score(email_risk),
        t_warn=t_warn,
        margin_text=f"{email_risk - t_warn:+.2e}",
        recipients=recipients,
        flagged=tuple(str(item) for item in body["flagged_recipients"]),
        explanation=tuple(str(item) for item in body.get("explanation") or ()),
        provenance=_provenance(provenance),
        request_id=body.get("request_id"),
        notes=tuple(notes),
    )


def _valid_assessed(response: ApiResponse) -> bool:
    body = response.body or {}
    if response.status_code != 200 or body.get("status") != "assessed":
        return False
    if body.get("decision") not in DECISION_LABELS:
        return False
    score = body.get("email_risk_score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        return False
    provenance = body.get("provenance")
    if not isinstance(provenance, dict) or not isinstance(provenance.get("T_warn"), (int, float)):
        return False
    return isinstance(body.get("recipients"), list) and isinstance(body.get("flagged_recipients"), list)


def _unable(category: str, message: str, request_id) -> ResultView:
    detail = [CATEGORY_TEXT.get(category, f"Category: {category}.")]
    if category == "unavailable" and any(part in message for part in DIRECTORY_MESSAGES):
        detail.append(DIRECTORY_SENTENCE)
    detail.append(f"Service message: {message}")
    return ResultView(
        kind="unable",
        headline=UNABLE_HEADLINE,
        detail=tuple(detail),
        category=category,
        message=message,
        request_id=request_id if isinstance(request_id, str) else None,
        notes=(SIMULATION_NOTE,),
    )


def _code_lines(items) -> tuple[CodeLine, ...]:
    lines = []
    for item in items or ():
        code = str(item.get("code"))
        lines.append(CodeLine(kind=CODE_KINDS.get(code, "code"), code=code, text=str(item.get("text", ""))))
    return tuple(lines)


def _recipient_row(item: dict) -> RecipientRow:
    score = float(item["risk_score"])
    return RecipientRow(
        address=str(item["address"]),
        display_name=str(item.get("display_name") or ""),
        roles=tuple(str(role) for role in item.get("roles", ())),
        risk_score=score,
        risk_text=format_score(score),
        flagged=bool(item["flagged"]),
        codes=_code_lines(item.get("reason_codes")),
        limitations=_code_lines(item.get("evidence_limitations")),
    )


def _provenance(provenance: dict) -> tuple[tuple[str, str], ...]:
    labels = (
        ("model_version", "Model"),
        ("feature_spec_version", "Features"),
        ("policy_version", "Policy"),
        ("T_warn", "T_warn (risk score cutoff)"),
        ("snapshot_id", "Snapshot"),
        ("effective_cutoff", "History cutoff"),
        ("history_rule", "History rule"),
    )
    rows = [(label, repr(provenance[key]) if key == "T_warn" else str(provenance[key])) for key, label in labels if key in provenance]
    if provenance.get("blocking_enabled") is False:
        rows.append(("Blocking", "disabled"))
    return tuple(rows)


def recipient_table(view: ResultView) -> list[dict]:
    """One display row per unique recipient, in the API's order."""
    return [
        {
            "Address": row.address,
            "Name": row.display_name,
            "Roles": ", ".join(row.roles),
            "Risk score": row.risk_text,
            "Flagged": "yes" if row.flagged else "no",
            "Codes": ", ".join(line.code for line in row.codes),
            "Evidence limitations": ", ".join(line.code for line in row.limitations),
        }
        for row in view.recipients
    ]


def view_lines(view: ResultView) -> list[str]:
    """Every string the result section can show for this view."""
    lines = [view.headline, *view.detail]
    if view.kind == "assessed":
        lines.append(f"Email risk score: {view.email_risk_text}")
        lines.append(f"Email risk score minus T_warn: {view.margin_text}")
        if view.flagged:
            lines.append("Flagged recipients: " + ", ".join(view.flagged))
        for row in recipient_table(view):
            lines.extend(f"{key}: {value}" for key, value in row.items())
        for row in view.recipients:
            for line in row.codes + row.limitations:
                lines.append(f"{line.kind} {line.code}: {line.text}")
        lines.extend(view.explanation)
        lines.extend(f"{label}: {value}" for label, value in view.provenance)
    lines.extend(view.notes)
    return lines


def feedback_note(response: ApiResponse) -> str:
    if response.reached and response.status_code == 200 and (response.body or {}).get("status") == "recorded":
        return (
            "Feedback recorded for later review. It is not a label until reviewed, and it does not change "
            "the model, the policy, or this decision."
        )
    message = (response.body or {}).get("message") or response.error or f"HTTP {response.status_code}"
    return f"Feedback was not recorded: {message}"
