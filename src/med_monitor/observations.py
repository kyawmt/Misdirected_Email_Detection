"""What the monitor keeps from an API response, and how a window is summarized.

An observation holds counts, categories, and one email-level number. It never
holds an address, a display name, a subject, or a body. Windows are summarized
as aggregates and the observations are dropped, so no score, address, or text is
written anywhere new.

The API's structured log carries only status, category, decision, timing,
versions, and two counts (`med_api.service.LOG_FIELDS`). Failure messages,
evidence limitations, and scores are not in that allow-list, so those metrics
come from the response body the replay driver receives. A deployed monitor
would need the log allow-list widened, which is a privacy decision this phase
does not take; `docs/phase_8/MONITORING.md` records the proposal.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from med_monitor.version import NEAR_BAND, SCORE_EDGES

ASSESSED = "assessed"
UNABLE = "unable_to_assess"
UNEXPECTED = "unexpected_response"
FAILURE_CATEGORIES = ("invalid_input", "unavailable")
LIMITED_HISTORY = "LIMITED_RELATIONSHIP_HISTORY"
LIMITED_TEXT = "LIMITED_TEXT"
WITHHELD = "[message withheld: long or contains an address]"
MAX_MESSAGE_CHARS = 160


def safe_message(text) -> str:
    """A failure message as the API sent it, unless it could carry an address."""
    if not isinstance(text, str):
        return "[non-text message]"
    if "@" in text or len(text) > MAX_MESSAGE_CHARS:
        return WITHHELD
    return text


@dataclass(frozen=True)
class Observation:
    status: str
    http_status: int | None
    client_ms: float
    category: str | None = None
    message: str | None = None
    decision: str | None = None
    email_risk: float | None = None
    recipient_count: int = 0
    flagged_count: int = 0
    limited_history_recipients: int = 0
    limited_text_recipients: int = 0
    version_key: str = "unknown"
    server_ms: float | None = None
    problems: tuple[str, ...] = field(default_factory=tuple)


def version_key(provenance) -> str:
    if not isinstance(provenance, dict):
        return "unknown"
    parts = [provenance.get(name) for name in ("model_version", "feature_spec_version", "policy_version")]
    if not all(isinstance(part, str) for part in parts):
        return "unknown"
    return "|".join(parts)


def _finite_score(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0.0 <= value <= 1.0


def observe(http_status: int | None, body, client_ms: float) -> Observation:
    """Reduce one API response to an observation. Malformed bodies become `unexpected_response`."""
    if not isinstance(body, dict):
        return Observation(UNEXPECTED, http_status, client_ms, category=UNEXPECTED, message="The response was not a JSON object")
    server_ms = body.get("duration_ms") if isinstance(body.get("duration_ms"), (int, float)) else None
    key = version_key(body.get("provenance"))
    status = body.get("status")
    if status == ASSESSED:
        return _assessed(http_status, body, client_ms, key, server_ms)
    if status == UNABLE:
        problems = []
        category = body.get("category")
        if category not in FAILURE_CATEGORIES:
            return Observation(UNEXPECTED, http_status, client_ms, category=UNEXPECTED, message="Unknown failure category", version_key=key)
        # A failure must carry no decision and no score: unable to assess is never an allow.
        if body.get("decision") is not None or body.get("email_risk_score") is not None or body.get("recipients") is not None:
            problems.append("unable_to_assess response carried a decision, score, or recipients")
        return Observation(
            UNABLE,
            http_status,
            client_ms,
            category=category,
            message=safe_message(body.get("message")),
            version_key=key,
            server_ms=server_ms,
            problems=tuple(problems),
        )
    return Observation(UNEXPECTED, http_status, client_ms, category=UNEXPECTED, message="Unknown response status", version_key=key)


def _assessed(http_status, body: dict, client_ms: float, key: str, server_ms) -> Observation:
    recipients = body.get("recipients")
    risk = body.get("email_risk_score")
    decision = body.get("decision")
    if not isinstance(recipients, list) or not recipients or not _finite_score(risk) or decision not in ("allow", "warn", "block"):
        return Observation(UNEXPECTED, http_status, client_ms, category=UNEXPECTED, message="An assessed response was incomplete", version_key=key)
    history = text = flagged = 0
    for item in recipients:
        if not isinstance(item, dict) or not _finite_score(item.get("risk_score")):
            return Observation(UNEXPECTED, http_status, client_ms, category=UNEXPECTED, message="A recipient result was malformed", version_key=key)
        limits = {entry.get("code") for entry in item.get("evidence_limitations") or [] if isinstance(entry, dict)}
        history += LIMITED_HISTORY in limits
        text += LIMITED_TEXT in limits
        flagged += bool(item.get("flagged"))
    problems = []
    provenance = body.get("provenance") or {}
    if provenance.get("blocking_enabled") is not False:
        problems.append("provenance did not report blocking disabled")
    if body.get("mode") != "simulation":
        problems.append("response mode was not simulation")
    if decision == "block":
        problems.append("a block decision was returned")
    return Observation(
        ASSESSED,
        http_status,
        client_ms,
        decision=decision,
        email_risk=float(risk),
        recipient_count=len(recipients),
        flagged_count=flagged,
        limited_history_recipients=history,
        limited_text_recipients=text,
        version_key=key,
        server_ms=server_ms,
        problems=tuple(problems),
    )


def score_bins(t_warn: float) -> list[tuple[str, float, float]]:
    """(label, inclusive lower edge, exclusive upper edge) for the email-risk histogram."""
    labels = ["< 0.001", "0.001 to 0.1", "0.1 to 0.5", "0.5 to 0.9", "0.9 to 0.99"]
    edges = list(SCORE_EDGES)
    bins = [(labels[index], edges[index], edges[index + 1]) for index in range(len(labels))]
    bins.append(("0.99 to near band", edges[-1], t_warn - NEAR_BAND))
    bins.append(("near band", t_warn - NEAR_BAND, t_warn))
    bins.append(("at or above T_warn", t_warn, math.inf))
    return bins


def percentiles(values) -> dict:
    values = np.asarray(list(values), dtype=np.float64)
    if values.size == 0:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "max": None}
    return {
        "n": int(values.size),
        "p50": round(float(np.percentile(values, 50)), 3),
        "p95": round(float(np.percentile(values, 95)), 3),
        "p99": round(float(np.percentile(values, 99)), 3),
        "max": round(float(values.max()), 3),
    }


class WindowSummary:
    """Accumulates observations for one window and reduces them to aggregates."""

    def __init__(self, t_warn: float):
        self.t_warn = float(t_warn)
        self.requests = 0
        self.statuses: Counter = Counter()
        self.failures: Counter = Counter()
        self.decisions: Counter = Counter()
        self.problems: Counter = Counter()
        self.versions: Counter = Counter()
        self.recipient_counts: Counter = Counter()
        self.flagged_recipients = 0
        self.emails_with_flags = 0
        self.emails_limited_history = 0
        self.emails_limited_text = 0
        self.recipients_limited_history = 0
        self.recipients_limited_text = 0
        self.email_flags: Counter = Counter()
        self.bins = {label: 0 for label, _, _ in score_bins(self.t_warn)}
        self.highest_allowed: float | None = None
        self._drafts: set[str] = set()
        self._near_drafts: set[str] = set()
        self.client_ms: list[float] = []
        self.server_ms: list[float] = []

    def add(self, observation: Observation, *, email_flags: dict | None = None, draft_id: str | None = None) -> None:
        """Count one response. `draft_id` is used only to count distinct drafts; it is not kept."""
        self.requests += 1
        if draft_id is not None:
            self._drafts.add(draft_id)
        self.statuses[observation.status] += 1
        self.client_ms.append(observation.client_ms)
        if observation.server_ms is not None:
            self.server_ms.append(float(observation.server_ms))
        self.versions[observation.version_key] += 1
        for problem in observation.problems:
            self.problems[problem] += 1
        if observation.status != ASSESSED:
            self.failures[(observation.category, observation.message)] += 1
            return
        self.decisions[observation.decision] += 1
        self.recipient_counts[observation.recipient_count] += 1
        self.flagged_recipients += observation.flagged_count
        self.emails_with_flags += observation.flagged_count > 0
        self.emails_limited_history += observation.limited_history_recipients > 0
        self.emails_limited_text += observation.limited_text_recipients > 0
        self.recipients_limited_history += observation.limited_history_recipients
        self.recipients_limited_text += observation.limited_text_recipients
        for label, lo, hi in score_bins(self.t_warn):
            if lo <= observation.email_risk < hi:
                self.bins[label] += 1
                if label == "near band" and draft_id is not None:
                    self._near_drafts.add(draft_id)
                break
        if observation.email_risk < self.t_warn:
            if self.highest_allowed is None or observation.email_risk > self.highest_allowed:
                self.highest_allowed = observation.email_risk
        for name, value in (email_flags or {}).items():
            self.email_flags[name] += int(bool(value))

    def to_dict(self) -> dict:
        assessed = self.statuses[ASSESSED]
        near_label = next(label for label in self.bins if label.startswith("near band"))
        return {
            "requests": self.requests,
            "statuses": dict(sorted(self.statuses.items())),
            "assessed": assessed,
            "unable_to_assess": self.statuses[UNABLE],
            "unexpected_responses": self.statuses[UNEXPECTED],
            "failures": [
                {"category": category, "message": message, "count": count}
                for (category, message), count in sorted(self.failures.items(), key=lambda item: (str(item[0][0]), str(item[0][1])))
            ],
            "decisions": {name: self.decisions[name] for name in ("allow", "warn", "block")},
            "warnings": self.decisions["warn"],
            "blocks": self.decisions["block"],
            "invariant_problems": dict(sorted(self.problems.items())),
            "recipients_per_email": {str(key): value for key, value in sorted(self.recipient_counts.items())},
            "recipients": int(sum(key * value for key, value in self.recipient_counts.items())),
            "flagged_recipients": self.flagged_recipients,
            "emails_with_flagged_recipients": self.emails_with_flags,
            "emails_with_limited_relationship_history": self.emails_limited_history,
            "recipients_with_limited_relationship_history": self.recipients_limited_history,
            "emails_with_limited_text": self.emails_limited_text,
            "recipients_with_limited_text": self.recipients_limited_text,
            "email_flags_from_feature_rows": dict(sorted(self.email_flags.items())),
            "score_histogram": dict(self.bins),
            "near_band_emails": self.bins[near_label],
            "near_band_distinct_drafts": len(self._near_drafts),
            "distinct_drafts": len(self._drafts),
            "near_band": {"width": NEAR_BAND, "low": self.t_warn - NEAR_BAND, "high": self.t_warn},
            "highest_allowed_email_risk": self.highest_allowed,
            "margin_to_cutoff": None if self.highest_allowed is None else self.t_warn - self.highest_allowed,
            "client_latency_ms": percentiles(self.client_ms),
            "server_latency_ms": percentiles(self.server_ms),
            "versions": dict(sorted(self.versions.items())),
        }
