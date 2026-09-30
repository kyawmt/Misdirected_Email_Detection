"""Run the replay plan through the scoring API and reduce each window to aggregates.

The driver is a client of the API, like the review screen: it sends Phase 1
requests and reads responses. It refuses to run against a service that does not
report the expected bundle. For every email it keeps an `Observation` (no
address, name, subject, or body) and, from the published feature rows of the
same draft, the model inputs used for input drift. Windows are then reduced to
counts, histograms, and percentiles. The only per-draft output is the review
queue: draft id, decision, and a coarse stratum.

A request that fails is an observation, not an exception: the replay records
its category and message and carries on.
"""

from __future__ import annotations

import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd

from med_monitor.drift import input_drift
from med_monitor.observations import ASSESSED, WindowSummary, observe
from med_monitor.stream import check_plan
from med_monitor.version import (
    ALLOWED_STRATA,
    API_CONTRACT_VERSION,
    MONITOR_VERSION,
    NEAR_BAND,
    PLAN_SEED,
    SNAPSHOT_ID,
    WARMUP_CALLS,
    WARNED_STRATUM,
)


class ReplayError(RuntimeError):
    """The replay cannot run against this service."""


def expected_bundle(policy_dir: Path) -> dict:
    """The bundle the monitor expects to see, read from the frozen policy file."""
    policy = json.loads((Path(policy_dir) / "policy.json").read_text(encoding="utf-8"))
    return {
        "contract_version": API_CONTRACT_VERSION,
        "snapshot_id": SNAPSHOT_ID,
        "model_version": policy["model_version"],
        "feature_spec_version": policy["feature_spec_version"],
        "policy_version": policy["policy_version"],
        "T_warn": policy["T_warn"],
        "blocking_enabled": policy["blocking_enabled"],
    }


def check_ready(client, expected: dict) -> dict:
    """GET /ready must report exactly the expected bundle, or the replay does not start."""
    response = client.get("/ready")
    if response.status_code != 200:
        raise ReplayError(f"The service is not ready (HTTP {response.status_code})")
    body = response.json()
    for name, value in expected.items():
        if name == "blocking_enabled":
            if body.get(name) is not False or value is not False:
                raise ReplayError("The service does not report blocking disabled")
        elif body.get(name) != value:
            raise ReplayError(f"The service reports {name}={body.get(name)!r}, expected {value!r}")
    return {key: body[key] for key in ("load_seconds",) if key in body}


# ------------------------------------------------------------------ probes


def probe_requests(base: dict) -> dict[str, dict]:
    """Failure probes derived from one ordinary request. They are not counted as traffic."""
    address = base["to"][0]["address"]
    local, _, domain = address.partition("@")
    probes = {
        "unknown_address": {**base, "to": [{"address": f"{local[:-1]}@{domain}"}], "cc": [], "bcc": []},
        "malformed_address": {**base, "to": [{"address": address.replace("@", ".")}], "cc": [], "bcc": []},
        "unknown_snapshot": {**base, "context_snapshot_id": "unknown-snapshot"},
        "no_recipients": {**base, "to": [], "cc": [], "bcc": []},
        "body_over_limit": {**base, "body": "x" * 20_001},
    }
    return probes


def run_probes(client, base: dict) -> list[dict]:
    """Send each probe once. A probe passes when it is unable to assess with no decision and no score."""
    results = []
    for name, payload in probe_requests(base).items():
        response = client.post("/assess", json=payload)
        try:
            body = response.json()
        except ValueError:
            body = None
        observation = observe(response.status_code, body, 0.0)
        clean = (
            isinstance(body, dict)
            and observation.status == "unable_to_assess"
            and not observation.problems
            and body.get("decision") is None
        )
        results.append(
            {
                "probe": name,
                "http_status": response.status_code,
                "status": observation.status,
                "category": observation.category,
                "message": observation.message,
                "no_decision_and_no_score": bool(clean and body.get("email_risk_score") is None),
            }
        )
    return results


# --------------------------------------------------------------- review queue


def stratum_of(decision: str, email_risk: float) -> tuple[str, float]:
    """(stratum, inclusion probability) for a scored email."""
    if decision == "warn":
        return WARNED_STRATUM, 1.0
    for name, low, high, probability in ALLOWED_STRATA:
        if low <= email_risk < high:
            return name, probability
    raise ReplayError(f"Email risk {email_risk} fits no review stratum")


def queue_decision(window: int, position: int, probability: float) -> bool:
    """A reproducible coin for one email occurrence. It depends on the window and position only."""
    if probability >= 1.0:
        return True
    return bool(np.random.default_rng([PLAN_SEED, 2, window, position]).random() < probability)


# ------------------------------------------------------------------ the run


def email_flags(rows: pd.DataFrame) -> dict:
    """Feature-row facts about one email, used for cold-start and slice counts."""
    return {
        "cold_start_sender": bool((rows["sender_history_available"] == 0).any()),
        "novel_recipient": bool((rows["recipient_novel_to_sender"] == 1).any()),
        "external_recipient": bool((rows["recipient_is_internal"] == 0).any()),
    }


