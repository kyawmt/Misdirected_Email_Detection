"""AC05 measurement on the API boundary.

One request in flight against the running app through the FastAPI test
client. Each timing starts when the client sends `POST /assess` and ends when
the response body is complete, so it covers validation, directory lookup,
features, the model, the policy, and response preparation. The server-side
`duration_ms` (handler start to response dict) is recorded beside it.

Workload: every `validation_product_like` draft, rebuilt as a request, in one
permutation drawn with a fixed seed before anything is timed. Time order is
not used, because early drafts have the smallest histories and would
understate latency. Twenty warm-up calls precede the measured calls and are
not counted. The recipient-count, month, and sender-history mix of the
measured requests is recorded with the result.
"""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from med_data.io import read_dataset
from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.fixtures import request_from_draft, validation_draft_ids
from med_api.version import API_CONTRACT_VERSION

WARMUP = 20
MIN_MEASURED = 1000
TARGET_P95_MS = 300.0
WORKLOAD_SEED = 20260926
SUBSET = "validation_product_like"
# Bounds for the sender-history bands: sent messages by the sender strictly
# before the draft, counted without family exclusions.
HISTORY_BANDS = (0, 1000, 2500, 5000, 10000, 20000, 40000)


class LatencyError(RuntimeError):
    pass


