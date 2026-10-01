"""Stored records for the deployment checks.

A measurement or rehearsal record is written once and never replaced: a new
measurement of the same thing needs a new DEPLOY_VERSION or a new path. Command
runs (pytest, validate) are the exception: `test_runs.json` keeps the latest run
of each named command with its date, so the report always describes the run that
last happened.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


class RecordExists(FileExistsError):
    """A record is not overwritten."""


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_record(path: Path, payload: dict) -> Path:
    """Write `payload` as JSON to a new file. Refuses an existing one."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2) + "\n")
    except FileExistsError as error:
        raise RecordExists(f"{path} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.") from error
    return path


def read_record(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def machine() -> dict:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


# ----------------------------------------------------------------- command runs

_COUNTS = {
    "passed": re.compile(r"(\d+) passed"),
    "failed": re.compile(r"(\d+) failed"),
    "errors": re.compile(r"(\d+) errors?\b"),
    "skipped": re.compile(r"(\d+) skipped"),
    "deselected": re.compile(r"(\d+) deselected"),
    "checks_passed": re.compile(r"(\d+) checks? passed"),
}
_PYTEST_SUMMARY = re.compile(r"\b(?:passed|failed|errors?)\b.*\bin [\d.]+s\b")


def parse_summary(output: str) -> dict:
    """Counts from the last pytest summary line (or a `validate` line), if there is one."""
    lines = [line for line in output.splitlines() if line.strip()]
    summary = next((line for line in reversed(lines) if _PYTEST_SUMMARY.search(line.strip())), None)
    if summary is None:
        summary = next((line for line in reversed(lines) if _COUNTS["checks_passed"].search(line)), "")
    found = {"summary_line": summary.strip().strip("=").strip()}
    for name, pattern in _COUNTS.items():
        match = pattern.search(summary)
        if match:
            found[name] = int(match.group(1))
    return found


def record_run(name: str, command: list[str], runs_path: Path, *, cwd: Path | None = None, note: str | None = None) -> dict:
    """Run `command`, then store its exit code, wall time, and summary counts under `name`."""
    started = time.perf_counter()
    when = now_utc()
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    output = completed.stdout + "\n" + completed.stderr
    run = {
        "name": name,
        "command": shlex.join(_display(item) for item in command),
        "date_utc": when,
        "exit_code": completed.returncode,
        "seconds": round(elapsed, 1),
        **parse_summary(output),
        "machine": machine(),
    }
    if note:
        run["note"] = note
    if completed.returncode != 0:
        run["output_tail"] = output.strip().splitlines()[-15:]
    runs_path = Path(runs_path)
    runs = read_record(runs_path) if runs_path.exists() else {"runs": {}}
    runs["runs"][name] = run
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    runs_path.write_text(json.dumps(runs, indent=2) + "\n", encoding="utf-8")
    return run


def _display(item: str) -> str:
    """The command as written, with the interpreter shown as `python`."""
    return "python" if item == sys.executable else item
