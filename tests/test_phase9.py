"""Phase 9: scenario regression, packaging, end-to-end smoke, and deployment checks.

One real API process serves the module (started the way a deployment starts it,
on a disposable feedback file). The published data and artifacts are never
written, and neither is the default `var/feedback.jsonl`: a module fixture checks
both when the module finishes. Existing coverage is cited in
`med_deploy.coverage_map`, not copied.
"""

from __future__ import annotations

import ast
import copy
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.version import API_CONTRACT_VERSION, DEFAULT_PATHS
from med_deploy import scenarios as S
from med_deploy import version as V
from med_deploy.bundle import check_bundle
from med_deploy.ci import CI_STEPS, FORBIDDEN_IN_CI
from med_deploy.coverage_map import COVERAGE
from med_deploy.environment import parse_constraints
from med_deploy.records import RecordExists, write_record
from med_deploy.rehearsal import observe_failing
from med_deploy.report import documents
from med_deploy.serving import BundlePaths, api_process
from med_deploy.smoke import bundle_hashes, run_smoke
from med_monitor.data import FrozenRowError, subsets_by_draft
from med_policy.decision import PolicyBundle, decide

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / DEFAULT_PATHS["data"]
POLICY = ROOT / DEFAULT_PATHS["policy"]
DEFAULT_FEEDBACK = ROOT / "var" / "feedback.jsonl"
SLOW_TESTS = {
    "test_published_contract_passes_validation",
    "test_roundtrip_and_published_checksums",
    "test_manifest_timestamp_and_family_must_match_draft",
    "test_swapped_manifest_assignment_is_rejected",
    "test_scoring_view_hides_labels",
    "test_real_history_and_scoring_view_agree",
    "test_score_query_matches_batch_and_scoring_view",
}
KNOWN_MISSES = {"known_miss_lookalike": "S01", "known_miss_topic": "S04", "known_miss_first_contact": "S11"}


