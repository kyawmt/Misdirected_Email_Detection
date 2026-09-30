"""What the service does today when handed a mismatched or corrupted bundle.

Each case builds the real API app on altered copies of the frozen files in a
temporary directory, then asks `/health`, `/ready`, and `/assess`. The frozen
files themselves are never edited. The expected result is the same every time:
the process stays up, `/ready` says 503, and `/assess` returns `unavailable`
with no decision and no score, so a bad bundle can never produce an allow.

This is evidence for the rollout notes. It is not a rollback mechanism: the
current code loads exactly one bundle version and refuses every other, including
the previous bundle. Switching between two loadable bundles belongs to Phase 9.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from med_api.context import ApiPaths
from med_monitor.version import FEATURE_SPEC_VERSION, MODEL_VERSION, MONITOR_VERSION, POLICY_VERSION


def previous(version: str) -> str:
    """The version before this one: the trailing number minus one. It names the previous bundle on disk."""
    return re.sub(r"(\d+)$", lambda match: str(int(match.group(1)) - 1), version)



def _flip_last_byte(path: Path) -> None:
    data = bytearray(Path(path).read_bytes())
    data[-1] ^= 0x01
    Path(path).write_bytes(bytes(data))


def _policy_copy(base: ApiPaths, tmp: Path, **changes) -> ApiPaths:
    policy = json.loads(Path(base.policy).read_text(encoding="utf-8"))
    for key, value in changes.items():
        if key == "model_checksum":
            policy["checksums"]["model.joblib"] = value
        else:
            policy[key] = value
    target = tmp / "policy.json"
    target.write_text(json.dumps(policy), encoding="utf-8")
    return replace(base, policy=target)


def _model_corrupted(base: ApiPaths, tmp: Path) -> ApiPaths:
    target = tmp / "model.joblib"
    shutil.copyfile(base.model, target)
    _flip_last_byte(target)
    return replace(base, model=target)


def _features_tampered(base: ApiPaths, tmp: Path) -> ApiPaths:
    target = tmp / "features"
    shutil.copytree(base.features, target)
    _flip_last_byte(target / "features_train.csv")
    return replace(base, features=target)


def _previous_bundle(base: ApiPaths, tmp: Path) -> ApiPaths:
    root = Path(base.policy).parents[2] / "artifacts"
    return replace(
        base,
        policy=root / previous(POLICY_VERSION) / "policy.json",
        model=root / previous(MODEL_VERSION) / "model.joblib",
        features=root / previous(FEATURE_SPEC_VERSION),
    )


CASES = (
    ("control_unchanged", "The frozen bundle, untouched.", lambda base, tmp: base),
    ("policy_names_another_policy_version", f"policy.json says {previous(POLICY_VERSION)}.", lambda base, tmp: _policy_copy(base, tmp, policy_version=previous(POLICY_VERSION))),
    ("policy_names_another_model_run", "policy.json names a different model run.", lambda base, tmp: _policy_copy(base, tmp, model_run_name="another_run")),
    ("policy_model_checksum_mismatch", "policy.json records a different model checksum.", lambda base, tmp: _policy_copy(base, tmp, model_checksum="0" * 64)),
    ("model_file_corrupted", "One byte of model.joblib is flipped.", _model_corrupted),
    ("policy_enables_blocking", "policy.json sets blocking_enabled to true.", lambda base, tmp: _policy_copy(base, tmp, blocking_enabled=True)),
    ("policy_cutoff_not_a_number", "policy.json sets T_warn to text.", lambda base, tmp: _policy_copy(base, tmp, T_warn="high")),
    ("policy_file_missing", "policy.json does not exist.", lambda base, tmp: replace(base, policy=tmp / "missing.json")),
    ("feature_artifact_tampered", "One byte of features_train.csv is flipped.", _features_tampered),
    ("previous_bundle", f"The previous bundle on disk: {previous(POLICY_VERSION)}, {previous(MODEL_VERSION)}, {previous(FEATURE_SPEC_VERSION)}.", _previous_bundle),
)


def scrub(text, *roots: Path) -> str:
    """Replace machine-specific paths so the stored record is stable."""
    text = str(text)
    for root, label in zip(roots, ("<tmp>", "<repo>")):
        text = text.replace(str(root), label)
    return text


def run_case(name: str, description: str, builder, base: ApiPaths, request: dict, repo_root: Path) -> dict:
    from fastapi.testclient import TestClient

    from med_api.app import create_app

    with tempfile.TemporaryDirectory(prefix="med-bundle-check-") as raw:
        tmp = Path(raw)
        paths = replace(builder(base, tmp), feedback=tmp / "feedback.jsonl")
        with TestClient(create_app(paths)) as client:
            health = client.get("/health")
            ready = client.get("/ready")
            assessed = client.post("/assess", json=request)
        ready_body = ready.json()
        body = assessed.json()
        refused = (
            ready.status_code == 503
            and assessed.status_code == 503
            and body.get("status") == "unable_to_assess"
            and body.get("category") == "unavailable"
            and body.get("decision") is None
            and body.get("email_risk_score") is None
            and body.get("recipients") is None
            and "allow" not in json.dumps(body)
        )
        return {
            "case": name,
            "change": description,
            "health_http": health.status_code,
            "ready_http": ready.status_code,
            "ready_reason": scrub(ready_body.get("reason", ""), tmp, repo_root) if not ready_body.get("ready") else None,
            "assess_http": assessed.status_code,
            "assess_status": body.get("status"),
            "assess_category": body.get("category"),
            "assess_message": body.get("message"),
            "decision": body.get("decision"),
            "email_risk_score_reported": body.get("email_risk_score") is not None,
            "versions_reported": "provenance" in body,
            "outcome": "refused: unavailable, no decision, no score" if refused else ("served" if assessed.status_code == 200 else "unexpected"),
            "refused": refused,
            "served": assessed.status_code == 200 and body.get("status") == "assessed",
        }


def run_checks(base: ApiPaths, request: dict, repo_root: Path, cases=CASES, progress=None) -> dict:
    results = []
    for name, description, builder in cases:
        result = run_case(name, description, builder, base, request, repo_root)
        results.append(result)
        if progress:
            progress(result)
    return {
        "monitor_version": MONITOR_VERSION,
        "kind": "bundle_checks",
        "frozen_files_edited": False,
        "cases": results,
        "all_altered_bundles_refused": all(item["refused"] for item in results if item["case"] != "control_unchanged"),
        "control_served": next((item["served"] for item in results if item["case"] == "control_unchanged"), None),
        "not_covered": "A live switch between two loadable bundles. The service loads one bundle version and refuses every other, including the previous one.",
    }
