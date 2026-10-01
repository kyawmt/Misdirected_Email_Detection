"""Warm scoring latency under a small, documented load, against a running API.

This is a new Phase 9 measurement of the packaged service. It is stored apart
from the one-shot Phase 6 record (`artifacts/med-api-latency/`), which it never
touches, and it is not a second evaluation of the frozen policy: every request
is a fictional `validation_product_like` draft and no frozen draft is read.

Workload, fixed before anything is timed:
- one permutation of the subset's drafts (send order, then id) drawn with the
  workload seed;
- warm-up: the first 20, sent once each and not timed;
- AC05 run: the next 1,000, one request in flight, timed at the client (an HTTP
  round trip from this process to the service) and, beside it, the service's
  own `duration_ms`;
- concurrent probe: the next 400 with 4 clients, reported apart from AC05;
- maximum-input probe: 30 further drafts stretched to the supported limits
  (20 recipients, 500-character subject, 20,000-character body), reported
  apart, because a service can pass on ordinary drafts and fail at its limits.

Nothing here stores an address, subject, body, or per-email score.
"""

from __future__ import annotations

import platform
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from med_deploy.records import now_utc
from med_deploy.version import (
    CONCURRENT_CALLS,
    CONCURRENT_CLIENTS,
    DEPLOY_VERSION,
    MAX_INPUT_BODY_CHARS,
    MAX_INPUT_PROBES,
    MAX_INPUT_RECIPIENTS,
    MEASURED_CALLS,
    TARGET_P95_MS,
    WARMUP_CALLS,
    WORKLOAD_SEED,
    WORKLOAD_SUBSET,
)

MAX_SUBJECT_CHARS = 500


class LatencyError(RuntimeError):
    """The workload cannot be built or the service is not ready."""


def workload_ids(data_dir: Path) -> dict[str, list[str]]:
    """The fixed draw: warm-up, AC05, concurrent, and maximum-input drafts, disjoint and in draw order."""
    from med_monitor.data import stream_rows, validation_ids

    _, keep = validation_ids(data_dir)
    frame = stream_rows(Path(data_dir) / "drafts.csv", keep, columns=("draft_id", "subset", "sent_at"))
    frame = frame.loc[frame["subset"] == WORKLOAD_SUBSET].sort_values(["sent_at", "draft_id"], kind="mergesort")
    ids = frame["draft_id"].tolist()
    needed = WARMUP_CALLS + MEASURED_CALLS + CONCURRENT_CALLS + MAX_INPUT_PROBES
    if len(ids) < needed:
        raise LatencyError(f"Need {needed} {WORKLOAD_SUBSET} drafts, found {len(ids)}")
    order = np.random.default_rng(WORKLOAD_SEED).permutation(len(ids))
    drawn = [ids[index] for index in order]
    cuts = np.cumsum([WARMUP_CALLS, MEASURED_CALLS, CONCURRENT_CALLS, MAX_INPUT_PROBES])
    return {
        "warmup": drawn[: cuts[0]],
        "measured": drawn[cuts[0] : cuts[1]],
        "concurrent": drawn[cuts[1] : cuts[2]],
        "max_input": drawn[cuts[2] : cuts[3]],
    }