class SliceCounter:
    """Counts for the slices an investigation looks at, without any per-email record."""

    NAMES = ("novel_recipient", "external_recipient")

    def __init__(self, t_warn: float, near_low: float):
        self.t_warn, self.near_low = t_warn, near_low
        self.data = {name: {"yes": self._empty(), "no": self._empty()} for name in self.NAMES}

    @staticmethod
    def _empty() -> dict:
        return {"emails": 0, "warnings": 0, "near_band": 0, "limited_relationship_history": 0, "highest_allowed": None}

    def add(self, flags: dict, observation) -> None:
        if observation.status != ASSESSED:
            return
        for name in self.NAMES:
            cell = self.data[name]["yes" if flags[name] else "no"]
            cell["emails"] += 1
            cell["warnings"] += observation.decision == "warn"
            cell["near_band"] += self.near_low <= observation.email_risk < self.t_warn
            cell["limited_relationship_history"] += observation.limited_history_recipients > 0
            if observation.email_risk < self.t_warn:
                if cell["highest_allowed"] is None or observation.email_risk > cell["highest_allowed"]:
                    cell["highest_allowed"] = observation.email_risk


def run_replay(plan: dict, requests: dict[str, dict], features: pd.DataFrame, client, expected: dict, reference: dict, *, subset_of: dict[str, str], progress=None) -> dict:
    """Score every planned email through the API and reduce each window."""
    check_plan(plan, subset_of)
    started = time.perf_counter()
    ready = check_ready(client, expected)
    t_warn = float(expected["T_warn"])
    by_draft = {draft_id: frame for draft_id, frame in features.groupby("draft_id", sort=False)}
    missing = [draft_id for draft_id in requests if draft_id not in by_draft]
    if missing:
        raise ReplayError(f"No published feature rows for {len(missing)} planned drafts")
    first_window = plan["windows"][0]["draft_ids"]
    for draft_id in first_window[:WARMUP_CALLS]:
        client.post("/assess", json=requests[draft_id])
    probes_before = run_probes(client, requests[plan["probe_draft_id"]])

    block_summary = {"reference": WindowSummary(t_warn), "current": WindowSummary(t_warn)}
    block_rows: dict[str, list[pd.DataFrame]] = {"reference": [], "current": []}
    block_slices = {"reference": SliceCounter(t_warn, t_warn - NEAR_BAND), "current": SliceCounter(t_warn, t_warn - NEAR_BAND)}
    windows_out, queue_items, population = [], [], {}
    for window in plan["windows"]:
        number, role = window["window"], window["role"]
        summary = WindowSummary(t_warn)
        slices = SliceCounter(t_warn, t_warn - NEAR_BAND)
        rows = []
        counts: dict[str, int] = {}
        for position, draft_id in enumerate(window["draft_ids"]):
            begin = time.perf_counter()
            response = client.post("/assess", json=requests[draft_id])
            elapsed = (time.perf_counter() - begin) * 1000
            try:
                body = response.json()
            except ValueError:
                body = None
            observation = observe(response.status_code, body, elapsed)
            draft_rows = by_draft[draft_id]
            flags = email_flags(draft_rows)
            for target in (summary, block_summary[role]):
                target.add(observation, email_flags=flags, draft_id=draft_id)
            if observation.status == ASSESSED and len(draft_rows) != observation.recipient_count:
                for target in (summary, block_summary[role]):
                    target.problems["feature rows and response disagree on the recipient count"] += 1
            slices.add(flags, observation)
            block_slices[role].add(flags, observation)
            rows.append(draft_rows.assign(occurrence=number * 100_000 + position))
            if observation.status == ASSESSED:
                stratum, probability = stratum_of(observation.decision, observation.email_risk)
                counts[stratum] = counts.get(stratum, 0) + 1
                if queue_decision(number, position, probability):
                    queue_items.append(
                        {
                            "window": number,
                            "position": position,
                            "draft_id": draft_id,
                            "decision": observation.decision,
                            "stratum": stratum,
                            "inclusion_probability": probability,
                        }
                    )
        frame = pd.concat(rows, ignore_index=True)
        block_rows[role].append(frame)
        population[str(number)] = dict(sorted(counts.items()))
        windows_out.append(
            {
                "window": number,
                "role": role,
                "planned_injected_share": window["injected_share"],
                "injected_emails": window["injected_emails"],
                "first_sent_at": window["first_sent_at"],
                "last_sent_at": window["last_sent_at"],
                "rows": int(len(frame)),
                "summary": summary.to_dict(),
                "slices": slices.data,
                "input_drift": input_drift(reference, frame),
            }
        )
        if progress:
            progress(number, summary.to_dict())
    probes_after = run_probes(client, requests[plan["probe_draft_id"]])
    blocks = {}
    for role in ("reference", "current"):
        frame = pd.concat(block_rows[role], ignore_index=True)
        blocks[role] = {
            "windows": [item["window"] for item in windows_out if item["role"] == role],
            "rows": int(len(frame)),
            "summary": block_summary[role].to_dict(),
            "slices": block_slices[role].data,
            "input_drift": input_drift(reference, frame),
        }
    return {
        "monitor_version": MONITOR_VERSION,
        "kind": "replay",
        "plan_checksum": plan["checksum_sha256"],
        "bundle": expected,
        "service": ready,
        "warmup_calls": WARMUP_CALLS,
        "probes": {"before": probes_before, "after": probes_after},
        "windows": windows_out,
        "blocks": blocks,
        "review_queue": {
            "strata": [{"name": WARNED_STRATUM, "inclusion_probability": 1.0}]
            + [{"name": name, "score_from": low, "score_below": min(high, 1.0), "inclusion_probability": probability} for name, low, high, probability in ALLOWED_STRATA],
            "population": population,
            "items": queue_items,
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 1),
    }
