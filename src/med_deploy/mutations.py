"""Does the scenario regression suite catch a change to the code that serves decisions?

Each mutation is a one-line change to the scoring or API code, applied to a
scratch copy of `src/` (never the real tree). The API is started from that copy,
against the real published bundle, and the recorded fixtures are replayed. A
mutation is **detected** when at least one fixture fails. A control run of the
unmutated copy must pass every fixture, or the harness is not trustworthy.

The mutations cover what the brief asks the suite to catch: a changed decision,
a changed score, changed provenance, a missing evidence limitation, and an
`unable_to_assess` body that carries an allow.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import httpx

from med_deploy.records import machine, now_utc
from med_deploy.scenarios import load_record, replay, requests_for
from med_deploy.serving import BundlePaths, api_process
from med_deploy.version import DEFAULT_PATHS, DEPLOY_VERSION, SCENARIO_RECORD

# (name, file under src/, old text, new text, what the change does)
MUTATIONS = (
    (
        "equality_allows",
        "med_policy/decision.py",
        '"decision": "warn" if email_risk >= bundle.t_warn else "allow",',
        '"decision": "warn" if email_risk > bundle.t_warn else "allow",',
        "a score exactly at the cutoff allows instead of warning",
    ),
    (
        "mean_instead_of_maximum",
        "med_policy/decision.py",
        "email_risk = float(scores.max())",
        "email_risk = float(scores.mean())",
        "the email risk is the mean recipient risk, not the maximum",
    ),
    (
        "score_shifted",
        "med_api/service.py",
        '"email_risk_score": float(result["email_risk"]),',
        '"email_risk_score": float(result["email_risk"]) * 0.999,',
        "the reported email risk score is 0.1% lower than the decision's",
    ),
    (
        "evidence_limitations_dropped",
        "med_api/service.py",
        "def _limitations(row) -> list[str]:\n    codes = []",
        "def _limitations(row) -> list[str]:\n    return []\n    codes = []",
        "no recipient carries an evidence limitation",
    ),
    (
        "history_rule_changed",
        "med_api/service.py",
        '"history_rule": "sent mail strictly earlier than the cutoff",',
        '"history_rule": "all mail",',
        "provenance states a different history rule",
    ),
    (
        "cutoff_misreported",
        "med_api/service.py",
        '"T_warn": context.bundle.t_warn,\n                "blocking_enabled": False,',
        '"T_warn": context.bundle.t_warn * 0.5,\n                "blocking_enabled": False,',
        "provenance reports a different cutoff than the one applied",
    ),
    (
        "failure_carries_an_allow",
        "med_api/service.py",
        '            "decision": None,\n            "email_risk_score": None,\n            "flagged_recipients": None,',
        '            "decision": "allow",\n            "email_risk_score": None,\n            "flagged_recipients": None,',
        "an unable_to_assess response carries the decision allow",
    ),
)


def _scratch_source(root: Path, scratch: Path, change: tuple | None) -> Path:
    source = scratch / "src"
    shutil.copytree(Path(root) / "src", source, ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    if change is not None:
        _, relative, old, new, _ = change
        path = source / relative
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise ValueError(f"{relative} holds {text.count(old)} copies of the text to mutate, expected 1")
        path.write_text(text.replace(old, new), encoding="utf-8")
    return source


def _run(root: Path, record: dict, requests: dict, change: tuple | None) -> dict:
    with tempfile.TemporaryDirectory(prefix="med-mutation-") as raw:
        scratch = Path(raw)
        source = _scratch_source(root, scratch, change)
        paths = BundlePaths.default(root, scratch / "feedback.jsonl")
        with api_process(paths, root, extra_env={"PYTHONPATH": str(source)}) as served:
            with httpx.Client(base_url=served.url, timeout=60.0) as client:
                outcome = replay(record, client, requests)
    failed = [item for item in outcome["fixtures"] if not item["passed"]]
    return {
        "fixtures": len(outcome["fixtures"]),
        "failed": len(failed),
        "first_problem": failed[0]["problems"][0] if failed else None,
        "first_failed_fixture": failed[0]["key"] if failed else None,
    }


def run_mutation_checks(root: Path) -> dict:
    root = Path(root).resolve()
    record = load_record(root / SCENARIO_RECORD)
    requests = requests_for(record, root / DEFAULT_PATHS["data"])
    control = _run(root, record, requests, None)
    results = []
    for change in MUTATIONS:
        name, relative, _, _, what = change
        outcome = _run(root, record, requests, change)
        results.append({"mutation": name, "file": f"src/{relative}", "change": what, "detected": outcome["failed"] > 0, **outcome})
    return {
        "kind": "mutation_checks",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "method": "each change is applied to a scratch copy of src/; the API is started from that copy against the published bundle; the recorded fixtures are replayed; the real source tree is never edited",
        "control": control,
        "control_passed": control["failed"] == 0,
        "mutations": results,
        "all_detected": all(item["detected"] for item in results),
        "machine": machine(),
    }