def _stat(path: Path):
    return (path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else None


@pytest.fixture(scope="module", autouse=True)
def published_files_stay_untouched():
    """No test here may write a published file or the default feedback file."""
    hashes, feedback = bundle_hashes(ROOT), _stat(DEFAULT_FEEDBACK)
    record = _stat(ROOT / V.SCENARIO_RECORD)
    yield
    assert bundle_hashes(ROOT) == hashes, "a published bundle file changed"
    assert _stat(DEFAULT_FEEDBACK) == feedback, "the default feedback file changed"
    assert _stat(ROOT / V.SCENARIO_RECORD) == record, "the scenario record changed"


@pytest.fixture(scope="module")
def record():
    return S.load_record(ROOT / V.SCENARIO_RECORD)


@pytest.fixture(scope="module")
def requests_by_key(record):
    return S.requests_for(record, DATA)


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    feedback = tmp_path_factory.mktemp("feedback") / "feedback.jsonl"
    with api_process(BundlePaths.default(ROOT, feedback), ROOT) as process:
        yield SimpleNamespace(url=process.url, feedback=feedback)


@pytest.fixture(scope="module")
def http(served):
    with httpx.Client(base_url=served.url, timeout=60.0) as client:
        yield client


@pytest.fixture(scope="module")
def policy():
    return json.loads(POLICY.read_text(encoding="utf-8"))


def _fixture(record, key):
    return next(item for item in record["fixtures"] if item["key"] == key)


def _response(http, requests_by_key, key):
    response = http.post("/assess", json=requests_by_key[key])
    return response.status_code, response.json()


# --------------------------------------------------------------- scenario suite


def test_scenario_fixtures_replay_against_the_frozen_bundle(record, requests_by_key, http):
    """Every recorded fixture: allow, warn, novelty, known misses, cold start, limited text, several recipients, repeated address, cutoff, failures."""
    outcome = S.replay(record, http, requests_by_key)
    assert [item for item in outcome["fixtures"] if not item["passed"]] == []
    assert outcome["passed"] == len(record["fixtures"]) == len(S.RULES) + len(S.DERIVED)
    kinds = {item["key"] for item in record["fixtures"]}
    assert {"routine_allow", "added_recipient_warn", "legitimate_first_contact_allow", "cold_start_allow", "little_text_allow", "multi_recipient_warn", "duplicate_roles", "threshold_equality_warn"} <= kinds
    assert set(KNOWN_MISSES) <= kinds


def test_fixtures_are_validation_only_and_chosen_by_rule(record, policy):
    frame = S.load_frame(DATA, POLICY.parent)
    picked = S.select_fixtures(frame)
    drafts = {item["key"]: item for item in record["fixtures"] if item["kind"] == "draft"}
    assert {key: drafts[key]["source"]["draft_id"] for key in picked} == picked
    subset_of = subsets_by_draft(DATA)
    stored = pd.read_csv(POLICY.parent / "validation_scores.csv", float_precision="round_trip").set_index("draft_id")
    for item in record["fixtures"]:
        assert subset_of[item["source"]["draft_id"]] == "validation_product_like"
        assert item["source"]["subset"] == "validation_product_like"
    for item in drafts.values():
        row = stored.loc[item["source"]["draft_id"]]
        assert item["source"]["stored_email_risk"] == float(row["email_risk"])
        assert item["source"]["stored_decision"] == ("warn" if row["warned"] else "allow") == item["expected"]["decision"]
        assert abs(item["expected"]["email_risk_score"] - float(row["email_risk"])) <= 1e-12
        assert item["misdirected"] == bool(row["misdirected"])
    assert record["bundle"]["T_warn"] == policy["T_warn"] and record["bundle"]["policy_version"] == policy["policy_version"]
    assert record["bundle"]["blocking_enabled"] is False
    text = json.dumps(record)
    assert not re.search(r"[\w.+-]+@[\w-]+\.example", text) and '"subject"' not in text and '"body"' not in text and '"address"' not in text


def test_known_misses_are_kept_and_labeled(record):
    drafts = [item for item in record["fixtures"] if item["kind"] == "draft"]
    assert {item["key"] for item in drafts if item["known_miss"]} == set(KNOWN_MISSES)
    for item in drafts:
        assert item["known_miss"] == (item["desired"] != item["expected"]["decision"])
        assert item["desired"] == ("warn" if item["misdirected"] else "allow")
    for key, scenario in KNOWN_MISSES.items():
        item = _fixture(record, key)
        assert item["scenario"]["id"] == scenario and item["desired"] == "warn" and item["expected"]["decision"] == "allow"
        assert item["expected"]["email_risk_score"] < record["bundle"]["T_warn"]


def test_the_comparator_detects_a_changed_decision_score_provenance_or_limitation(record, requests_by_key, http):
    def detect(key, change):
        item = _fixture(record, key)
        status, body = _response(http, requests_by_key, key)
        assert S.compare(item["expected"], status, body, reference=requests_by_key[key]["draft_reference"]) == []
        changed = copy.deepcopy(body)
        change(changed)
        return S.compare(item["expected"], status, changed, reference=requests_by_key[key]["draft_reference"])

    def flip(body):
        body["decision"] = "allow" if body["decision"] == "warn" else "warn"

    assert any("decision" in problem for problem in detect("added_recipient_warn", flip))
    assert any("decision" in problem for problem in detect("routine_allow", flip))

    def nudge(amount):
        def apply(body):
            top = max(range(len(body["recipients"])), key=lambda index: body["recipients"][index]["risk_score"])
            body["recipients"][top]["risk_score"] += amount
            body["email_risk_score"] += amount

        return apply

    assert detect("routine_allow", nudge(1e-12)) == []  # a different machine may sum in another order
    assert any("risk score" in problem for problem in detect("routine_allow", nudge(1e-6)))
    for field, value in (("policy_version", "med-policy-v3"), ("model_version", "med-model-v3"), ("feature_spec_version", "med-features-v3"), ("snapshot_id", "other"), ("T_warn", 0.5), ("blocking_enabled", True)):
        assert any("provenance" in problem for problem in detect("routine_allow", lambda body, f=field, v=value: body["provenance"].__setitem__(f, v))), field
    assert any("limitations" in problem for problem in detect("legitimate_first_contact_allow", lambda body: body["recipients"][0].__setitem__("evidence_limitations", [])))
    assert any("limitations" in problem for problem in detect("little_text_allow", lambda body: body["recipients"][0]["evidence_limitations"].append({"code": "LIMITED_TEXT", "text": "changed"})))
    flagged = next(i for i, item in enumerate(_fixture(record, "added_recipient_warn")["expected"]["recipients"]) if item["flagged"])
    assert any("reason codes" in problem for problem in detect("added_recipient_warn", lambda body: body["recipients"][flagged].__setitem__("reason_codes", [])))
    assert any("roles" in problem for problem in detect("routine_allow", lambda body: body["recipients"][0].__setitem__("roles", ["cc"])))
    assert any("flagged" in problem for problem in detect("added_recipient_warn", lambda body: body.__setitem__("flagged_recipients", [])))
    assert any("maximum" in problem for problem in detect("routine_allow", lambda body: body.__setitem__("email_risk_score", body["email_risk_score"] + 1e-3)))
    assert any("explanation" in problem for problem in detect("routine_allow", lambda body: body["explanation"].append("new sentence")))
    # Equality belongs to the higher-intervention band: a score at the cutoff that allows is a defect.
    problems = detect("threshold_equality_warn", lambda body: body.update({"decision": "allow"}))
    assert any("equality must warn" in problem for problem in problems)
    # A malformed body is reported, never raised.
    assert any("malformed" in problem for problem in detect("routine_allow", lambda body: body["recipients"][0].pop("risk_score")))
    assert S.compare(_fixture(record, "routine_allow")["expected"], 200, None) == ["the response is not a JSON object"]


def test_an_unable_to_assess_that_carries_a_decision_is_detected(record, requests_by_key, http):
    item = _fixture(record, "unavailable_unknown_address")
    status, body = _response(http, requests_by_key, "unavailable_unknown_address")
    reference = requests_by_key["unavailable_unknown_address"]["draft_reference"]
    assert S.compare(item["expected"], status, body, reference=reference) == []
    assert body["decision"] is None and body["email_risk_score"] is None and body["recipients"] is None
    allowed = {**body, "decision": "allow", "email_risk_score": 0.0}
    assert any("decision or a risk score" in problem for problem in S.compare(item["expected"], status, allowed, reference=reference))
    scored = {**body, "recipients": [{"address": "x@demo.example", "risk_score": 0.0}]}
    assert any("recipients" in problem for problem in S.compare(item["expected"], status, scored, reference=reference))
    hidden = {**body, "message": "allow"}
    assert any("contains 'allow'" in problem for problem in S.compare(item["expected"], status, {**hidden, "note": "allow"}, reference=reference))
    assert any("HTTP 200" in problem for problem in S.compare(item["expected"], 200, body, reference=reference))
    # An assessed allow where the record expects a failure is flagged on every count.
    assessed_status, assessed = _response(http, requests_by_key, "routine_allow")
    assert S.compare(item["expected"], assessed_status, assessed, reference=reference)
    # The reverse: an unable_to_assess where the record expects an allow.
    expected_allow = _fixture(record, "routine_allow")["expected"]
    assert any("status" in problem for problem in S.compare(expected_allow, status, body, reference=reference))


def test_a_broken_bundle_fails_every_assessed_fixture(record, requests_by_key, tmp_path):
    paths = ApiPaths.from_env(ROOT)
    from dataclasses import replace

    broken = replace(paths, features=tmp_path / "nowhere", feedback=tmp_path / "feedback.jsonl")
    with TestClient(create_app(broken)) as client:
        assert client.get("/ready").status_code == 503
        outcome = S.replay(record, client, requests_by_key)
    assessed = {item["key"] for item in record["fixtures"] if item["expected"]["status"] == "assessed"}
    flagged = {item["key"] for item in outcome["fixtures"] if not item["passed"]}
    assert assessed <= flagged and len(assessed) == 15
    assert all(item["decision"] is None for item in outcome["fixtures"]), "a broken bundle produced a decision"


def test_threshold_equality_through_the_api_and_the_decision_function(record, requests_by_key, http, policy):
    t_warn = policy["T_warn"]
    status, body = _response(http, requests_by_key, "threshold_equality_warn")
    assert status == 200 and body["provenance"]["T_warn"] == t_warn
    assert abs(body["email_risk_score"] - t_warn) <= 1e-12, "the cutoff fixture no longer scores at the cutoff"
    assert body["decision"] == "warn" and body["flagged_recipients"]
    bundle = PolicyBundle(policy=policy, model=None, t_warn=t_warn)

    def decision(*scores):
        frame = pd.DataFrame({"contact_id": [f"c{i}" for i in range(len(scores))], "risk_score": list(scores)})
        return decide(bundle, frame)

    below = float(np.nextafter(t_warn, 0.0))
    assert decision(t_warn)["decision"] == "warn"
    assert decision(below)["decision"] == "allow"
    several = decision(0.1, t_warn, below, 1.0)
    assert several["decision"] == "warn" and several["email_risk"] == 1.0 and several["flagged_recipient_ids"] == ["c1", "c3"]
    assert decision(float("nan"))["status"] == "unable_to_assess" and decision(float("nan"))["decision"] is None


# -------------------------------------------------------------------- data rules


def test_frozen_draft_ids_are_refused_by_the_phase_9_paths(record):
    subset_of = subsets_by_draft(DATA)
    frozen = sorted(draft for draft, subset in subset_of.items() if subset in V.FROZEN_SUBSETS)
    assert frozen
    with pytest.raises(FrozenRowError):
        S.base_requests(DATA, [frozen[0]])
    from med_deploy.latency import workload_ids

    groups = workload_ids(DATA)
    everything = [draft for group in groups.values() for draft in group]
    assert len(everything) == len(set(everything)) == V.WARMUP_CALLS + V.MEASURED_CALLS + V.CONCURRENT_CALLS + V.MAX_INPUT_PROBES
    assert {subset_of[draft] for draft in everything} == {"validation_product_like"}
    assert {subset_of[item["source"]["draft_id"]] for item in record["fixtures"]} == {"validation_product_like"}


def test_no_phase_9_path_opens_a_file_with_frozen_outcomes(tmp_path):
    """The bundle check for each process, run under the audit wrapper, opens only the files that process needs."""
    for scope in ("api", "ui"):
        output = tmp_path / f"{scope}.json"
        completed = subprocess.run(
            [sys.executable, "-m", "med_deploy.audited", str(output), str(ROOT), "--", "med_deploy", "check-bundle", "--scope", scope],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        read = json.loads(output.read_text(encoding="utf-8"))["read"]
        assert not [item for item in read if Path(item).name in V.FORBIDDEN_FILES or Path(item).name.startswith(V.FORBIDDEN_PREFIXES)]
        assert not [item for item in read if re.search(r"med-synth-v2|med-(features|model|policy|api)-v1/", item)], "the superseded baseline was opened"
        assert V.DIGESTS_RECORD.as_posix() in read, "the check did not read the anchored digests"
        assert json.loads(output.read_text(encoding="utf-8"))["written_under_root"] == []


# -------------------------------------------------------------- bundle checking


def _flip_last_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[-1] ^= 0x01
    path.write_bytes(bytes(data))


def test_published_bundle_passes_the_check_and_a_damaged_copy_fails(tmp_path, capsys):
    from med_deploy.cli import main

    features = tmp_path / "features"
    shutil.copytree(ROOT / DEFAULT_PATHS["features"], features)
    _flip_last_byte(features / "features_train.csv")
    damaged = check_bundle("api", root=ROOT, features_dir=features)
    assert damaged["ok"] is False and [c["name"] for c in damaged["checks"] if not c["passed"]] == ["feature_artifact"]
    assert any("Checksum mismatch for features_train.csv" in c["detail"] for c in damaged["checks"])
    missing = check_bundle("api", root=ROOT, policy_path=tmp_path / "policy.json")
    assert missing["ok"] is False and "does not exist" in next(c["detail"] for c in missing["checks"] if c["name"] == "policy_and_model")
    # The screen's scope: a policy that names another version, and a missing validation file.
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["policy_version"] = "med-policy-v3"
    other = tmp_path / "policy-other"
    other.mkdir()
    (other / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    wrong = check_bundle("ui", root=ROOT, policy_path=other / "policy.json")
    assert wrong["ok"] is False and "policy_file" in [c["name"] for c in wrong["checks"] if not c["passed"]]
    # The published bundle passes both scopes, and the command exits non-zero on a failure.
    assert check_bundle("ui", root=ROOT)["ok"] is True
    assert main(["check-bundle", "--scope", "ui", "--root", str(tmp_path)]) == 1
    capsys.readouterr()
    with pytest.raises(RecordExists):
        write_record(ROOT / V.SCENARIO_RECORD, {})


def _policy_tree(tmp_path: Path) -> Path:
    """A root whose data, features, and model are the published ones (symlinks) and whose policy directory is a disposable copy."""
    root = tmp_path / "root"
    (root / "data").mkdir(parents=True)
    (root / "data" / "med-synth-v4").symlink_to(DATA)
    (root / "artifacts").mkdir()
    (root / "artifacts" / "med-features-v2").symlink_to(ROOT / DEFAULT_PATHS["features"])
    (root / "artifacts" / "med-model-v2").mkdir()
    (root / "artifacts" / "med-model-v2" / "model.joblib").symlink_to(ROOT / DEFAULT_PATHS["model"])
    policy_dir = root / "artifacts" / "med-policy-v2"
    policy_dir.mkdir()
    for name in ("policy.json", "validation_evaluation.json", "validation_scores.csv"):
        shutil.copyfile(POLICY.parent / name, policy_dir / name)
    return root


def _passed(result: dict, name: str) -> bool:
    return next(item for item in result["checks"] if item["name"] == name)["passed"]


def test_a_file_changed_without_changing_its_shape_fails_the_digest_check(tmp_path):
    """P9-01: the structural checks accept each of these files after a change that keeps its shape; the anchored digest does not."""
    anchors = json.loads((ROOT / V.DIGESTS_RECORD).read_text(encoding="utf-8"))
    assert set(anchors["files"]) == {f"artifacts/med-policy-v2/{name}" for name in ("policy.json", "validation_evaluation.json", "validation_scores.csv")}
    assert re.fullmatch(r"[0-9a-f]{40}", anchors["verified_against"]["commit"])
    digests = ROOT / V.DIGESTS_RECORD
    root = _policy_tree(tmp_path)
    policy_dir = root / "artifacts" / "med-policy-v2"
    # Control: the copies are the published files.
    assert check_bundle("ui", root=root, digests=digests)["ok"] is True
    assert check_bundle("api", root=root, digests=digests)["ok"] is True

    # An unselected validation score changes; columns and the warning count do not.
    scores = policy_dir / "validation_scores.csv"
    frame = pd.read_csv(scores, float_precision="round_trip")
    quiet = frame.index[~frame["warned"].astype(bool)][0]
    frame.loc[quiet, "email_risk"] = frame.loc[quiet, "email_risk"] / 2
    frame.to_csv(scores, index=False, lineterminator="\n")
    changed = check_bundle("ui", root=root, digests=digests)
    assert _passed(changed, "validation_files") and not _passed(changed, "anchored_digests") and changed["ok"] is False
    assert "validation_scores.csv differs from its anchored digest" in next(c["detail"] for c in changed["checks"] if c["name"] == "anchored_digests")
    shutil.copyfile(POLICY.parent / "validation_scores.csv", scores)

    # A valid evaluation narrative changes; the JSON keeps its keys and stays valid.
    evaluation = policy_dir / "validation_evaluation.json"
    document = json.loads(evaluation.read_text(encoding="utf-8"))

    def reword(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and len(value) > 20:
                    node[key] = value + " (edited)"
                    return True
                if reword(value):
                    return True
        elif isinstance(node, list):
            return any(reword(item) for item in node)
        return False

    assert reword(document)
    evaluation.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    changed = check_bundle("ui", root=root, digests=digests)
    assert _passed(changed, "validation_files") and not _passed(changed, "anchored_digests")
    shutil.copyfile(POLICY.parent / "validation_evaluation.json", evaluation)

    # A different but finite cutoff: both scopes' existing policy checks accept it, the anchor does not.
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["T_warn"] = policy["T_warn"] - 1e-6
    (policy_dir / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    for scope, structural in (("ui", "policy_file"), ("api", "policy_and_model")):
        changed = check_bundle(scope, root=root, digests=digests)
        assert _passed(changed, structural), f"{scope}: the structural check should accept a finite cutoff"
        assert not _passed(changed, "anchored_digests") and changed["ok"] is False
    # An anchor manifest that lacks an entry fails too, rather than passing silently.
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"files": {}}), encoding="utf-8")
    shutil.copyfile(POLICY, policy_dir / "policy.json")
    assert "has no anchored digest" in next(c["detail"] for c in check_bundle("api", root=root, digests=bare)["checks"] if c["name"] == "anchored_digests")


def test_image_contents_must_match_exactly(tmp_path):
    """`--image` demands exactly the files a process reads: no missing file, no extra one, no frozen-outcome file."""
    root = tmp_path / "app"
    for name in ("contacts.csv", "draft_recipients.csv", "drafts.csv", "labels.csv", "split_manifest.csv"):
        (root / "data/med-synth-v4").mkdir(parents=True, exist_ok=True)
        (root / "data/med-synth-v4" / name).symlink_to(DATA / name)
    for name in ("policy.json", "validation_evaluation.json", "validation_scores.csv"):
        (root / "artifacts/med-policy-v2").mkdir(parents=True, exist_ok=True)
        (root / "artifacts/med-policy-v2" / name).symlink_to(POLICY.parent / name)
    manifest = DATA / "dataset_manifest.json"
    digests = ROOT / V.DIGESTS_RECORD
    exact = check_bundle("ui", root=root, image=True, dataset_manifest=manifest, digests=digests)
    assert exact["ok"] is True, exact["checks"]
    extra = root / "artifacts/med-policy-v2" / "test_evaluation.json"
    extra.write_text("{}", encoding="utf-8")
    flagged = check_bundle("ui", root=root, image=True, dataset_manifest=manifest, digests=digests)
    assert flagged["ok"] is False and "frozen-outcome files" in next(c["detail"] for c in flagged["checks"] if c["name"] == "image_contents_exact")
    extra.unlink()
    (root / "data/med-synth-v4/labels.csv").unlink()
    missing = check_bundle("ui", root=root, image=True, dataset_manifest=manifest, digests=digests)
    assert missing["ok"] is False and "labels.csv" in next(c["detail"] for c in missing["checks"] if c["name"] == "image_contents_exact")


# --------------------------------------------------------------------- smoke


def test_smoke_passes_end_to_end_over_http(served):
    before = served.feedback.read_text(encoding="utf-8").count("\n") if served.feedback.exists() else 0
    completed = subprocess.run(
        [sys.executable, "-m", "med_deploy", "smoke", "--api", served.url, "--feedback-file", str(served.feedback), "--root", str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    lines = [line for line in completed.stdout.splitlines() if re.match(r"(ok|FAIL|skip) ", line)]
    assert lines and not [line for line in lines if not line.startswith("ok")]
    names = {line.split()[1].rstrip(":") for line in lines}
    assert {"api_ready", "screen_allow", "screen_warn", "screen_edit_then_reassess", "screen_invalid_input", "screen_unavailable", "screen_feedback", "screen_no_local_scoring", "bundle_files_unchanged"} <= names
    assert served.feedback.read_text(encoding="utf-8").count("\n") == before + 1, "the smoke wrote more than one feedback line"
    assert "@" not in served.feedback.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def failing(tmp_path_factory):
    """A separate process pointed at a disposable copy with no policy file."""
    scratch = tmp_path_factory.mktemp("failing")
    paths = BundlePaths.default(ROOT, scratch / "feedback.jsonl").replace(policy=scratch / "policy.json")
    with api_process(paths, ROOT) as process:
        yield SimpleNamespace(url=process.url, feedback=scratch / "feedback.jsonl")


def test_smoke_reports_a_service_that_is_not_ready(failing):
    result = run_smoke(failing.url, root=ROOT, feedback_file=failing.feedback)
    assert result["passed"] is False
    by_name = {item["name"]: item for item in result["checks"]}
    assert by_name["api_health"]["passed"] is True and by_name["api_ready"]["passed"] is False
    assert by_name["screen"]["passed"] is None and "not verified" in by_name["screen"]["detail"]
    assert not failing.feedback.exists()


def test_the_rehearsal_fails_when_the_ui_container_is_not_healthy(monkeypatch):
    """P9-02: an unreachable or unhealthy screen container fails its step; an exception is never recorded as a pass."""
    from med_deploy import rehearsal as R

    R.require_ui_ok("ok", "now")
    for bad in ("unreachable: ConnectError", "", "starting"):
        with pytest.raises(R.RehearsalError, match="not healthy"):
            R.require_ui_ok(bad, "after it was started")
    backend = R._ContainerBackend.__new__(R._ContainerBackend)
    backend.known_good = {"id": "sha256:unused"}
    backend.ui_port = 1
    monkeypatch.setattr(backend, "_compose", lambda *arguments, **keywords: None)
    monkeypatch.setattr(backend, "ui_health", lambda: "unreachable: ConnectError")
    with pytest.raises(R.RehearsalError, match="not healthy after it was started: unreachable"):
        backend.start_ui(timeout=0)
    steps: list[dict] = []
    R.run_step(steps, "start the review screen container", lambda: {"ui_health": backend.start_ui(timeout=0)})
    R.run_step(steps, "a step that works", lambda: {"detail": 1})
    assert [item["passed"] for item in steps] == [False, True]
    assert "not healthy" in steps[0]["error"] and "ui_health" not in steps[0]
    # The process-level backend has no screen container and says so instead of claiming health.
    process = R._ProcessBackend.__new__(R._ProcessBackend)
    assert process.has_ui_container is False and process.ui_sees_api_ready() is None and process.ui_health() == "not applicable"
    assert backend.has_ui_container is True


def test_a_failing_candidate_process_fails_closed(record, requests_by_key, failing, served):
    outcome = observe_failing(failing.url, record, requests_by_key, failing.feedback, "does not exist")
    assert outcome["ready_http"] == 503 and outcome["health_http"] == 200
    assert outcome["scenario_suite"] == {"assessed_fixtures": 15, "flagged_by_the_suite": 15}
    for probe in outcome["assess"].values():
        assert (probe["http"], probe["status"], probe["category"], probe["decision"], probe["email_risk_score"]) == (503, "unable_to_assess", "unavailable", None, None)
    # The same observation of a healthy service must fail: the check has teeth.
    with pytest.raises(AssertionError):
        observe_failing(served.url, record, requests_by_key, failing.feedback, "does not exist")


# ------------------------------------------------------------------- packaging


# Platform-conditional dependencies are pinned too: Streamlit needs watchdog on Linux but not on macOS,
# so a freeze made on one platform lacks what another installs.
MARKER_ENVIRONMENTS = (
    {"extra": "", "sys_platform": "darwin", "platform_system": "Darwin"},
    {"extra": "", "sys_platform": "linux", "platform_system": "Linux"},
)


def _closure(requirements):
    from importlib import metadata

    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    seen: set[str] = set()
    pending = list(requirements)
    while pending:
        requirement = pending.pop()
        name = str(canonicalize_name(requirement.name))
        if name in seen:
            continue
        seen.add(name)
        try:
            dependencies = metadata.requires(name) or []
        except metadata.PackageNotFoundError:
            continue  # not installed on this platform, for example watchdog on macOS
        for text in dependencies:
            dependency = Requirement(text)
            if dependency.marker is None or any(dependency.marker.evaluate(environment) for environment in MARKER_ENVIRONMENTS):
                pending.append(dependency)
    return seen


def test_constraints_are_exact_portable_and_cover_every_dependency():
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    text = (ROOT / "constraints.txt").read_text(encoding="utf-8")
    pins = parse_constraints(ROOT / "constraints.txt")  # raises on anything that is not an exact name==version
    assert pins and not any(line.lstrip().startswith(("-e ", "git+")) or "://" in line for line in text.splitlines())
    assert "med-data" not in pins and "med_data" not in text
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == V.TESTED_PYTHON
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    extras = project["optional-dependencies"]
    assert set(extras) >= {"dev", "ui", "monitor"}
    requirements = [Requirement(item) for item in project["dependencies"]] + [Requirement(item) for group in extras.values() for item in group]
    names = {str(canonicalize_name(item.name)) for item in requirements}
    tooling = {"pip", "setuptools", "wheel"}
    closure = _closure(requirements) - tooling
    assert names <= set(pins), sorted(names - set(pins))
    assert not (closure - set(pins)), f"not pinned: {sorted(closure - set(pins))}"
    # The core install must stay light: nothing heavy and no UI package in its requirements.
    core = {str(canonicalize_name(Requirement(item).name)) for item in project["dependencies"]}
    assert not core & {"streamlit", "pyarrow", "torch", "tensorflow", "transformers"}
    assert "pyarrow" in pins and "streamlit" in pins  # pinned for the ui extra, never installed by the core install
    assert "watchdog" in pins and "watchdog" in closure, "a Linux-only dependency of Streamlit must be pinned"


def _ignore_includes(path: Path) -> list[str]:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line[1:] for line in lines if line.startswith("!")]


def test_dockerfiles_pin_the_base_and_ship_what_the_process_reads():
    api = (ROOT / "docker/Dockerfile.api").read_text(encoding="utf-8")
    ui = (ROOT / "docker/Dockerfile.ui").read_text(encoding="utf-8")
    base = re.search(r"^FROM (python:(\d+\.\d+\.\d+)-slim-[a-z]+@sha256:[0-9a-f]{64})$", api, re.MULTILINE)
    assert base and base.group(2) == V.TESTED_PYTHON
    assert re.search(rf"^FROM {re.escape(base.group(1))}$", ui, re.MULTILINE), "the two images use different bases"
    api_install = next(line for line in api.splitlines() if "pip install" in line)
    ui_install = next(line for line in ui.splitlines() if "pip install" in line)
    assert "-c constraints.txt" in api_install and "--only-binary=:all:" in api_install and "[ui]" not in api_install and "streamlit" not in api
    assert '".[ui]"' in ui_install and "-c constraints.txt" in ui_install and "--only-binary=:all:" in ui_install
    for text in (api, ui):
        assert "USER 10001" in text and "HEALTHCHECK" in text and "check-bundle" in text and "--image" in text
        for forbidden in ("test_evaluation", "project" + "_context", ".git", "var/", "med-synth-v2", "med-features-v1", "med-model-v1", "med-policy-v1", "features_test_", "evaluate-test", "med_models run", "med_features build"):
            assert forbidden not in "\n".join(line for line in text.splitlines() if line.startswith(("COPY", "RUN"))), forbidden
    assert "/ready" in next(line for line in api.splitlines() if "urlopen" in line)
    assert "med-model-v2" not in ui and "med-features-v2" not in ui, "the screen image must not hold a model or features"
    for name in ("docker/Dockerfile.api.dockerignore", "docker/Dockerfile.ui.dockerignore"):
        lines = [line.strip() for line in (ROOT / name).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
        assert lines[0] == "*", f"{name} is not default-deny"
    # The include lists are exactly what the measured processes read (the screen also gets the dataset manifest, bind-mounted for the build check only).
    reads = json.loads((ROOT / V.READS_RECORD).read_text(encoding="utf-8"))["processes"]
    api_includes = _ignore_includes(ROOT / "docker/Dockerfile.api.dockerignore")
    ui_includes = _ignore_includes(ROOT / "docker/Dockerfile.ui.dockerignore")

    def covered(path, includes):
        return any(path == item or path.startswith(item.rstrip("/") + "/") for item in includes)

    assert all(covered(path, api_includes) for path in reads["api"]["read"])
    anchor = "artifacts/med-deploy-v1/bundle_digests.json"
    assert {item for item in api_includes if item.startswith(("data/", "artifacts/"))} == {"data/med-synth-v4", "artifacts/med-features-v2", "artifacts/med-model-v2/model.joblib", "artifacts/med-policy-v2/policy.json", anchor}
    for text in (api, ui):
        assert f"--mount=type=bind,source={anchor}" in text and "--digests /tmp/bundle_digests.json" in text, "the image build must check the anchored digests"
        assert "COPY " + anchor not in text, "the anchor is bind-mounted for the build check and not copied into the image"
    for directory in ("data/med-synth-v4", "artifacts/med-features-v2"):
        on_disk = {p.relative_to(ROOT).as_posix() for p in (ROOT / directory).iterdir() if p.is_file()}
        assert on_disk == {path for path in reads["api"]["read"] if path.startswith(directory + "/")}, f"{directory} holds a file the API does not read"
    ui_files = {item for item in ui_includes if item.startswith(("data/", "artifacts/"))}
    assert ui_files == set(reads["ui"]["read"]) | {"data/med-synth-v4/dataset_manifest.json", anchor}
    # The images hold only the deployment-check modules they run (check-bundle, environment). Those modules import nothing
    # else from the package at module level, so the others can stay out and an edit to one never changes an image.
    shipped = {"__init__.py", "__main__.py", "bundle.py", "cli.py", "environment.py", "version.py"}
    for includes in (api_includes, ui_includes):
        assert {item.rsplit("/", 1)[1] for item in includes if item.startswith("src/med_deploy/")} == shipped
    for name in shipped:
        tree = ast.parse((ROOT / "src/med_deploy" / name).read_text(encoding="utf-8"))
        for node in tree.body:  # module level only; the CLI imports its other modules inside its command functions
            modules = [node.module] if isinstance(node, ast.ImportFrom) and node.module else [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
            for module in modules:
                if module.startswith("med_deploy."):
                    assert module.split(".")[1] + ".py" in shipped, f"{name} imports {module} at module level, which is not shipped"
            if isinstance(node, ast.ImportFrom) and node.module == "med_deploy":
                assert all(alias.name + ".py" in shipped for alias in node.names), f"{name}: from med_deploy import {[a.name for a in node.names]}"


def test_the_shipped_modules_run_without_the_others():
    """The images hold six of the package's modules. `check-bundle` and `environment` must run with every other one blocked."""
    probe = (
        "import importlib.abc, sys\n"
        "SHIPPED = {'__init__', '__main__', 'bundle', 'cli', 'environment', 'version'}\n"
        "class Block(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path, target=None):\n"
        "        if name.startswith('med_deploy.') and name.split('.')[1] not in SHIPPED:\n"
        "            raise ImportError('not shipped in the images: ' + name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "from med_deploy.cli import main\n"
        "import contextlib, io\n"
        "with contextlib.redirect_stdout(io.StringIO()):\n"
        "    codes = [main(['check-bundle', '--scope', 'ui']), main(['environment'])]\n"
        "print(codes, sorted(m for m in sys.modules if m.startswith('med_deploy.')))\n"
    )
    completed = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr[-600:]
    assert completed.stdout.startswith("[0, 0]"), completed.stdout
    assert not {"med_deploy.records", "med_deploy.report", "med_deploy.smoke", "med_deploy.scenarios"} & set(completed.stdout.split("[", 2)[2].split("]")[0].replace("'", "").replace(" ", "").split(","))


def test_compose_publishes_on_loopback_and_hardens_the_containers():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    ports = re.findall(r'^\s+- "([^"]*:\d+)"', text, re.MULTILINE)
    assert ports and all(item.startswith("127.0.0.1:") for item in ports)
    assert "0.0.0.0" not in re.sub(r"#.*", "", text)
    assert "read_only: true" in text and "cap_drop:" in text and "ALL" in text and "no-new-privileges:true" in text
    code = re.sub(r"#.*", "", text)
    assert code.count("pull_policy: never") == 2 and "privileged" not in code and "network_mode" not in code
    volumes = re.findall(r"^\s+- (\S+:/\S+)$", text, re.MULTILINE)
    assert volumes == ["${MED_FEEDBACK_DIR:-./var/demo}:/feedback"], "the feedback folder must be the only mount"
    assert "condition: service_healthy" in text and "cpus: 2" in text and "mem_limit: 2g" in text


def test_ci_workflow_runs_the_compact_checks_and_never_retrains():
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for _, command in CI_STEPS:
        assert f"run: {command}" in code, command
    assert 'python-version: "3.11.14"' in code and "cache-dependency-path: constraints.txt" in code
    assert "-c constraints.txt" in code and '-m "not slow"' in code and "check-bundle --scope api" in code and "check-bundle --scope ui" in code
    for forbidden in FORBIDDEN_IN_CI:
        assert forbidden not in code, forbidden
    assert "pull_request_target" not in code and "contents: read" in code and "secrets." not in code


def test_slow_marker_is_registered_and_used():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert any(item.startswith("slow:") for item in project["tool"]["pytest"]["ini_options"]["markers"])
    marked = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef) and any(ast.unparse(item) == "pytest.mark.slow" for item in node.decorator_list):
                marked.add(node.name)
    assert marked == SLOW_TESTS


def test_coverage_map_points_at_real_tests_in_the_right_layer():
    for topic, tests in COVERAGE.items():
        assert tests, topic
        for node, layer in tests:
            file, name = node.split("::")
            tree = ast.parse((ROOT / file).read_text(encoding="utf-8"))
            found = [item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name]
            assert len(found) == 1, node
            slow = any(ast.unparse(item) == "pytest.mark.slow" for item in found[0].decorator_list)
            assert slow == (layer == "release"), f"{node} is {'slow' if slow else 'not slow'} but mapped to {layer}"


def test_ui_binds_loopback_by_default(monkeypatch):
    import med_ui.cli as cli

    commands = []
    monkeypatch.setattr(cli.subprocess, "call", lambda command, env=None: commands.append(command) or 0)
    cli.main(["serve"])
    cli.main(["serve", "--host", "0.0.0.0", "--port", "8601"])
    default, explicit = commands
    assert default[default.index("--server.address") + 1] == "127.0.0.1"
    assert explicit[explicit.index("--server.address") + 1] == "0.0.0.0" and explicit[explicit.index("--server.port") + 1] == "8601"


def test_package_version_is_bumped_and_the_frozen_bundle_is_not(policy):
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert tuple(int(part) for part in project["version"].split(".")) >= (0, 9, 0)
    assert project["scripts"]["med-deploy"] == "med_deploy.cli:main"
    assert (policy["policy_version"], policy["model_version"], policy["feature_spec_version"], policy["dataset_version"]) == ("med-policy-v2", "med-model-v2", "med-features-v2", "med-synth-v4")
    assert API_CONTRACT_VERSION == "med-api-v1"
    assert policy["T_warn"] == 0.9996767050340489 and policy["blocking_enabled"] is False and policy["T_block"] is None
    assert policy["scores_are"] == "risk_scores" and policy["calibration"] == "not_fit"


def test_every_command_has_a_handler_and_record_run_keeps_its_arguments(tmp_path, capsys):
    import argparse

    from med_deploy import cli

    parser = cli.build_parser()
    choices = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction)).choices
    assert {"check-bundle", "smoke", "latency", "rehearse", "record-run", "report", "clean-checkout", "mutation-check"} <= set(choices)
    assert all(callable(getattr(cli, "_" + name.replace("-", "_"), None)) for name in choices), "a command has no handler"
    args = parser.parse_args(["record-run", "--runs", "r.json", "--note", "n", "full_pytest", "--", "python", "-m", "pytest", "-m", "not slow"])
    assert (args.command, args.name, str(args.runs), args.note, args.argv) == ("record-run", "full_pytest", "r.json", "n", ["python", "-m", "pytest", "-m", "not slow"])
    runs = tmp_path / "runs.json"
    assert cli.main(["record-run", "--runs", str(runs), "demo", "--", "python", "-c", "print('3 passed, 1 deselected in 0.1s')"]) == 0
    run = json.loads(runs.read_text(encoding="utf-8"))["runs"]["demo"]
    assert (run["exit_code"], run["passed"], run["deselected"]) == (0, 3, 1) and run["command"].startswith("python -c")
    assert cli.main(["record-run", "--runs", str(runs), "failing", "--", "python", "-c", "import sys; print('1 failed in 0.1s'); sys.exit(1)"]) == 1
    assert json.loads(runs.read_text(encoding="utf-8"))["runs"]["failing"]["failed"] == 1
    capsys.readouterr()


def test_environment_check_fails_on_a_different_version(tmp_path, capsys):
    from med_deploy.cli import main

    pins = tmp_path / "constraints.txt"
    pins.write_text("numpy==0.0.1\n", encoding="utf-8")
    assert main(["environment", "--constraints", str(pins), "--check"]) == 1
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["constraints"]["version_differs"]["numpy"]["pinned"] == "0.0.1" and report["matches_constraints"] is False
    with pytest.raises(ValueError, match="exact name==version"):
        parse_constraints(_write(tmp_path / "loose.txt", "numpy>=1\n"))
    with pytest.raises(ValueError, match="must not be pinned"):
        parse_constraints(_write(tmp_path / "project.txt", "med-data==0.9.0\n"))


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- stored records


def _read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_stored_records_are_consistent(policy):
    served = {key: policy[key] for key in ("model_version", "feature_spec_version", "policy_version", "T_warn")}
    bundle = {scope: _read(path) for scope, path in V.BUNDLE_RECORDS.items()}
    assert all(item["ok"] for item in bundle.values()) and bundle["api"]["bundle"]["T_warn"] == policy["T_warn"]
    assert all("anchored_digests" in [check["name"] for check in item["checks"] if check["passed"]] for item in bundle.values())
    reads, images = _read(V.READS_RECORD), _read(V.IMAGES_RECORD)
    for name in ("api", "ui"):
        process = reads["processes"][name]
        assert process["matches_expected"] and process["written_under_root"] == [] and process["read"] == process["expected_by_bundle_check"]
        assert sorted(images["images"][name]["files_in_app"]) == process["read"], f"the {name} image does not hold exactly what the process reads"
        item = images["images"][name]
        assert item["environment"]["matches_constraints"] and item["environment"]["python_matches_tested"] and item["identity"]["user"] == "10001"
        probes = item["write_probes"]
        assert "PermissionError" in probes["as_the_container_user"]["outcome"] and "Read-only" in probes["root_on_a_read_only_filesystem"]["outcome"]
    assert images["images"]["api"]["environment"]["pyarrow_importable"] is False and images["images"]["ui"]["environment"]["pyarrow_importable"] is True
    assert images["images"]["api"]["base_image"] == images["images"]["ui"]["base_image"]
    latency = _read(V.LATENCY_RECORD)
    ac05 = latency["ac05"]
    assert ac05["requests"] >= V.MEASURED_CALLS and ac05["failures"] == 0 and latency["workload"]["warmup_calls"] == V.WARMUP_CALLS
    assert ac05["result"] == ("met" if ac05["client_p95_ms"] < V.TARGET_P95_MS else "not met")
    assert latency["environment_of_measured_process"]["pyarrow_importable"] is False
    assert latency["target"]["image"]["id"] == images["images"]["api"]["identity"]["id"], "the measured image is not the recorded image"
    assert latency["served"]["T_warn"] == policy["T_warn"] and ac05["parity_with_stored_validation_scores"]["decisions_matching"] == ac05["requests"]
    assert _read(V.LATENCY_PATH)["measured_calls"] == 4000, "the Phase 6 latency record must stay as it was"
    for mode, path in V.SMOKE_RECORDS.items():
        smoke = _read(path)
        assert smoke["passed"] and smoke["target"] == mode and smoke["feedback_checked"] and all(item["passed"] is not False for item in smoke["checks"])
        assert {key: smoke["served"][key] for key in served} == served
    assert _read(V.SMOKE_RECORDS["container"])["ui_url"] is not None
    for mode, path in V.REHEARSAL_RECORDS.items():
        rehearsal = _read(path)
        assert rehearsal["passed"] and rehearsal["mode"] == mode and rehearsal["published_bundle_files_unchanged"] and rehearsal["identities"]["known_good_unchanged"]
        failing = [step for step in rehearsal["steps"] if step.get("deployable") not in (None, "known_good")]
        assert len(failing) == 2 and all(step["ready_http"] == 503 and step["health_command_exit_code"] != 0 and step["review_screen"]["assessment_disabled"] for step in failing)
        healthy = [step for step in rehearsal["steps"] if step.get("deployable") == "known_good"]
        assert len(healthy) == 3 and all(step["scenario_fixtures"]["failed"] == 0 and step["served"]["T_warn"] == policy["T_warn"] for step in healthy)
    container = _read(V.REHEARSAL_RECORDS["container"])
    assert container["identities"]["known_good"]["id"] == images["images"]["api"]["identity"]["id"]
    seen = {step["step"]: step for step in container["steps"] if "ui_container_sees_ready_http" in step}
    failing_steps = [step for step in container["steps"] if step.get("deployable") not in (None, "known_good")]
    restores = [step for step in container["steps"] if step["step"].startswith("restore")]
    assert all(step["ui_container_sees_ready_http"] == 503 and step["ui_process_health"] == "ok" for step in failing_steps)
    assert all(step["ui_container_sees_ready_http"] == 200 and step["ui_health"] == "ok" for step in restores)
    assert len(seen) == 5 and [step["ui_health"] for step in container["steps"] if step["step"].startswith(("start the review", "review screen container stayed"))] == ["ok", "ok"]
    assert all(step["review_screen"]["checked_by"].startswith("the screen script") for step in failing_steps)
    assert any("not opened in a browser" in limit for limit in container["limits"])
    process_record = _read(V.REHEARSAL_RECORDS["process"])
    assert not [step for step in process_record["steps"] if "ui_container_sees_ready_http" in step and step["ui_container_sees_ready_http"] is not None]
    assert {step["image_id"] for step in container["steps"] if step.get("deployable") == "known_good"} == {container["identities"]["known_good"]["id"]}
    mutations = _read(V.MUTATION_RECORD)
    assert mutations["control_passed"] and mutations["all_detected"] and len(mutations["mutations"]) >= 7
    assert {"equality_allows", "evidence_limitations_dropped", "failure_carries_an_allow", "cutoff_misreported", "history_rule_changed", "score_shifted"} <= {item["mutation"] for item in mutations["mutations"]}
    browser = _read(V.BROWSER_RECORD)
    assert browser["passed"] and all(browser["matches"].values())
    # The run log is written by the runs that execute this test, so it is checked for structure only; the report shows a failed run as FAILED.
    runs = _read(V.RUNS_RECORD)["runs"] if (ROOT / V.RUNS_RECORD).exists() else {}
    for name, run in runs.items():
        assert run["name"] == name and run["command"] and isinstance(run["exit_code"], int) and run["date_utc"].endswith("Z") and run["seconds"] >= 0
    if (ROOT / V.REBUILD_RECORD).exists():
        assert _read(V.REBUILD_RECORD)["published_files_unchanged"] is True


def test_clean_checkout_record_is_consistent():
    """The dry run of the CI steps writes this record after it runs the fast suite, so the copy it runs in has no record yet."""
    path = ROOT / V.CLEAN_CHECKOUT_RECORD
    if not path.exists():
        pytest.skip("written by `python -m med_deploy clean-checkout`, which runs this suite in a scratch copy first")
    clean = _read(V.CLEAN_CHECKOUT_RECORD)
    assert clean["passed"] and [step["command"] for step in clean["steps"]] == [command for _, command in CI_STEPS]
    assert all(step["exit_code"] == 0 for step in clean["steps"])
    assert clean["venv_python"] == V.TESTED_PYTHON and clean["environment_of_the_fresh_venv"]["matches_constraints"]


def test_documents_regenerate_exactly_from_the_records():
    for name, text in documents(ROOT).items():
        assert (ROOT / V.DOCS_DIR / name).read_text(encoding="utf-8") == text.rstrip("\n") + "\n", f"{name} is not what the records generate; run python -m med_deploy report"
