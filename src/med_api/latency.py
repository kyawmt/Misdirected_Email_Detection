"""AC05 measurement on the API boundary.

One request in flight against the running app through the FastAPI test
client. Each timing starts when the client sends `POST /assess` and ends when
the response body is complete, so it covers validation, directory lookup,
features, the model, the policy, and response preparation. The server-side
`duration_ms` (handler start to response dict) is recorded beside it.
Requests are rebuilt from `validation_product_like` drafts only.
"""

from __future__ import annotations

import os
import platform
import time

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from med_data.io import read_dataset
from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.fixtures import request_from_draft, validation_draft_ids
from med_api.version import API_CONTRACT_VERSION

WARMUP = 20
MEASURED = 1000
TARGET_P95_MS = 300.0


def measure(paths: ApiPaths) -> dict:
    dataset = read_dataset(paths.data)
    draft_ids = validation_draft_ids(dataset, "validation_product_like")
    if len(draft_ids) < MEASURED:
        raise ValueError(f"Need {MEASURED} validation drafts, found {len(draft_ids)}")
    payloads = [request_from_draft(dataset, draft_id) for draft_id in draft_ids]
    stored = pd.read_csv(paths.policy.parent / "validation_scores.csv", float_precision="round_trip").set_index("draft_id")

    started = time.perf_counter()
    client = TestClient(create_app(paths))
    client.__enter__()
    cold_start = time.perf_counter() - started
    try:
        ready = client.get("/ready")
        if ready.status_code != 200:
            raise RuntimeError(f"App is not ready: {ready.json()}")
        for payload in payloads[:WARMUP]:
            client.post("/assess", json=payload)
        client_ms, server_ms, statuses = [], [], {}
        decisions_match, max_diff, t_warn = 0, 0.0, ready.json()["T_warn"]
        margin = {}
        for draft_id, payload in zip(draft_ids[:MEASURED], payloads[:MEASURED], strict=True):
            begin = time.perf_counter()
            response = client.post("/assess", json=payload)
            _ = response.content
            client_ms.append((time.perf_counter() - begin) * 1000)
            body = response.json()
            statuses[body["status"]] = statuses.get(body["status"], 0) + 1
            server_ms.append(body["duration_ms"])
            if body["status"] == "assessed":
                expected = stored.loc[draft_id]
                decisions_match += int((body["decision"] == "warn") == bool(expected["warned"]))
                max_diff = max(max_diff, abs(body["email_risk_score"] - float(expected["email_risk"])))
                if float(expected["email_risk"]) == t_warn:
                    margin = {"draft_id": draft_id, "api_email_risk_score": body["email_risk_score"], "T_warn": t_warn, "decision": body["decision"]}
    finally:
        client.__exit__(None, None, None)

    client_values = np.asarray(client_ms)
    server_values = np.asarray(server_ms)
    recipients = [len({entry["address"].casefold() for role in ("to", "cc", "bcc") for entry in payload[role]}) for payload in payloads[:MEASURED]]
    counts = pd.Series(recipients).value_counts().sort_index()
    p95 = float(np.percentile(client_values, 95))
    import fastapi
    import sklearn

    return {
        "contract_version": API_CONTRACT_VERSION,
        "boundary": "test client sends POST /assess until the response body is complete, in process, no network",
        "server_boundary": "handler start after body read until the response dict is ready (duration_ms)",
        "subset": "validation_product_like",
        "warmup_calls": WARMUP,
        "measured_calls": int(len(client_values)),
        "concurrency": 1,
        "statuses": statuses,
        "client_p50_ms": float(np.percentile(client_values, 50)),
        "client_p95_ms": p95,
        "client_max_ms": float(client_values.max()),
        "server_p50_ms": float(np.percentile(server_values, 50)),
        "server_p95_ms": float(np.percentile(server_values, 95)),
        "server_max_ms": float(server_values.max()),
        "cold_start_seconds": float(cold_start),
        "cold_start_includes": "app creation and startup: dataset read with checksums, bundle load with checksum checks, transformer load, directory and history index, history vectorization",
        "target_p95_ms": TARGET_P95_MS,
        "ac05": "met" if p95 < TARGET_P95_MS else "not met",
        "recipient_mix": {str(int(key)): int(value) for key, value in counts.items()},
        "parity": {
            "assessed": int(statuses.get("assessed", 0)),
            "decisions_matching_validation_table": decisions_match,
            "max_abs_email_risk_difference": max_diff,
            "draft_at_T_warn": margin,
        },
        "versions": {
            **{key: value for key, value in ready.json().items() if key.endswith("_version")},
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
