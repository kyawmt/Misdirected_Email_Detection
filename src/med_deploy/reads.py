"""Measure which published files the API and the review screen read.

The API is started exactly as it is served (`python -m med_api serve`) under the
audit wrapper, and the review screen is driven with real requests by the smoke
check under the same wrapper. The files each one opened under `data/` and
`artifacts/` are compared with what `check-bundle` says the process needs. The
image file lists come from this record, so an image holds what its process
reads and nothing else. No process may write anywhere under the repository
root: the published files stay untouched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from med_deploy.bundle import API_SCOPE, UI_SCOPE, required_files
from med_deploy.records import machine, now_utc
from med_deploy.serving import BundlePaths, api_environment, free_port, wait_until_serving
from med_deploy.version import DEFAULT_PATHS, DEPLOY_VERSION, LOCAL_HOST


def _expected(scope: str, root: Path) -> list[str]:
    paths = BundlePaths.default(root, Path("unused"))
    files = required_files(scope, data_dir=paths.data, features_dir=paths.features, model_path=paths.model, policy_dir=paths.policy.parent, root=root)
    return sorted(path.resolve().relative_to(root.resolve()).as_posix() for path in files)


def measure_reads(root: Path) -> dict:
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory(prefix="med-deploy-reads-") as raw:
        scratch = Path(raw)
        api_out, ui_out, feedback = scratch / "api.json", scratch / "ui.json", scratch / "feedback.jsonl"
        port = free_port()
        url = f"http://{LOCAL_HOST}:{port}"
        env = {**os.environ, **api_environment(BundlePaths.default(root, feedback), root)}
        with open(scratch / "api.log", "w", encoding="utf-8") as log:
            api = subprocess.Popen(
                [sys.executable, "-m", "med_deploy.audited", str(api_out), str(root), "--", "med_api", "serve", "--host", LOCAL_HOST, "--port", str(port)],
                cwd=root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                wait_until_serving(url, api)
                ui = subprocess.run(
                    [sys.executable, "-m", "med_deploy.audited", str(ui_out), str(root), "--", "med_deploy", "smoke", "--api", url, "--feedback-file", str(feedback), "--root", str(root), "--no-file-hashes"],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                )
            finally:
                api.terminate()
                try:
                    api.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    api.kill()
                    api.wait(timeout=5)
        api_audit = json.loads(api_out.read_text(encoding="utf-8"))
        ui_audit = json.loads(ui_out.read_text(encoding="utf-8"))
        feedback_lines = len(feedback.read_text(encoding="utf-8").splitlines()) if feedback.exists() else 0
    processes = {}
    for name, scope, audit in (("api", API_SCOPE, api_audit), ("ui", UI_SCOPE, ui_audit)):
        expected = _expected(scope, root)
        processes[name] = {
            "read": audit["read"],
            "expected_by_bundle_check": expected,
            "matches_expected": audit["read"] == expected,
            "read_but_not_expected": sorted(set(audit["read"]) - set(expected)),
            "expected_but_not_read": sorted(set(expected) - set(audit["read"])),
            "written_under_root": audit["written_under_root"],
            "files_written_outside_root": audit["files_written_outside_root"],
        }
    return {
        "kind": "reads",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "method": "each process ran under a Python audit hook that logs open events; the API was started as `python -m med_api serve` and stopped with SIGTERM, "
        "the review screen was driven by the smoke check (AppTest) against it with file hashing off",
        "workload": {
            "api": "startup, then the smoke check's assessments (allow, warn, edits, invalid_input, unavailable) and one feedback click",
            "ui": "page load, every curated example's catalog build, readiness, assessments, edits, and one feedback click",
            "smoke_passed": ui.returncode == 0,
            "feedback_lines_written_to_the_disposable_file": feedback_lines,
        },
        "policy_dir": Path(DEFAULT_PATHS["policy"]).parent.as_posix(),
        "processes": processes,
        "machine": machine(),
    }