def measure(paths: ApiPaths, output: Path | None = None) -> dict:
    """Measure once. Refuses to start if `output` already exists."""
    if output is not None and Path(output).exists():
        raise LatencyError(f"{output} exists. A latency record is not overwritten; use a new bundle version.")
    dataset = read_dataset(paths.data)
    draft_ids = validation_draft_ids(dataset, SUBSET)
    if len(draft_ids) < MIN_MEASURED:
        raise LatencyError(f"Need at least {MIN_MEASURED} {SUBSET} drafts, found {len(draft_ids)}")
    order = np.random.default_rng(WORKLOAD_SEED).permutation(len(draft_ids))
    measured_ids = [draft_ids[index] for index in order]
    warmup_ids = measured_ids[:WARMUP]
    payloads = {draft_id: request_from_draft(dataset, draft_id) for draft_id in measured_ids}
    workload = _workload_mix(dataset, measured_ids)
    stored = pd.read_csv(paths.policy.parent / "validation_scores.csv", float_precision="round_trip").set_index("draft_id")

    started = time.perf_counter()
    client = TestClient(create_app(paths))
    client.__enter__()
    cold_start = time.perf_counter() - started
    try:
        ready = client.get("/ready")
        if ready.status_code != 200:
            raise LatencyError(f"App is not ready: {ready.json()}")
        t_warn = ready.json()["T_warn"]
        for draft_id in warmup_ids:
            client.post("/assess", json=payloads[draft_id])
        client_ms, server_ms, statuses = [], [], {}
        decisions_match, max_diff, at_cutoff = 0, 0.0, []
        for draft_id in measured_ids:
            begin = time.perf_counter()
            response = client.post("/assess", json=payloads[draft_id])
            _ = response.content
            client_ms.append((time.perf_counter() - begin) * 1000)
            body = response.json()
            statuses[body["status"]] = statuses.get(body["status"], 0) + 1
            server_ms.append(body["duration_ms"])
            if body["status"] != "assessed":
                continue
            expected = stored.loc[draft_id]
            decisions_match += int((body["decision"] == "warn") == bool(expected["warned"]))
            max_diff = max(max_diff, abs(body["email_risk_score"] - float(expected["email_risk"])))
            if float(expected["email_risk"]) == t_warn:
                at_cutoff.append(
                    {"draft_id": draft_id, "api_email_risk_score": body["email_risk_score"], "T_warn": t_warn, "decision": body["decision"]}
                )
    finally:
        client.__exit__(None, None, None)

    client_values = np.asarray(client_ms)
    server_values = np.asarray(server_ms)
    p95 = float(np.percentile(client_values, 95))
    import fastapi
    import sklearn

    return {
        "contract_version": API_CONTRACT_VERSION,
        "boundary": "test client sends POST /assess until the response body is complete, in process, no network",
        "server_boundary": "handler start after body read until the response dict is ready (duration_ms)",
        "subset": SUBSET,
        "workload": {
            "drawn": f"every {SUBSET} draft, in one permutation with seed {WORKLOAD_SEED}, fixed before timing",
            "warmup": f"the first {WARMUP} drafts of that permutation, called once each and not timed; they are measured again in order",
            **workload,
        },
        "warmup_calls": WARMUP,
        "measured_calls": int(len(client_values)),
        "concurrency": 1,
        "statuses": statuses,
        "client_p50_ms": float(np.percentile(client_values, 50)),
        "client_p95_ms": p95,
        "client_p99_ms": float(np.percentile(client_values, 99)),
        "client_max_ms": float(client_values.max()),
        "server_p50_ms": float(np.percentile(server_values, 50)),
        "server_p95_ms": float(np.percentile(server_values, 95)),
        "server_max_ms": float(server_values.max()),
        "cold_start_seconds": float(cold_start),
        "cold_start_includes": "app creation and startup: dataset read with checksums, bundle load with checksum checks, transformer load, directory and history index, history vectorization",
        "target_p95_ms": TARGET_P95_MS,
        "ac05": "met" if p95 < TARGET_P95_MS else "not met",
        "recipient_mix": workload["recipients"],
        "parity": {
            "assessed": int(statuses.get("assessed", 0)),
            "decisions_matching_validation_table": decisions_match,
            "max_abs_email_risk_difference": max_diff,
            "drafts_at_T_warn": at_cutoff,
        },
        "versions": {
            **{key: value for key, value in ready.json().items() if key.endswith("_version")},
            "snapshot_id": ready.json().get("snapshot_id"),
            "python": platform.python_version(),
            "fastapi": fastapi.__version__,
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
    }


def write_once(result: dict, output: Path) -> None:
    import json

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")


def _workload_mix(dataset, draft_ids: list[str]) -> dict:
    """Recipient count, month, and sender-history size of the measured drafts."""
    drafts = dataset.drafts.set_index("draft_id").loc[draft_ids]
    recipients = dataset.draft_recipients.groupby("draft_id").size().loc[draft_ids]
    messages = dataset.messages
    sent = {sender: np.sort(group.to_numpy(dtype="datetime64[ns]")) for sender, group in messages.groupby("sender_contact_id")["sent_at"]}
    history = []
    for sender, moment in zip(drafts["sender_contact_id"], drafts["sent_at"], strict=True):
        times = sent.get(sender)
        cutoff = np.datetime64(pd.Timestamp(moment).tz_convert("UTC").tz_localize(None), "ns")
        history.append(0 if times is None else int(np.searchsorted(times, cutoff, side="left")))
    history = np.asarray(history)
    months = pd.Series([pd.Timestamp(moment).strftime("%Y-%m") for moment in drafts["sent_at"]])
    return {
        "recipients": {str(int(key)): int(value) for key, value in recipients.value_counts().sort_index().items()},
        "months": {str(key): int(value) for key, value in months.value_counts().sort_index().items()},
        "sender_history_messages": {
            "bands": _bands(history),
            "p25": float(np.percentile(history, 25)),
            "p50": float(np.percentile(history, 50)),
            "p75": float(np.percentile(history, 75)),
            "max": int(history.max()),
        },
    }


def _bands(values: np.ndarray) -> dict:
    out = {}
    edges = list(HISTORY_BANDS) + [None]
    for low, high in zip(edges[:-1], edges[1:]):
        mask = values >= low if high is None else (values >= low) & (values < high)
        out[f"{low}+" if high is None else f"{low}-{high - 1}"] = int(mask.sum())
    return out
