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
from collections.abc import Mapping
from dataclasses import dataclass, field

import pandas as pd

from med_ui.client import ApiResponse
from med_ui.config import (
    CODE_KINDS,
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
UNABLE_CATEGORIES = ("invalid_input", "unavailable")


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
class ExpectedBundle:
    """The bundle this screen was built against: the contract and snapshot it
    speaks, and the versions and cutoff in the local policy file that the
    exploration view reads. The service must report exactly these."""

    contract_version: str
    snapshot_id: str
    model_version: str
    feature_spec_version: str
    policy_version: str
    t_warn: float

    def mismatches(self, reported: dict) -> list[str]:
        expected = {
            "contract_version": self.contract_version,
            "snapshot_id": self.snapshot_id,
            "model_version": self.model_version,
            "feature_spec_version": self.feature_spec_version,
            "policy_version": self.policy_version,
            "T_warn": self.t_warn,
        }
        return [f"{key} {reported.get(key)!r}, expected {value!r}" for key, value in expected.items() if reported.get(key) != value]


@dataclass(frozen=True)
class ReadinessView:
    ok: bool
    headline: str
    items: tuple[tuple[str, str], ...] = ()
    problem: str | None = None


def readiness_view(response: ApiResponse, expected: ExpectedBundle) -> ReadinessView:
    body = response.body or {}
    if not response.reached:
        return ReadinessView(False, "Scoring service unavailable. Assessment is disabled.", problem=response.error)
    if response.status_code != 200 or body.get("ready") is not True:
        return ReadinessView(
            False, "Scoring service is not ready. Assessment is disabled.", problem=str(body.get("reason") or f"HTTP {response.status_code}")
        )
    mismatches = expected.mismatches(body)
    if mismatches:
        return ReadinessView(
            False,
            "The service serves a different contract, snapshot, or bundle than this screen was built for. Assessment is disabled.",
            problem="; ".join(mismatches),
        )
    if body.get("blocking_enabled") is not False:
        return ReadinessView(False, "The service does not report blocking as disabled. Assessment is disabled.")
    items = (
        ("Contract", str(body["contract_version"])),
        ("Snapshot", str(body["snapshot_id"])),
        ("Model", str(body["model_version"])),
        ("Features", str(body["feature_spec_version"])),
        ("Policy", str(body["policy_version"])),
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


def result_view(record: AssessmentRecord | None, current_fingerprint: str | None, expected: ExpectedBundle | None = None) -> ResultView:
    """What the result section shows for this record and the draft now in the form."""
    if record is None:
        return ResultView(kind="empty", headline="No assessment yet.")
    if current_fingerprint != record.fingerprint:
        return ResultView(kind="stale", headline=STALE_HEADLINE, detail=(STALE_DETAIL,))
    return response_view(record.response, expected)


def response_view(response: ApiResponse, expected: ExpectedBundle | None = None) -> ResultView:
    """Display a response. Anything that is not a complete, consistent assessment from the expected bundle shows no decision."""
    body = response.body
    if not response.reached:
        return _unable("unavailable", f"The scoring service could not be reached ({response.error}).", None)
    if body is None:
        return _unable("unexpected_response", f"HTTP {response.status_code} with no JSON body.", None)
    request_id = body.get("request_id")
    if body.get("status") == "unable_to_assess":
        category = body.get("category")
        if category not in UNABLE_CATEGORIES or response.status_code not in (422, 503):
            return _unable("unexpected_response", f"HTTP {response.status_code}, unrecognized failure category.", request_id)
        return _unable(str(category), str(body.get("message") or ""), request_id)
    problems = assessed_problems(response)
    if not problems and expected is not None:
        problems = [f"bundle differs from readiness: {item}" for item in expected.mismatches({**body["provenance"], "contract_version": body["contract_version"]})]
    if problems:
        return _unable("unexpected_response", f"HTTP {response.status_code}; " + "; ".join(problems[:3]), request_id)
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
        flagged=tuple(body["flagged_recipients"]),
        explanation=tuple(body["explanation"]),
        provenance=_provenance(provenance),
        request_id=request_id if isinstance(request_id, str) else None,
        notes=tuple(notes),
    )


def _score(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0.0 <= value <= 1.0


def _codes_ok(items) -> bool:
    return isinstance(items, list) and all(
        isinstance(item, dict) and isinstance(item.get("code"), str) and isinstance(item.get("text"), str) for item in items
    )


def assessed_problems(response: ApiResponse) -> list[str]:
    """Why a response is not a complete, consistent simulated assessment (empty when it is).

    Checks the shape the screen displays and the API's own consistency
    (flagged list against flagged recipients, warn against a non-empty flagged
    list). It does not compare any score with the cutoff.
    """
    body = response.body or {}
    problems = []
    if response.status_code != 200 or body.get("status") != "assessed":
        return ["not an assessed response"]
    if not isinstance(body.get("contract_version"), str):
        problems.append("no contract version")
    if body.get("mode") != "simulation":
        problems.append("mode is not simulation")
    if body.get("decision") not in DECISION_LABELS:
        problems.append("decision is not a recognized simulated decision")
    if not _score(body.get("email_risk_score")):
        problems.append("email risk score is not a number from 0 to 1")
    provenance = body.get("provenance")
    if not isinstance(provenance, dict):
        return problems + ["no provenance"]
    if provenance.get("blocking_enabled") is not False:
        problems.append("provenance does not report blocking as disabled")
    t_warn = provenance.get("T_warn")
    if not isinstance(t_warn, (int, float)) or isinstance(t_warn, bool) or not math.isfinite(t_warn):
        problems.append("T_warn is not a finite number")
    explanation = body.get("explanation")
    if not isinstance(explanation, list) or not all(isinstance(item, str) for item in explanation):
        problems.append("explanation is not a list of sentences")
    recipients = body.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        return problems + ["no recipients"]
    for index, item in enumerate(recipients):
        if not isinstance(item, dict):
            problems.append(f"recipient {index} is not an object")
            continue
        if not isinstance(item.get("address"), str) or not item["address"]:
            problems.append(f"recipient {index} has no address")
        if not isinstance(item.get("display_name", ""), (str, type(None))):
            problems.append(f"recipient {index} display name is not text")
        roles = item.get("roles")
        if not isinstance(roles, list) or not roles or not all(role in ROLES for role in roles):
            problems.append(f"recipient {index} roles are invalid")
        if not _score(item.get("risk_score")):
            problems.append(f"recipient {index} risk score is not a number from 0 to 1")
        if not isinstance(item.get("flagged"), bool):
            problems.append(f"recipient {index} flagged is not true or false")
        if not _codes_ok(item.get("reason_codes")) or not _codes_ok(item.get("evidence_limitations")):
            problems.append(f"recipient {index} codes are malformed")
    if problems:
        return problems
    flagged = body.get("flagged_recipients")
    if not isinstance(flagged, list) or flagged != [item["address"] for item in recipients if item["flagged"]]:
        problems.append("flagged list does not match the flagged recipients")
    elif (body["decision"] == "warn") != bool(flagged):
        problems.append("decision does not match the flagged recipients")
    return problems


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


# ------------------------------------------------------------ action message

WARN_ACTION = "Pause and review before sending."
ALLOW_ACTION = "No warning from this policy."
UNABLE_ACTION = "Assessment unavailable. Check recipients manually before sending."
STALE_ACTION = "The draft changed after the last assessment. Assess the edited draft again; the earlier result no longer applies."
EMPTY_ACTION = "Not assessed yet. Assess the draft to see whether the service asks you to pause."
WARN_ITEMS_HEADING = "Check these recipients and the field they are in:"
WARN_NOTE_ACTION = "A warning asks you to check these addresses. It is not proof of a mistake."
NO_CODE_TEXT = "The service returned no reason or context code for this recipient."
ALLOW_NOTE_ACTION = (
    "This is not a check that every recipient is correct, and the policy misses some kinds of mistakes. "
    "Review the recipients yourself before sending."
)
LIMITED_ITEMS_HEADING = "Less evidence for:"
LIMITED_NOTE = "Less evidence is an evidence limitation from the service, not a warning."
ROLE_LABELS = {"to": "To", "cc": "Cc", "bcc": "Bcc"}


@dataclass(frozen=True)
class ActionItem:
    address: str
    display_name: str
    fields: str
    anchor: str
    lines: tuple[CodeLine, ...]


@dataclass(frozen=True)
class ActionMessage:
    """What to do next, shown under the Assess button. Built only from the result view, which comes from the API response."""

    kind: str  # "empty", "stale", "warn", "allow", or "unable"
    headline: str
    items_heading: str | None = None
    items: tuple[ActionItem, ...] = ()
    notes: tuple[str, ...] = ()


def recipient_anchor(index: int) -> str:
    return f"recipient-{index}"


def _fields(roles: tuple[str, ...]) -> str:
    return " and ".join(ROLE_LABELS.get(role, role) for role in roles)


def action_message(view: ResultView) -> ActionMessage:
    """The plain-language next step for a result view.

    Warn lists every flagged recipient in the API's order with the field it is
    in and the API's own codes. Allow lists recipients with the API's evidence
    limitations. Nothing is ranked by score and no reason is derived.
    """
    if view.kind == "empty":
        return ActionMessage(kind="empty", headline=EMPTY_ACTION)
    if view.kind == "stale":
        return ActionMessage(kind="stale", headline=STALE_ACTION)
    if view.kind == "unable":
        return ActionMessage(kind="unable", headline=UNABLE_ACTION, notes=(f"Category: {view.category}.", *view.detail))
    if view.decision == "warn":
        items = tuple(
            ActionItem(
                address=row.address,
                display_name=row.display_name,
                fields=_fields(row.roles),
                anchor=recipient_anchor(index),
                lines=row.codes,
            )
            for index, row in enumerate(view.recipients)
            if row.flagged
        )
        return ActionMessage(kind="warn", headline=WARN_ACTION, items_heading=WARN_ITEMS_HEADING, items=items, notes=(WARN_NOTE_ACTION,))
    items = tuple(
        ActionItem(
            address=row.address,
            display_name=row.display_name,
            fields=_fields(row.roles),
            anchor=recipient_anchor(index),
            lines=row.limitations,
        )
        for index, row in enumerate(view.recipients)
        if row.limitations
    )
    notes = (ALLOW_NOTE_ACTION, LIMITED_NOTE) if items else (ALLOW_NOTE_ACTION,)
    return ActionMessage(kind="allow", headline=ALLOW_ACTION, items_heading=LIMITED_ITEMS_HEADING if items else None, items=items, notes=notes)


def action_lines(message: ActionMessage) -> list[str]:
    """Every string the action message shows."""
    lines = [message.headline]
    if message.items_heading:
        lines.append(message.items_heading)
    for item in message.items:
        name = f" ({item.display_name})" if item.display_name else ""
        lines.append(f"{item.address}{name}, in {item.fields}")
        if item.lines:
            lines.extend(f"{line.kind.capitalize()}: {line.text}" for line in item.lines)
        elif message.kind == "warn":
            lines.append(NO_CODE_TEXT)
    lines.extend(message.notes)
    return lines
