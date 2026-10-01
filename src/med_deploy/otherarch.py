"""The API image built and served for a second CPU architecture, with the scenario suite replayed against it.

CI runs on x86_64 Linux and a development machine may be arm64. The pinned wheels
and the floating-point results can differ between them, and the warning cutoff
`T_warn` is the exact score of one validation draft, so a last-digit difference
could flip that draft's decision. This builds the same Dockerfile for another
platform (emulated when it is not the host's), serves it on a local port with a
disposable feedback folder, replays the recorded fixtures, and records how far
each score is from the recorded one and whether the cutoff fixture still scores at
the cutoff and warns. Nothing here is a frozen-test evaluation or a latency claim:
emulation makes timing meaningless.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from med_deploy import container as dk
from med_deploy.records import machine, now_utc
from med_deploy.scenarios import load_record, replay, requests_for
from med_deploy.serving import free_port, wait_until_serving
from med_deploy.version import API_DOCKERFILE, API_IMAGE_NAME, DEFAULT_PATHS, DEPLOY_VERSION, LOCAL_HOST, SCENARIO_RECORD

EMULATED_START_TIMEOUT_SECONDS = 600


def check_platform(root: Path, platform: str) -> dict:
    root = Path(root).resolve()
    record = load_record(root / SCENARIO_RECORD)
    requests = requests_for(record, root / DEFAULT_PATHS["data"])
    tag = f"{API_IMAGE_NAME}:phase9-{platform.replace('/', '-')}"
    began = time.perf_counter()
    dk.docker("build", "--platform", platform, "-f", str(API_DOCKERFILE), "-t", tag, str(root), timeout=3600)
    build_seconds = round(time.perf_counter() - began, 1)
    identity = dk.image_identity(tag)
    inside = dk.image_environment(tag, root / "constraints.txt", platform=platform)
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="med-platform-") as raw:
        feedback = Path(raw)
        feedback.chmod(0o777)
        name = f"med-platform-check-{port}"
        dk.docker("run", "-d", "--name", name, "--platform", platform, "--read-only", "--tmpfs", "/tmp", "-p", f"{LOCAL_HOST}:{port}:8000", "-v", f"{feedback}:/feedback", tag)
        try:
            url = f"http://{LOCAL_HOST}:{port}"
            began = time.perf_counter()
            wait_until_serving(url, None, EMULATED_START_TIMEOUT_SECONDS)
            start_seconds = round(time.perf_counter() - began, 1)
            architecture = dk.docker("exec", name, "python", "-c", "import platform; print(platform.machine())").stdout.strip()
            with httpx.Client(base_url=url, timeout=120.0) as client:
                ready = client.get("/ready")
                outcome = replay(record, client, requests)
                differences = []
                cutoff = None
                for item in record["fixtures"]:
                    if item["expected"]["status"] != "assessed":
                        continue
                    body = client.post("/assess", json=requests[item["key"]]).json()
                    differences.append(abs(body["email_risk_score"] - item["expected"]["email_risk_score"]))
                    if item["key"] == "threshold_equality_warn":
                        cutoff = {"email_risk_score_equals_T_warn": body["email_risk_score"] == body["provenance"]["T_warn"], "decision": body["decision"]}
        finally:
            dk.docker("rm", "-f", name, check=False)
    return {
        "kind": "other_platform_check",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "platform": platform,
        "architecture": architecture,
        "image": {"id": identity["id"], "architecture": identity["architecture"], "size_bytes": identity["size_bytes"]},
        "build_seconds": build_seconds,
        "seconds_until_ready": start_seconds,
        "ready_http": ready.status_code,
        "environment": {
            "python": inside["python"],
            "platform": inside["platform"],
            "pyarrow_importable": inside["pyarrow_importable"],
            "packages": inside["packages"],
            "matches_constraints": inside["matches_constraints"],
            "key_packages": inside["key_packages"],
        },
        "regression": {"passed": outcome["passed"], "failed": outcome["failed"], "failed_fixtures": [item["key"] for item in outcome["fixtures"] if not item["passed"]]},
        "max_abs_email_risk_difference_from_the_record": max(differences),
        "cutoff_fixture": cutoff,
        "note": "Built and served for this platform (emulated when it is not the host's). The pins installed as wheels for it, every fixture was replayed, and the cutoff fixture was checked for an exact score at T_warn. Timing under emulation is not meaningful and is not reported.",
        "machine": machine(),
    }
