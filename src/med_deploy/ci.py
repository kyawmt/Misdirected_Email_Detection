"""The CI steps, defined once, and a clean-checkout dry run of them.

`.github/workflows/ci.yml` runs exactly `CI_STEPS`, in order, on a clean
checkout. A test requires the workflow to contain every command here, so the
workflow and this list cannot drift. GitHub Actions itself cannot be run from a
development machine, so `clean_checkout` runs the same steps in a scratch copy
of the working tree (tracked files and new files that are not ignored) inside a
fresh virtual environment, and records each step's outcome and time. That
checks the commands, the pins, and the tests; it does not prove that GitHub's
runner executes the workflow file.

CI never fits, retrains, selects a cutoff, or runs the frozen test evaluation.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from pathlib import Path

from med_deploy.records import machine, now_utc
from med_deploy.version import DEPLOY_VERSION, TESTED_PYTHON

# (name, command as run inside the virtual environment's activated shell)
CI_STEPS = (
    ("install from the pinned dependencies", 'python -m pip install -c constraints.txt -e ".[dev,ui,monitor]"'),
    ("dependency consistency", "python -m pip check"),
    ("environment matches the pins", "python -m med_deploy environment --constraints constraints.txt --check"),
    ("api bundle versions and checksums", "python -m med_deploy check-bundle --scope api"),
    ("ui bundle versions and checksums", "python -m med_deploy check-bundle --scope ui"),
    ("compact suite and public-doc checks", 'python -m pytest -m "not slow" -q'),
    ("api startup and end-to-end smoke", "python -m med_deploy smoke --spawn"),
)
# Strings that must never appear in a CI step: they retrain, reselect, or re-evaluate.
FORBIDDEN_IN_CI = (
    "med_features build",
    "med_models run",
    "med_policy select",
    "evaluate-test",
    "med_api latency",
    "med_data build",
)


def tracked_and_new_files(root: Path) -> list[str]:
    """Files a clean checkout of this working tree would hold: tracked, plus new and not ignored."""
    completed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root, capture_output=True, check=True)
    return [item.decode() for item in completed.stdout.split(b"\0") if item]


def clean_copy(root: Path, target: Path) -> int:
    files = tracked_and_new_files(root)
    for name in files:
        source = Path(root) / name
        if not source.is_file():
            continue
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return len(files)


def clean_checkout(root: Path, *, python: str | None = None) -> dict:
    """Run every CI step in a fresh copy and a fresh virtual environment."""
    root = Path(root).resolve()
    steps = []
    fresh_environment = None
    with tempfile.TemporaryDirectory(prefix="med-clean-checkout-") as raw:
        scratch = Path(raw)
        checkout = scratch / "checkout"
        checkout.mkdir()
        copied = clean_copy(root, checkout)
        environment = scratch / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        bin_dir = environment / ("Scripts" if sys.platform == "win32" else "bin")
        interpreter = str(bin_dir / "python")
        version = subprocess.run([interpreter, "-c", "import platform; print(platform.python_version())"], capture_output=True, text=True).stdout.strip()
        for name, command in CI_STEPS:
            argv = _split(command, interpreter)
            begin = time.perf_counter()
            completed = subprocess.run(argv, cwd=checkout, capture_output=True, text=True)
            seconds = time.perf_counter() - begin
            tail = (completed.stdout + "\n" + completed.stderr).strip().splitlines()[-6:]
            steps.append({"step": name, "command": command, "exit_code": completed.returncode, "seconds": round(seconds, 1), "output_tail": tail})
            if " environment " in command and completed.returncode == 0:
                fresh_environment = json.loads(completed.stdout[completed.stdout.index("{") :])
            if completed.returncode != 0:
                break
    return {
        "kind": "clean_checkout",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "what": "every CI step, run in a scratch copy of the working tree (tracked files and new files that are not ignored) inside a fresh virtual environment",
        "files_copied": copied,
        "venv_python": version,
        "tested_python": TESTED_PYTHON,
        "environment_of_the_fresh_venv": fresh_environment,
        "steps": steps,
        "passed": len(steps) == len(CI_STEPS) and all(item["exit_code"] == 0 for item in steps),
        "not_verified": "GitHub Actions itself: the workflow file was not executed by a GitHub runner from this machine",
        "machine": machine(),
    }


def _split(command: str, interpreter: str) -> list[str]:
    """Split like a shell, so `-m "not slow"` stays one argument, and run `python` as the venv's interpreter."""
    argv = shlex.split(command)
    if argv and argv[0] == "python":
        argv[0] = interpreter
    return argv
