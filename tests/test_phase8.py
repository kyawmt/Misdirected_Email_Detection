"""Phase 8 monitoring: references, drift gating, alerts, reviewed feedback, bundle refusal, and data boundaries.

The stored records under artifacts/med-monitor-v1 are produced by
`python -m med_monitor build-reference | replay | feedback | bundle-checks`.
These tests check those records against the code that produced them, and run
small live replays through one shared in-process API.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from med_api.app import create_app
from med_api.context import ApiPaths
from med_data.calendar import FROZEN_SUBSETS
from med_features.schema import FEATURE_COLUMNS
from med_monitor import alerts, bundles, drift, experiment, observations as obs, report, stream
from med_monitor import data as mdata
from med_monitor import feedback as fb
from med_monitor import reference as ref
from med_monitor import replay as rp
from med_monitor import version as V
from med_policy.decision import load_bundle
from med_policy.version import PolicyError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / V.DATA_DIR
FEATURES = ROOT / V.FEATURES_DIR
POLICY_PATH = ROOT / V.POLICY_PATH
POLICY_DIR = ROOT / V.POLICY_DIR
MODEL_PATH = ROOT / V.MODEL_PATH
STORED = ROOT / V.ARTIFACT_DIR
DOCS = ROOT / V.DOCS_DIR
SRC = ROOT / "src" / "med_monitor"


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def stored():
    return {name: json.loads((STORED / f"{name}.json").read_text(encoding="utf-8")) for name in ("reference", "replay_plan", "replay", "feedback_review", "bundle_checks")}


@pytest.fixture(scope="module")
def policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def structure():
    subset_of, keep = mdata.validation_ids(DATA)
    return subset_of, mdata.load_structure(DATA, keep)


@pytest.fixture(scope="module")
def plan(structure):
    return stream.build_plan(structure[1])


@pytest.fixture(scope="module")
def features():
    return pd.concat([mdata.read_features(FEATURES / f"features_{name}.csv") for name in V.VALIDATION_SUBSETS], ignore_index=True)


@pytest.fixture(scope="module")
def by_draft(features):
    return {draft_id: frame for draft_id, frame in features.groupby("draft_id", sort=False)}


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    paths = replace(ApiPaths.from_env(ROOT), feedback=tmp_path_factory.mktemp("feedback") / "feedback.jsonl")
    with TestClient(create_app(paths)) as client:
        yield client


def window_frame(window: dict, by_draft: dict) -> pd.DataFrame:
    """The recipient rows of one planned window, one occurrence id per email."""
    parts = [by_draft[draft_id].assign(occurrence=window["window"] * 100_000 + position) for position, draft_id in enumerate(window["draft_ids"])]
    return pd.concat(parts, ignore_index=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FileSpy:
    """Record the name of every file the code under test opens or reads."""

    def __init__(self, monkeypatch):
        self.names: list[str] = []
        record = self.names.append
        original_open, original_read_text, original_read_bytes = Path.open, Path.read_text, Path.read_bytes
        original_read_csv = pd.read_csv

        def spy_open(path, *args, **kwargs):
            record(Path(path).name)
            return original_open(path, *args, **kwargs)

        def spy_read_text(path, *args, **kwargs):
            record(Path(path).name)
            return original_read_text(path, *args, **kwargs)

        def spy_read_bytes(path, *args, **kwargs):
            record(Path(path).name)
            return original_read_bytes(path, *args, **kwargs)

        def spy_read_csv(path, *args, **kwargs):
            record(Path(path).name)
            return original_read_csv(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", spy_open)
        monkeypatch.setattr(Path, "read_text", spy_read_text)
        monkeypatch.setattr(Path, "read_bytes", spy_read_bytes)
        monkeypatch.setattr(pd, "read_csv", spy_read_csv)


# ------------------------------------------------- data boundary (frozen rows)


def test_no_monitoring_command_reads_a_frozen_test_row(monkeypatch, plan, structure):
    subset_of, _ = structure
    frozen = {draft for draft, subset in subset_of.items() if subset in FROZEN_SUBSETS}
    assert frozen
    kept: list[tuple[str, set[str]]] = []
    original_stream = mdata.stream_rows

    def spy_stream(path, keep_ids, **kwargs):
        assert not (set(keep_ids) & frozen), f"{Path(path).name} was asked for a frozen id"
        frame = original_stream(path, keep_ids, **kwargs)
        kept.append((Path(path).name, set(frame["draft_id"]) if "draft_id" in frame else set()))
        return frame

    monkeypatch.setattr(mdata, "stream_rows", spy_stream)
    spy = FileSpy(monkeypatch)
    ids = sorted(stream.plan_ids(plan))[:25]
    mdata.load_structure(DATA, mdata.validation_ids(DATA)[1])
    mdata.load_requests(DATA, ids)
    mdata.read_labels(DATA, set(ids))
    mdata.read_reviewer_feedback(DATA)
    mdata.sender_population(DATA, set(ids))
    ref.build_all(FEATURES, POLICY_DIR, ROOT / V.LATENCY_PATH)
    for name, seen in kept:
        assert not (seen & frozen), name
    read = set(spy.names)
    allowed = {
        "split_manifest.csv", "drafts.csv", "draft_recipients.csv", "labels.csv", "contacts.csv", "reviewer_feedback.csv",
        "features_train.csv", "artifact_manifest.json", "policy.json", "test_evaluation.json", "latency.json",
    }
    assert read <= allowed, sorted(read - allowed)
    assert not [name for name in read if name.startswith("features_test")]
    # Draft-keyed tables are streamed, never read whole.
    assert not {"drafts.csv", "draft_recipients.csv", "labels.csv", "reviewer_feedback.csv"} & {
        name for name in spy.names if name not in {item[0] for item in kept}
    }
    assert not list(FEATURES.glob("features_test_*"))


def test_frozen_and_non_validation_drafts_are_refused(structure, plan):
    subset_of, _ = structure
    frozen = next(draft for draft, subset in subset_of.items() if subset == "test_product_like")
    train = next(draft for draft, subset in subset_of.items() if subset == "train")
    for call in (mdata.load_requests, mdata.read_labels, mdata.sender_population):
        argument = [frozen] if call is mdata.load_requests else {frozen}
        with pytest.raises(mdata.FrozenRowError):
            call(DATA, argument)
    with pytest.raises(mdata.DataError):
        mdata.read_labels(DATA, {train})
    bad = copy.deepcopy(plan)
    bad["windows"][0]["draft_ids"][0] = frozen
    with pytest.raises(mdata.FrozenRowError):
        stream.check_plan(bad, subset_of)
    frame = mdata.read_reviewer_feedback(DATA)
    assert not (set(frame["draft_id"]) & {draft for draft, subset in subset_of.items() if subset in FROZEN_SUBSETS})
    assert set(frame["subset"]) <= {"train", "validation_product_like", "validation_diagnostic"}


def test_only_the_recorded_test_aggregate_is_quoted(stored):
    quoted = stored["reference"]["recorded_test_pass"]
    assert set(quoted) == {"subset", "emails", "misdirected", "legitimate", "warned_mistakes", "false_interventions", "recall", "recall_interval_exact", "note"}
    assert all(not isinstance(value, (dict, list)) or key == "recall_interval_exact" for key, value in quoted.items())
    assert quoted == ref.recorded_test_pass(POLICY_DIR)


# ------------------------------------------------------------- the reference


def test_drift_reference_uses_train_only(monkeypatch, stored, tmp_path):
    spy = FileSpy(monkeypatch)
    rebuilt = ref.build_reference(FEATURES)
    assert {name for name in spy.names if name.startswith("features_")} == {"features_train.csv"}
    monkeypatch.undo()
    manifest = json.loads((FEATURES / "artifact_manifest.json").read_text(encoding="utf-8"))
    fit = json.loads((FEATURES / "fit_metadata.json").read_text(encoding="utf-8"))
    reference = stored["reference"]
    assert reference["subset"] == "train" == V.REFERENCE_SUBSET
    assert reference["source"]["file"] == "features_train.csv"
    assert reference["source"]["sha256"] == manifest["files"]["features_train.csv"]["sha256"] == sha256(FEATURES / "features_train.csv")
    assert reference["rows"] == fit["row_counts"]["train"]
    for key in ("subset", "source", "rows", "drafts", "features"):
        assert rebuilt[key] == reference[key], key
    # Changing a validation feature file cannot change the reference; changing the train file is refused.
    copy_dir = tmp_path / "features"
    copy_dir.mkdir()
    for path in FEATURES.iterdir():
        (copy_dir / path.name).write_bytes(path.read_bytes())
    assert ref.build_reference(copy_dir)["features"] == reference["features"]
    (copy_dir / "features_validation_product_like.csv").write_bytes(b"garbage")
    assert ref.build_reference(copy_dir)["features"] == reference["features"]
    (copy_dir / "features_train.csv").write_bytes((FEATURES / "features_train.csv").read_bytes() + b"\n")
    with pytest.raises(ref.ReferenceError, match="Checksum"):
        ref.build_reference(copy_dir)


def test_feature_classification_matches_the_catalog(stored):
    assert set(V.CUMULATIVE_FEATURES) <= set(FEATURE_COLUMNS) and set(V.DRAFT_LEVEL_FEATURES) <= set(FEATURE_COLUMNS)
    train = mdata.read_features(FEATURES / "features_train.csv")
    per_draft = train.groupby("draft_id")
    for name in V.DRAFT_LEVEL_FEATURES:
        assert (per_draft[name].nunique() <= 1).all(), name
    reference = stored["reference"]["features"]
    assert {name for name, spec in reference.items() if spec["cumulative"]} == set(V.CUMULATIVE_FEATURES)
    assert {name for name, spec in reference.items() if spec["unit"] == "email"} == set(V.DRAFT_LEVEL_FEATURES)
    assert reference["addressed_recipient_count"]["rows"] == stored["reference"]["drafts"]
    # The unit of analysis: draft-level features once per email, the rest once per recipient row.
    assert len(ref.unit_values(train, "addressed_recipient_count", "draft_id")) == train["draft_id"].nunique() < len(train)
    assert len(ref.unit_values(train, "recipient_novel_to_sender", "draft_id")) == len(train)
    # A cumulative feature really does leave the train range on later mail.
    later = mdata.read_features(FEATURES / "features_validation_product_like.csv")
    assert (later["sender_history_span_days"] > train["sender_history_span_days"].max()).mean() > 0.9


# --------------------------------------------------------------- input drift


def test_no_drift_is_reported_below_the_minimum_sample(stored, plan, by_draft):
    reference = stored["reference"]
    window = plan["windows"][-1]
    full = window_frame(window, by_draft)
    assert drift.input_drift(reference, full)["status"] != drift.INSUFFICIENT
    few_rows = full.head(V.MIN_ROWS_INPUT_DRIFT - 1)
    result = drift.input_drift(reference, few_rows)
    assert result["status"] == drift.INSUFFICIENT and result["features"] == [] and result["alert"] == [] and result["watch"] == []
    assert "No input-drift statement" in result["statement"]
    # Enough rows but too few emails.
    repeated = pd.concat([full.iloc[[0]].assign(occurrence=1)] * (V.MIN_ROWS_INPUT_DRIFT + 5), ignore_index=True)
    assert drift.input_drift(reference, repeated)["status"] == drift.INSUFFICIENT
    # Rates and decision-rate statements refuse small samples.
    small = drift.rate_finding("x", {"k": 5, "n": 100}, {"k": 50, "n": 100}, alternative="greater", min_n=200)
    assert small["status"] == drift.INSUFFICIENT and small["p_value"] is None
    below = drift.decision_rate_change({"k": 6, "n": V.MIN_EMAILS_DECISION_RATE - 1}, {"k": 60, "n": V.MIN_EMAILS_DECISION_RATE})
    assert below["status"] == drift.INSUFFICIENT and below["p_value"] is None
    enough = drift.decision_rate_change({"k": 6, "n": V.MIN_EMAILS_DECISION_RATE}, {"k": 60, "n": V.MIN_EMAILS_DECISION_RATE})
    assert enough["status"] == drift.ALERT and enough["p_value"] < V.RATE_ALPHA
    side = {"positives_confirmed": V.MIN_REVIEWED_POSITIVES - 1, "recall": {"estimate": 0.5, "low": 0.4, "high": 0.6}}
    far = {"positives_confirmed": V.MIN_REVIEWED_POSITIVES, "recall": {"estimate": 0.05, "low": 0.0, "high": 0.1}}
    assert drift.performance_change(side, far)["status"] == drift.INSUFFICIENT
    assert drift.performance_change({**side, "positives_confirmed": V.MIN_REVIEWED_POSITIVES}, far)["status"] == drift.ALERT


def test_input_drift_rules(stored, plan, by_draft):
    reference = stored["reference"]
    train = mdata.read_features(FEATURES / "features_train.csv")
    rng = np.random.default_rng(7)
    # Whole emails, as a real window is formed; sampling recipient rows would oversample multi-recipient emails.
    sampled = train["draft_id"].drop_duplicates().sample(n=700, random_state=7)
    picked = train[train["draft_id"].isin(sampled)].reset_index(drop=True)
    picked["occurrence"] = picked["draft_id"]
    assert drift.input_drift(reference, picked)["alert"] == []

    shifted = picked.copy()
    hits = rng.choice(len(shifted), size=int(0.25 * len(shifted)), replace=False)
    shifted.loc[hits, ["recipient_novel_to_sender"]] = 1
    result = drift.input_drift(reference, shifted)
    assert "recipient_novel_to_sender" in result["alert"]

    tiny = picked.copy()
    tiny.loc[tiny.index[:2], "recipient_novel_to_sender"] = 1
    assert "recipient_novel_to_sender" not in drift.input_drift(reference, tiny)["alert"]

    emails = picked["occurrence"].drop_duplicates()
    unseen = picked.copy()
    unseen.loc[unseen["occurrence"].isin(emails.head(2)), "draft_text_empty"] = 1
    assert drift.input_drift(reference, unseen)["features"][FEATURE_COLUMNS.index("draft_text_empty")]["status"] == drift.WATCH
    unseen.loc[unseen["occurrence"].isin(emails.head(60)), "draft_text_empty"] = 1
    assert "draft_text_empty" in drift.input_drift(reference, unseen)["alert"]

    grown = picked.copy()
    grown["sender_outbound_count"] = grown["sender_outbound_count"] * 5
    result = drift.input_drift(reference, grown)
    item = next(row for row in result["features"] if row["feature"] == "sender_outbound_count")
    assert item["status"] == drift.STRUCTURAL and item["psi"] is None and item["share_outside_train_range"] > 0.5
    assert "sender_outbound_count" not in result["alert"] and "sender_outbound_count" in result["structural"]

    # Draft-level features count each email once, not once per recipient row.
    real = window_frame(plan["windows"][-1], by_draft)
    counted = next(row for row in drift.input_drift(reference, real)["features"] if row["feature"] == "addressed_recipient_count")
    assert counted["n"] == real["occurrence"].nunique() < len(real)


def test_input_drift_decision_rate_and_performance_are_separate_findings(stored):
    reference, replay_record, review = stored["reference"], stored["replay"], stored["feedback_review"]
    key = alerts.expected_version_key(json.loads(POLICY_PATH.read_text(encoding="utf-8")))
    base = alerts.evaluate(replay_record, reference, key, review)
    block = {item["id"]: item for item in base["block"]["checks"]}
    assert {block[name]["family"] for name in ("input_drift", "decision_rate_change", "confirmed_performance_change")} == {"input_drift", "decision_rate", "performance"}

    def statuses(evaluated):
        checks = {item["id"]: item["status"] for item in evaluated["windows"][8]["checks"]}
        checks["performance"] = {item["id"]: item["status"] for item in evaluated["block"]["checks"]}["confirmed_performance_change"]
        return checks

    original = statuses(base)
    # More warnings change the decision-rate finding and not the input-drift or performance findings.
    warned = copy.deepcopy(replay_record)
    for role in ("reference", "current"):
        warned["blocks"][role]["summary"]["warnings"] += 60 if role == "current" else 0
    changed = alerts.evaluate(warned, reference, key, review)
    assert {item["id"]: item["status"] for item in changed["block"]["checks"]}["decision_rate_change"] == drift.ALERT
    assert statuses(changed)["input_drift"] == original["input_drift"] and statuses(changed)["performance"] == original["performance"]
    # A different input-drift result changes the input-drift finding and not the other two.
    moved = copy.deepcopy(replay_record)
    moved["windows"][7]["input_drift"]["status"] = drift.NO_DRIFT
    moved["windows"][7]["input_drift"]["alert"] = []
    after = statuses(alerts.evaluate(moved, reference, key, review))
    assert after["input_drift"] == drift.NO_DRIFT and after["decision_rate_change"] == original["decision_rate_change"] and after["performance"] == original["performance"]
    # Reviewed labels alone move the performance finding.
    reviewed = copy.deepcopy(review)
    horizon = str(reviewed["efficacy"]["comparison_horizon_days"])
    for side in reviewed["efficacy"]["by_horizon"][horizon].values():
        side["positives_confirmed"] = V.MIN_REVIEWED_POSITIVES
    reviewed["efficacy"]["by_horizon"][horizon]["reference"]["recall"] = {"estimate": 0.9, "low": 0.8, "high": 1.0}
    reviewed["efficacy"]["by_horizon"][horizon]["current"]["recall"] = {"estimate": 0.2, "low": 0.1, "high": 0.3}
    third = alerts.evaluate(replay_record, reference, key, reviewed)
    assert statuses(third)["performance"] == drift.ALERT
    assert {k: v for k, v in statuses(third).items() if k != "performance"} == {k: v for k, v in original.items() if k != "performance"}
    assert alerts.evaluate(replay_record, reference, key, None)["block"]["checks"][-1]["status"] == drift.INSUFFICIENT


# ------------------------------------------------------ the plan and the replay


def test_replay_plan_is_deterministic_seeded_and_validation_only(monkeypatch, plan, structure, stored):
    subset_of, table = structure
    assert stream.build_plan(table)["checksum_sha256"] == plan["checksum_sha256"] == stored["replay_plan"]["checksum_sha256"]
    monkeypatch.setattr(stream, "PLAN_SEED", V.PLAN_SEED + 1)
    assert stream.build_plan(table)["checksum_sha256"] != plan["checksum_sha256"]
    monkeypatch.undo()
    stream.check_plan(plan, subset_of)
    assert all(subset_of[draft] in V.VALIDATION_SUBSETS for draft in stream.plan_ids(plan))
    traffic = table.loc[table["subset"] == V.TRAFFIC_SUBSET].sort_values(["sent_at", "draft_id"], kind="mergesort")["draft_id"].tolist()
    scenario = table.set_index("draft_id")["scenario_id"]
    pool = set(plan["shift"]["pool_draft_ids"])
    for window in plan["windows"]:
        base = traffic[(window["window"] - 1) * V.WINDOW_EMAILS : window["window"] * V.WINDOW_EMAILS]
        assert len(window["draft_ids"]) == V.WINDOW_EMAILS
        assert window["injected_emails"] == round(V.SHIFT_SCHEDULE.get(window["window"], 0.0) * V.WINDOW_EMAILS)
        replaced = {item["position"] for item in window["injected"]}
        assert len(replaced) == window["injected_emails"]
        for position, draft_id in enumerate(window["draft_ids"]):
            if position in replaced:
                assert draft_id in pool and scenario[base[position]] == V.REPLACEABLE_SCENARIO
            else:
                assert draft_id == base[position]
    assert plan["probe_draft_id"] in traffic and scenario[plan["probe_draft_id"]] == V.REPLACEABLE_SCENARIO
    assert stored["replay_plan"]["windows"] == json.loads(json.dumps(plan["windows"]))


def test_stored_replay_matches_the_plan_the_bundle_and_the_frozen_policy(stored, policy):
    replay_record, plan_record = stored["replay"], stored["replay_plan"]
    assert replay_record["plan_checksum"] == plan_record["checksum_sha256"]
    bundle = replay_record["bundle"]
    assert bundle["T_warn"] == policy["T_warn"] and bundle["blocking_enabled"] is False
    assert bundle["policy_version"] == policy["policy_version"] and bundle["model_version"] == policy["model_version"]
    key = alerts.expected_version_key(policy)
    for item in replay_record["windows"]:
        summary = item["summary"]
        assert summary["blocks"] == 0 and summary["decisions"]["block"] == 0
        assert summary["requests"] == V.WINDOW_EMAILS == summary["assessed"] + summary["unable_to_assess"] + summary["unexpected_responses"]
        assert set(summary["versions"]) == {key} and not summary["invariant_problems"]
    # The replayed base traffic contains every validation mistake exactly once, so the warnings match the stored policy record.
    total = sum(item["summary"]["warnings"] for item in replay_record["windows"])
    assert total == policy["validation_confusion"]["warnings"]
    assert all(item["no_decision_and_no_score"] for when in replay_record["probes"].values() for item in when)
    assert {item["category"] for item in replay_record["probes"]["before"]} == {"invalid_input", "unavailable"}


def test_the_replay_raises_its_alert_deterministically(stored, plan, by_draft, policy):
    reference = stored["reference"]
    drifts = {window["window"]: drift.input_drift(reference, window_frame(window, by_draft)) for window in plan["windows"]}
    again = {window["window"]: drift.input_drift(reference, window_frame(window, by_draft)) for window in plan["windows"]}
    assert json.dumps(drifts, sort_keys=True) == json.dumps(again, sort_keys=True)
    # Unshifted windows do not alert; the last, most shifted window alerts on the first-contact inputs.
    for number in (*V.REFERENCE_WINDOWS, V.CURRENT_WINDOWS[0]):
        assert drifts[number]["alert"] == [], number
    last = drifts[V.N_WINDOWS]
    assert last["status"] == drift.ALERT
    assert {"recipient_novel_to_sender", "pair_recency_observed"} <= set(last["alert"])
    # The stored record agrees with the recomputation.
    for item in stored["replay"]["windows"]:
        recomputed = drifts[item["window"]]
        assert item["input_drift"]["alert"] == recomputed["alert"] and item["input_drift"]["status"] == recomputed["status"]
        assert item["input_drift"]["rows"] == recomputed["rows"]
    key = alerts.expected_version_key(policy)
    first = alerts.evaluate(stored["replay"], reference, key, stored["feedback_review"])
    second = alerts.evaluate(copy.deepcopy(stored["replay"]), copy.deepcopy(reference), key, copy.deepcopy(stored["feedback_review"]))
    assert first == second
    assert {item["check"] for item in first["timeline"]} >= {"input_drift", "near_cutoff_scores", "limited_relationship_history_rate"}
    assert first["windows"][V.CURRENT_WINDOWS[0]]["alerts"] == []
    deterministic = [item for item in first["windows"][V.N_WINDOWS]["checks"] if not item.get("timing_dependent")]
    assert {item["id"] for item in deterministic if item["status"] == drift.ALERT} == {"limited_relationship_history_rate", "near_cutoff_scores", "input_drift"}


def _mini_plan(plan: dict, per_window: int = 6) -> dict:
    mini = copy.deepcopy(plan)
    for window in mini["windows"]:
        injected = [item["draft_id"] for item in window["injected"][: per_window // 2]]
        window["draft_ids"] = window["draft_ids"][: per_window - len(injected)] + injected
        window["emails"] = len(window["draft_ids"])
        window["injected"] = []
    mini["checksum_sha256"] = stream.plan_checksum(mini)
    return mini


def test_live_replay_is_reproducible_and_refuses_another_bundle(monkeypatch, api, plan, features, structure, stored, policy):
    subset_of, _ = structure
    monkeypatch.setattr(rp, "WARMUP_CALLS", 2)
    mini = _mini_plan(plan)
    requests = mdata.load_requests(DATA, sorted(stream.plan_ids(mini)))
    expected = rp.expected_bundle(POLICY_DIR)
    assert expected["T_warn"] == policy["T_warn"]

    def run():
        return rp.run_replay(mini, requests, features, api, expected, stored["reference"], subset_of=subset_of)

    first, second = run(), run()
    for result in (first, second):
        for item in result["windows"] + [result["blocks"]["reference"], result["blocks"]["current"]]:
            item["summary"].pop("client_latency_ms"), item["summary"].pop("server_latency_ms")
        result.pop("elapsed_seconds"), result.pop("service"), result["environment"].pop("cpu_count")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["windows"][0]["input_drift"]["status"] == drift.INSUFFICIENT
    assert all(item["no_decision_and_no_score"] for when in first["probes"].values() for item in when)
    assert sum(item["summary"]["blocks"] for item in first["windows"]) == 0
    # The requests sent carry only Phase 1 fields.
    assert all(set(payload) == {"draft_timestamp", "sender", "to", "cc", "bcc", "subject", "body", "context_snapshot_id"} for payload in requests.values())
    for change in ({"T_warn": 0.5}, {"policy_version": "other-policy"}, {"model_version": "other-model"}, {"snapshot_id": "other-snapshot"}):
        with pytest.raises(rp.ReplayError):
            rp.check_ready(api, {**expected, **change})


# ------------------------------------------------------------- observations


def _assessed_body(**changes) -> dict:
    body = {
        "status": "assessed", "mode": "simulation", "decision": "allow", "email_risk_score": 0.2,
        "provenance": {"model_version": "m", "feature_spec_version": "f", "policy_version": "p", "blocking_enabled": False},
        "recipients": [{"risk_score": 0.2, "flagged": False, "evidence_limitations": [{"code": "LIMITED_RELATIONSHIP_HISTORY"}]}],
        "duration_ms": 1.0,
    }
    body.update(changes)
    return body


def test_observations_flag_broken_contracts_and_never_keep_addresses():
    ok = obs.observe(200, _assessed_body(), 5.0)
    assert ok.status == obs.ASSESSED and ok.limited_history_recipients == 1 and not ok.problems
    assert obs.observe(200, _assessed_body(decision="block"), 5.0).problems
    assert obs.observe(200, _assessed_body(provenance={"model_version": "m", "feature_spec_version": "f", "policy_version": "p", "blocking_enabled": True}), 5.0).problems
    assert obs.observe(200, _assessed_body(mode="live"), 5.0).problems
    for bad in (None, "text", {"status": "assessed"}, _assessed_body(email_risk_score=float("nan")), _assessed_body(recipients=[]), {"status": "other"}):
        assert obs.observe(200, bad, 1.0).status == obs.UNEXPECTED
    failure = {"status": "unable_to_assess", "category": "unavailable", "message": "A recipient is not in the context snapshot directory", "decision": None, "email_risk_score": None, "recipients": None}
    seen = obs.observe(503, failure, 1.0)
    assert seen.status == obs.UNABLE and seen.category == "unavailable" and not seen.problems
    assert obs.observe(503, {**failure, "decision": "allow"}, 1.0).problems
    assert obs.observe(503, {**failure, "email_risk_score": 0.1}, 1.0).problems
    assert obs.observe(503, {**failure, "category": "maybe"}, 1.0).status == obs.UNEXPECTED
    assert obs.observe(422, {**failure, "category": "invalid_input", "message": "bad sam@demo.example"}, 1.0).message == obs.WITHHELD
    assert obs.safe_message("x" * 500) == obs.WITHHELD


def test_window_summary_bins_the_near_band_and_keeps_aggregates_only():
    t_warn = 0.9996767050340489
    summary = obs.WindowSummary(t_warn)
    edges = [t_warn - V.NEAR_BAND - 1e-9, t_warn - V.NEAR_BAND, t_warn - 1e-9, t_warn, 1.0]
    for index, score in enumerate(edges):
        summary.add(obs.Observation(obs.ASSESSED, 200, 1.0, decision="warn" if score >= t_warn else "allow", email_risk=score, recipient_count=1, version_key="a|b|c"), draft_id=f"d{index}")
    result = summary.to_dict()
    histogram = result["score_histogram"]
    assert histogram["near band"] == 2 and histogram["at or above T_warn"] == 2 and histogram["0.99 to near band"] == 1
    assert result["near_band_emails"] == 2 and result["near_band_distinct_drafts"] == 2
    assert result["highest_allowed_email_risk"] == edges[2] and result["warnings"] == 2
    assert all(not isinstance(value, list) or all(isinstance(item, dict) for item in value) for value in result.values())


# ------------------------------------------------------------ alert checks


def test_critical_checks_and_gated_rate_checks():
    base = {
        "requests": 600, "assessed": 600, "unable_to_assess": 0, "unexpected_responses": 0, "blocks": 0, "warnings": 1, "invariant_problems": {},
        "versions": {"m|f|p": 600}, "failures": [], "emails_with_limited_relationship_history": 5, "emails_with_limited_text": 1,
        "email_flags_from_feature_rows": {"cold_start_sender": 1}, "near_band_emails": 1, "margin_to_cutoff": 0.002,
        "client_latency_ms": {"n": 600, "p50": 20.0, "p95": 40.0, "p99": 50.0, "max": 60.0},
    }
    reference = copy.deepcopy(base)
    by_id = lambda summary: {item["id"]: item for item in alerts.operational_checks(summary, reference, "m|f|p")}  # noqa: E731
    assert not [item for item in by_id(base).values() if item["status"] == drift.ALERT]
    assert by_id({**base, "blocks": 1})["blocks"]["status"] == drift.ALERT and by_id({**base, "blocks": 1})["blocks"]["severity"] == alerts.CRITICAL
    assert by_id({**base, "versions": {"m|f|other": 600}})["served_versions"]["status"] == drift.ALERT
    assert by_id({**base, "invariant_problems": {"x": 1}})["response_invariants"]["severity"] == alerts.CRITICAL
    assert by_id({**base, "client_latency_ms": {**base["client_latency_ms"], "p95": 400.0}})["latency_p95"]["status"] == drift.ALERT
    small = by_id({**base, "requests": 100, "client_latency_ms": {**base["client_latency_ms"], "p95": 900.0}})
    assert small["latency_p95"]["status"] == drift.INSUFFICIENT and small["unable_to_assess_rate"]["status"] == drift.INSUFFICIENT
    unable = by_id({**base, "unable_to_assess": 30, "assessed": 570})
    assert unable["unable_to_assess_rate"]["status"] == drift.ALERT
    few = by_id({**base, "assessed": V.MIN_EMAILS_SCORE_BAND - 1, "near_band_emails": 40})
    assert few["near_cutoff_scores"]["status"] == drift.INSUFFICIENT


# ------------------------------------------------------- reviewed feedback


def _items(spec):
    """(stratum, misdirected, delay) tuples as queue items, labels, and delays."""
    items, labels, delays = [], {}, {}
    for index, (stratum, misdirected, delay) in enumerate(spec):
        draft = f"d{index:06d}"
        items.append({"window": 1, "position": index, "draft_id": draft, "decision": "warn" if stratum == "warned" else "allow", "stratum": stratum, "inclusion_probability": 1.0})
        labels[draft], delays[(1, index)] = misdirected, delay
    return items, labels, delays


def test_efficacy_comes_only_from_returned_labels_with_denominators():
    spec = [("warned", True, 1.0), ("warned", True, 20.0)] + [("a", i < 2, 1.0) for i in range(10)] + [("a", True, 40.0)] + [("b", False, 2.0) for _ in range(10)]
    items, labels, delays = _items(spec)
    population = {"warned": 2, "a": 11, "b": 100}
    early = fb.review_block(items, population, labels, delays, horizon=5.0, assessed=113)
    assert early["queued"] == 23 and early["returned"] == 21
    assert early["warned"] == {"population": 2, "reviewed": 1, "confirmed_misdirected": 1, "confirmed_all_intended": 0, "coverage": 0.5}
    assert early["strata"]["a"]["reviewed"] == 10 and early["strata"]["a"]["mistakes"] == 2 and early["strata"]["a"]["population"] == 11
    assert early["strata"]["b"]["reviewed"] == 10 and early["strata"]["b"]["population"] == 100
    assert early["positives_confirmed"] == 3 and early["label_coverage_of_assessed"] == 21 / 113
    # The unreturned mistake (delay 40 days) is unknown, not zero: the estimate extrapolates from what returned.
    assert early["strata"]["a"]["estimate"] == pytest.approx(2 + 1 * 2 / 10)
    assert early["recall"]["low"] < early["recall"]["estimate"] < early["recall"]["high"] <= 1.0
    assert early["warned_only_view"]["recall_if_only_warned_emails_were_reviewed"] == 1.0
    late = fb.review_block(items, population, labels, delays, horizon=100.0, assessed=113)
    assert late["returned"] == 23 and late["strata"]["a"]["mistakes"] == 3 and late["positives_confirmed"] == 5
    # Nothing returned in a stratum: recall is not estimable and no interval is invented.
    none = fb.review_block(items, population, labels, delays, horizon=0.5, assessed=113)
    assert none["returned"] == 0 and none["recall"]["estimate"] is None and none["recall"]["low"] is None
    # Exact interval facts.
    assert fb.clopper_pearson(0, 10)[0] == 0.0 and fb.clopper_pearson(10, 10)[1] == 1.0
    assert fb.stratum_count(50, 50, 4) == {"estimate": 4.0, "low": 4.0, "high": 4.0, "reviewed": 50, "mistakes": 4, "population": 50}


def test_unreviewed_feedback_never_changes_a_label_the_model_or_the_cutoff(stored, policy, tmp_path):
    stipulated = {("d1", "c1"): True, ("d1", "c2"): False}
    for status in ("pending_review", "rejected", "", "click"):
        assert fb.apply_accepted_reviews(stipulated, [{"draft_id": "d1", "contact_id": "c1", "review_status": status, "asserted_intended": "false"}]) == stipulated
    assert fb.apply_accepted_reviews(stipulated, [{"draft_id": "d1", "contact_id": "c1", "review_status": "accepted", "asserted_intended": "false"}])[("d1", "c1")] is False
    assert fb.apply_accepted_reviews(stipulated, [{"draft_id": "d1", "contact_id": "c1", "review_status": "accepted", "asserted_intended": ""}]) == stipulated

    clicks = tmp_path / "clicks.jsonl"
    versions = {"model_version": policy["model_version"], "feature_spec_version": policy["feature_spec_version"], "policy_version": policy["policy_version"]}
    clicks.write_text("".join(json.dumps({"received_at": "2026-01-01T00:00:00Z", "request_id": f"req_{i}", "contact_id": "c_x", "label": "unintended", **versions}) + "\n" for i in range(5)), encoding="utf-8")
    before = {"policy": sha256(POLICY_PATH), "model": sha256(MODEL_PATH), "scores": sha256(POLICY_DIR / "validation_scores.csv")}
    with_clicks = fb.summarize(stored["replay"], DATA, policy_path=POLICY_PATH, model_path=MODEL_PATH, feedback_path=clicks)
    none = fb.summarize(stored["replay"], DATA, policy_path=POLICY_PATH, model_path=MODEL_PATH, feedback_path=tmp_path / "missing.jsonl")
    assert before == {"policy": sha256(POLICY_PATH), "model": sha256(MODEL_PATH), "scores": sha256(POLICY_DIR / "validation_scores.csv")}
    assert with_clicks["policy_and_model_unchanged"] and with_clicks["labels_changed_by_feedback"] == 0
    assert with_clicks["real_reviewed_labels"]["api_feedback"]["lines"] == 5 and with_clicks["real_reviewed_labels"]["api_feedback"]["reviewed"] == 0
    assert with_clicks["real_reviewed_labels"]["reviewed_labels_on_monitored_traffic"] == 0
    assert none["real_reviewed_labels"]["api_feedback"]["lines"] == 0
    # Clicks change no efficacy number, no queued label, and no delay.
    for key in ("efficacy", "queue_items", "simulation", "checksums"):
        assert with_clicks[key] == none[key], key
    assert with_clicks["policy_and_model_unchanged"] and stored["feedback_review"]["policy_and_model_unchanged"]
    # The simulated review is reproducible from the replay and the stipulated labels.
    assert with_clicks["queue_items"] == stored["feedback_review"]["queue_items"]


def test_click_feedback_through_the_api_leaves_decisions_and_files_alone(api, plan, policy):
    request = mdata.load_requests(DATA, [plan["probe_draft_id"]])[plan["probe_draft_id"]]
    before_files = (sha256(POLICY_PATH), sha256(MODEL_PATH))
    first = api.post("/assess", json=request).json()
    address = first["recipients"][0]["address"]
    assert api.post("/feedback", json={"request_id": first["request_id"], "recipient": address, "label": "unintended"}).status_code == 200
    second = api.post("/assess", json=request).json()
    assert (second["decision"], second["email_risk_score"], second["provenance"]["T_warn"]) == (first["decision"], first["email_risk_score"], policy["T_warn"])
    assert before_files == (sha256(POLICY_PATH), sha256(MODEL_PATH))


def test_stored_feedback_record_reports_coverage_delay_and_the_real_evidence(stored):
    review = stored["feedback_review"]
    real = review["real_reviewed_labels"]
    assert real["reviewed_labels_on_monitored_traffic"] == 0 and real["dataset_reviewer_feedback"]["accepted"] == 0
    assert real["dataset_reviewer_feedback"]["about_validation_drafts"] == 0
    assert real["api_feedback"]["reviewed"] == 0 and real["api_feedback"]["linkable_to_a_draft"] is False
    assert review["simulation"]["label_source"].startswith("simulated reviewer")
    horizons = review["efficacy"]["by_horizon"]
    assert sorted(int(h) for h in horizons) == list(V.REVIEW_HORIZONS_DAYS)
    for role in ("reference", "current"):
        returned = [horizons[str(h)][role]["returned"] for h in V.REVIEW_HORIZONS_DAYS]
        assert returned == sorted(returned) and returned[-1] == horizons["30"][role]["queued"]
        for h in V.REVIEW_HORIZONS_DAYS:
            side = horizons[str(h)][role]
            assert side["label_coverage_of_assessed"] == pytest.approx(side["returned"] / side["assessed_emails"])
            assert side["warned"]["reviewed"] <= side["warned"]["population"]
    queue = stored["replay"]["review_queue"]
    assert {item["stratum"] for item in queue["items"]} <= {"warned", *[name for name, *_ in V.ALLOWED_STRATA]}
    assert all(item["decision"] == "warn" for item in queue["items"] if item["stratum"] == "warned")
    assert all(item["inclusion_probability"] == 1.0 for item in queue["items"] if item["stratum"] in ("warned", V.ALLOWED_STRATA[0][0]))
    # Every warned email is queued, and every one of them is in the population count.
    assert sum(1 for item in queue["items"] if item["stratum"] == "warned") == sum(week.get("warned", 0) for week in queue["population"].values())


# --------------------------------------------------- bundle refusal (rollback)


def test_a_mismatched_bundle_is_refused_and_never_allowed(tmp_path, policy, plan):
    base = ApiPaths.from_env(ROOT)
    # Direct loader checks: every policy-level mismatch refuses to load.
    def variant(**changes):
        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        for key, value in changes.items():
            if key == "model_checksum":
                data["checksums"]["model.joblib"] = value
            else:
                data[key] = value
        target = tmp_path / f"{len(list(tmp_path.iterdir()))}.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        return target

    manifest = FEATURES / "artifact_manifest.json"
    assert load_bundle(POLICY_PATH, MODEL_PATH, manifest).t_warn == policy["T_warn"]
    for changes in ({"policy_version": "med-policy-v1"}, {"model_run_name": "other"}, {"model_checksum": "0" * 64}, {"blocking_enabled": True}, {"T_warn": "high"}, {"T_block": 0.9}, {"calibration": "fit"}):
        with pytest.raises(PolicyError):
            load_bundle(variant(**changes), MODEL_PATH, manifest)
    with pytest.raises(PolicyError):
        load_bundle(tmp_path / "missing.json", MODEL_PATH, manifest)
    corrupted = tmp_path / "model.joblib"
    corrupted.write_bytes(MODEL_PATH.read_bytes()[:-1] + bytes([MODEL_PATH.read_bytes()[-1] ^ 1]))
    with pytest.raises(PolicyError, match="Checksum"):
        load_bundle(POLICY_PATH, corrupted, manifest)
    # Through the real service: refused as unavailable, with no decision and no score.
    request = mdata.load_requests(DATA, [plan["probe_draft_id"]])[plan["probe_draft_id"]]
    cases = {name: (description, builder) for name, description, builder in bundles.CASES}
    for name in ("feature_artifact_tampered", "policy_names_another_policy_version"):
        description, builder = cases[name]
        result = bundles.run_case(name, description, builder, base, request, ROOT)
        assert result["refused"] and not result["served"], name
        assert result["health_http"] == 200 and result["ready_http"] == 503 and result["assess_http"] == 503
        assert result["assess_category"] == "unavailable" and result["decision"] is None and result["email_risk_score_reported"] is False
        assert result["versions_reported"] is False and result["ready_reason"]


def test_stored_bundle_checks_refuse_every_altered_bundle(stored):
    checks = stored["bundle_checks"]
    names = {item["case"] for item in checks["cases"]}
    assert names == {name for name, _, _ in bundles.CASES}
    assert checks["all_altered_bundles_refused"] and checks["control_served"] and checks["frozen_files_edited"] is False
    for item in checks["cases"]:
        if item["case"] == "control_unchanged":
            assert item["served"] and item["ready_http"] == 200 and "score" not in json.dumps(item).replace("email_risk_score_reported", "")
        else:
            assert item["refused"] and item["decision"] is None and item["email_risk_score_reported"] is False and item["assess_category"] == "unavailable"
            assert "<repo>" in item["ready_reason"] or "/Users/" not in item["ready_reason"]
    assert next(item for item in checks["cases"] if item["case"] == "previous_bundle")["refused"]
    assert "live switch" in checks["not_covered"]


# --------------------------------------------------------- reports and privacy


def _text_files():
    return [*sorted(DOCS.glob("*.md")), *sorted(STORED.glob("*.json"))]


def test_reports_contain_no_addresses_subjects_or_bodies(plan):
    address = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
    corpus = {path.name: path.read_text(encoding="utf-8") for path in _text_files()}
    assert len(corpus) >= 10
    for name, text in corpus.items():
        assert not address.search(text), name
    keep = set(stream.plan_ids(plan))
    drafts = mdata.stream_rows(DATA / "drafts.csv", keep, columns=("draft_id", "subject", "body"))
    joined = "\n".join(corpus.values())
    for subject in set(drafts["subject"]):
        if len(subject) >= 12:
            assert subject not in joined, subject
    for body in drafts["body"]:
        if len(body) >= 40:
            assert body[:60] not in joined
    contacts = mdata.load_contacts(DATA)
    for display_name in contacts["display_name"]:
        assert display_name not in joined, display_name


def test_stored_records_hold_aggregates_and_no_per_email_score(stored):
    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in {"email_risk", "email_risk_score", "risk_score", "score", "scores"}, path + "/" + key
                yield from walk(value, path + "/" + key)
        elif isinstance(node, list):
            if len(node) > 40:
                assert all(isinstance(item, (str, dict)) for item in node), path
            for item in node:
                yield from walk(item, path)
        else:
            yield path, node

    for name, record in stored.items():
        assert len(list(walk(record))) > 0, name
    item_keys = {"window", "position", "draft_id", "decision", "stratum", "inclusion_probability"}
    assert all(set(item) == item_keys for item in stored["replay"]["review_queue"]["items"])
    assert all(set(item) == {"window", "position", "draft_id", "decision", "stratum", "delay_days", "misdirected"} for item in stored["feedback_review"]["queue_items"])


def test_documents_are_regenerated_from_the_stored_records():
    records = report.load_records(STORED, POLICY_PATH)
    rendered = report.render_all(records)
    assert set(rendered) == set(report.DOC_FILES)
    for name, text in rendered.items():
        assert (DOCS / name).read_text(encoding="utf-8") == text, name
    monitoring, replay_doc, feedback_doc, proposal, runbook = (rendered[name] for name in report.DOC_FILES)
    assert "## Reference periods" in monitoring and "insufficient sample" in monitoring and "What the structured log carries" in monitoring
    assert "Three findings, kept apart" in replay_doc and "Proposed targeted experiment (not run)" in replay_doc
    assert "A click is not a label" in feedback_doc and "Why feedback on warned emails alone is biased" in feedback_doc
    assert "There is no online evidence" in proposal and "Unit of randomization: the sender" in proposal
    for heading in ("## Rollout", "## Rollback", "### A high-impact false positive", "### Rising false negatives", "### A scoring outage", "## Promotion gates"):
        assert heading in runbook, heading
    assert "does not show that detection improved" in feedback_doc and "Nothing here shows that detection improved" in monitoring


def test_public_files_avoid_private_terms():
    terms = [re.compile(pattern, re.IGNORECASE) for pattern in (r"interview", r"job description", r"project_context", r"abnormal", r"employer")]
    for path in [*sorted(DOCS.glob("*.md")), *sorted(SRC.glob("*.py"))]:
        text = path.read_text(encoding="utf-8")
        for pattern in terms:
            assert not pattern.search(text), (path.name, pattern.pattern)


# --------------------------------------------------- code rules and packaging


FORBIDDEN_IMPORTS = (
    "med_models.experiments", "med_models.estimators", "med_models.folds", "med_models.cli", "med_models.report",
    "med_policy.select", "med_policy.pipeline", "med_policy.evaluate", "med_policy.cli", "med_policy.report", "med_policy.latency",
    "med_features.build", "med_features.text_model", "med_features.cli", "med_data.generate", "med_data.cli",
    "sklearn.linear_model", "sklearn.tree", "sklearn.calibration", "sklearn.model_selection", "sklearn.pipeline",
)


def test_no_module_imports_training_code_to_refit():
    for path in SRC.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module}.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"fit", "fit_transform", "partial_fit", "fit_predict"}, f"{path.name} calls .{node.func.attr}"
                continue
            else:
                continue
            for name in names:
                assert not any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN_IMPORTS), f"{path.name} imports {name}"
    probe = (
        "import sys, importlib\n"
        "for m in ('version','data','reference','drift','observations','stream','alerts','replay','feedback','bundles','experiment','report','cli'):\n"
        "    importlib.import_module('med_monitor.' + m)\n"
        "print('\\n'.join(sorted(sys.modules)))"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT, check=True)
    loaded = set(result.stdout.split())
    training = {
        "med_models.experiments", "med_models.estimators", "med_models.folds", "med_policy.select", "med_policy.pipeline",
        "med_policy.evaluate", "sklearn.linear_model", "sklearn.tree", "sklearn.calibration", "sklearn.model_selection",
    }
    assert not (loaded & training), sorted(loaded & training)


def test_versions_come_from_the_owning_packages():
    from med_api import version as api_version
    from med_api.latency import TARGET_P95_MS
    from med_policy import version as policy_version

    assert V.POLICY_VERSION == policy_version.POLICY_VERSION and V.MODEL_VERSION == policy_version.MODEL_VERSION
    assert V.FEATURE_SPEC_VERSION == policy_version.FEATURE_SPEC_VERSION and V.SNAPSHOT_ID == api_version.SNAPSHOT_ID
    assert V.LATENCY_TARGET_MS == TARGET_P95_MS
    assert V.TRAFFIC_SUBSET == policy_version.SELECTION_SUBSET and set(V.FROZEN_SUBSETS) == set(FROZEN_SUBSETS)
    for path in SRC.glob("*.py"):
        assert re.search(r"med-(synth|features|model|policy|api)-v\d", path.read_text(encoding="utf-8")) is None, path.name
    assert V.MONITOR_VERSION == "med-monitor-v1" and V.ARTIFACT_DIR.name == V.MONITOR_VERSION


def test_commands_refuse_to_overwrite_a_record(tmp_path, capsys):
    from med_monitor.cli import main

    existing = tmp_path / "reference.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="not overwritten"):
        main(["build-reference", "--output", str(existing)])
    assert existing.read_text(encoding="utf-8") == "{}"
    with pytest.raises(FileExistsError):
        ref.write_once({}, existing)


def test_package_version_script_and_light_dependencies():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == "0.8.0"
    assert project["scripts"]["med-monitor"] == "med_monitor.cli:main"
    heavy = ("torch", "tensorflow", "transformers", "openai", "anthropic", "keras", "jax")
    everything = list(project["dependencies"]) + [item for group in project["optional-dependencies"].values() for item in group]
    assert not [item for item in everything if item.lower().startswith(heavy)]


def test_experiment_arithmetic_is_labeled_a_proposal(stored):
    assert experiment.zero_event_n(1.0) == 2996
    assert experiment.design_effect(200, 0.0) == 1.0 and experiment.design_effect(200, 0.05) == pytest.approx(10.95)
    assert experiment.two_proportion_n(0.3, 0.5) < experiment.two_proportion_n(0.3, 0.4) and experiment.two_proportion_n(0.3, 0.4) > 0
    assert experiment.stop_for_harm_count(2996, 1.0) > 3
    design = experiment.design(stored["reference"])
    assert design["status"] == "proposal: no online evidence"
    assert design["detections"][0]["baseline_recall"] == stored["reference"]["recorded_test_pass"]["recall"]
    assert all(row["with_sender_clustering"][0]["emails"] <= row["with_sender_clustering"][-1]["emails"] for row in design["detections"])
    pop = stored["replay_plan"]["traffic_population"]
    assert pop["senders"] > 1 and pop["largest_sender_share"] > 0.9