def stretch(request: dict, contacts: pd.DataFrame, seed: int) -> dict:
    """The request stretched to the supported limits: 20 unique recipients visible at its send time, a full subject and body."""
    moment = pd.Timestamp(request["draft_timestamp"])
    sender = request["sender"]["address"].casefold()
    visible = contacts.loc[(contacts["directory_visible_from"] <= moment) & (contacts["email_address"].str.casefold() != sender)]
    chosen = visible.sample(n=MAX_INPUT_RECIPIENTS, random_state=seed)
    to = [{"address": row.email_address, "display_name": row.display_name} for row in chosen.iloc[:10].itertuples()]
    cc = [{"address": row.email_address, "display_name": row.display_name} for row in chosen.iloc[10:15].itertuples()]
    bcc = [{"address": row.email_address, "display_name": row.display_name} for row in chosen.iloc[15:].itertuples()]
    body = request["body"] or "Status update."
    subject = request["subject"] or "Update"
    return {
        **request,
        "to": to,
        "cc": cc,
        "bcc": bcc,
        "subject": ((subject + " ") * (MAX_SUBJECT_CHARS // (len(subject) + 1) + 1))[:MAX_SUBJECT_CHARS],
        "body": ((body + "\n") * (MAX_INPUT_BODY_CHARS // (len(body) + 1) + 1))[:MAX_INPUT_BODY_CHARS],
    }


def _percentiles(values: list[float]) -> dict:
    array = np.asarray(values, dtype=float)
    return {
        "p50_ms": float(np.percentile(array, 50)),
        "p95_ms": float(np.percentile(array, 95)),
        "p99_ms": float(np.percentile(array, 99)),
        "max_ms": float(array.max()),
        "mean_ms": float(array.mean()),
    }


def _timed_post(client, payload: dict) -> tuple[float, int | None, dict | None, str | None]:
    """(milliseconds, HTTP status, body, transport error). A transport error is a failure, not an exception."""
    import httpx

    begin = time.perf_counter()
    try:
        response = client.post("/assess", json=payload)
        content = response.content
    except httpx.HTTPError as error:
        return (time.perf_counter() - begin) * 1000, None, None, f"{type(error).__name__}"
    elapsed = (time.perf_counter() - begin) * 1000
    try:
        body = response.json() if content else None
    except ValueError:
        body = None
    return elapsed, response.status_code, body if isinstance(body, dict) else None, None


def _mix(requests: list[dict]) -> dict:
    counts = pd.Series([len({person["address"].strip().casefold() for role in ("to", "cc", "bcc") for person in item[role]}) for item in requests])
    return {str(int(key)): int(value) for key, value in counts.value_counts().sort_index().items()}


def _summarize(rows: list[tuple], stored: pd.DataFrame | None, ids: list[str] | None) -> dict:
    statuses: dict[str, int] = {}
    categories: dict[str, int] = {}
    transport = 0
    client_ms, server_ms = [], []
    matched, compared, max_diff = 0, 0, 0.0
    for index, (elapsed, code, body, error) in enumerate(rows):
        client_ms.append(elapsed)
        if error is not None or body is None:
            transport += 1
            statuses["transport_error" if error else "no_json_body"] = statuses.get("transport_error" if error else "no_json_body", 0) + 1
            continue
        status = body.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        if status != "assessed":
            categories[str(body.get("category"))] = categories.get(str(body.get("category")), 0) + 1
        if isinstance(body.get("duration_ms"), (int, float)):
            server_ms.append(float(body["duration_ms"]))
        if status == "assessed" and stored is not None and ids is not None:
            row = stored.loc[ids[index]]
            compared += 1
            matched += int((body["decision"] == "warn") == bool(row["warned"]))
            max_diff = max(max_diff, abs(body["email_risk_score"] - float(row["email_risk"])))
    result = {"requests": len(rows), "statuses": statuses, "failures": len(rows) - statuses.get("assessed", 0), "transport_errors": transport, "client": _percentiles(client_ms)}
    if categories:
        result["failure_categories"] = categories
    if server_ms:
        result["server"] = _percentiles(server_ms)
    if stored is not None:
        result["parity_with_stored_validation_scores"] = {"compared": compared, "decisions_matching": matched, "max_abs_email_risk_difference": max_diff}
    return result


def measure(api_url: str, *, data_dir: Path, policy_dir: Path, target: dict, environment: dict) -> dict:
    """Run the workload against `api_url`. `target` and `environment` describe what is being measured."""
    import httpx

    from med_monitor.data import load_contacts, load_requests

    ids = workload_ids(data_dir)
    every = [item for group in ids.values() for item in group]
    payloads = load_requests(data_dir, every)
    contacts = load_contacts(data_dir)
    contacts["directory_visible_from"] = pd.to_datetime(contacts["directory_visible_from"], utc=True)
    stored = pd.read_csv(Path(policy_dir) / "validation_scores.csv", float_precision="round_trip").set_index("draft_id")

    with httpx.Client(base_url=api_url, timeout=60.0) as client:
        ready = client.get("/ready")
        if ready.status_code != 200:
            raise LatencyError(f"The service is not ready: HTTP {ready.status_code} {ready.text[:200]}")
        served = ready.json()
        for draft_id in ids["warmup"]:
            client.post("/assess", json=payloads[draft_id])
        measured_requests = [payloads[draft_id] for draft_id in ids["measured"]]
        began = time.perf_counter()
        rows = [_timed_post(client, payload) for payload in measured_requests]
        ac05_seconds = time.perf_counter() - began
    ac05 = _summarize(rows, stored, ids["measured"])
    ac05["recipient_mix"] = _mix(measured_requests)
    ac05["wall_seconds"] = round(ac05_seconds, 2)
    p95 = ac05["client"]["p95_ms"]

    concurrent_requests = [payloads[draft_id] for draft_id in ids["concurrent"]]
    shares = [concurrent_requests[index::CONCURRENT_CLIENTS] for index in range(CONCURRENT_CLIENTS)]
    share_ids = [ids["concurrent"][index::CONCURRENT_CLIENTS] for index in range(CONCURRENT_CLIENTS)]

    def worker(part: list[dict]) -> list[tuple]:
        with httpx.Client(base_url=api_url, timeout=60.0) as local:
            return [_timed_post(local, payload) for payload in part]

    began = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENT_CLIENTS) as pool:
        parts = list(pool.map(worker, shares))
    concurrent_seconds = time.perf_counter() - began
    flat_rows = [row for part in parts for row in part]
    flat_ids = [item for part in share_ids for item in part]
    concurrent = _summarize(flat_rows, stored, flat_ids)
    concurrent["clients"] = CONCURRENT_CLIENTS
    concurrent["wall_seconds"] = round(concurrent_seconds, 2)
    concurrent["requests_per_second"] = round(len(flat_rows) / concurrent_seconds, 1)

    stretched = [stretch(payloads[draft_id], contacts, WORKLOAD_SEED + index) for index, draft_id in enumerate(ids["max_input"])]
    with httpx.Client(base_url=api_url, timeout=60.0) as client:
        max_rows = [_timed_post(client, payload) for payload in stretched]
    maximum = _summarize(max_rows, None, None)
    maximum["shape"] = f"{MAX_INPUT_RECIPIENTS} unique recipients, a {MAX_SUBJECT_CHARS}-character subject, a {MAX_INPUT_BODY_CHARS:,}-character body"

    return {
        "kind": "latency",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "claim": "AC05 measurement on this machine" if ac05["requests"] >= MEASURED_CALLS else "smoke measurement only",
        "boundary": "an httpx client on the host sends POST /assess to the service's published port and reads the whole response body; this includes the loopback hop "
        "and, for a container, the runtime's port forwarding, and excludes the review screen",
        "server_boundary": "duration_ms in the response: from the handler's start until the response dict is ready",
        "subset": WORKLOAD_SUBSET,
        "workload": {
            "drawn": f"every {WORKLOAD_SUBSET} draft in send order, one permutation with seed {WORKLOAD_SEED}, fixed before timing; the four groups are disjoint",
            "warmup_calls": WARMUP_CALLS,
            "warmup": "the first drafts of the permutation, sent once each and not timed",
            "measured_calls": MEASURED_CALLS,
            "concurrent_calls": CONCURRENT_CALLS,
            "concurrent_clients": CONCURRENT_CLIENTS,
            "max_input_probes": MAX_INPUT_PROBES,
        },
        "target_p95_ms": TARGET_P95_MS,
        "ac05": {
            "concurrency": 1,
            "result": "met" if p95 < TARGET_P95_MS else "not met",
            "client_p95_ms": p95,
            **ac05,
        },
        "concurrent_probe": concurrent,
        "maximum_input_probe": maximum,
        "served": {key: served.get(key) for key in ("contract_version", "snapshot_id", "model_version", "feature_spec_version", "policy_version", "T_warn", "blocking_enabled", "load_seconds")},
        "target": target,
        "environment_of_measured_process": environment,
        "client": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "httpx": httpx.__version__,
            "numpy": np.__version__,
        },
    }
