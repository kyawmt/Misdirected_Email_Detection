"""Phase 6 API contract: normalizer, failures, codes, feedback, and logging."""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import med_api.context as context_module
import med_api.service as service_module
import med_data.io as data_io
import med_policy.decision as decision_module
from med_data.io import read_dataset, read_serving_tables
from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.fixtures import FixtureError, example_draft_ids, request_from_draft
from med_api.service import CONTENT_FEATURES, LOG_FIELDS, format_log_record
from med_api.version import API_CONTRACT_VERSION, DEFAULT_PATHS, SNAPSHOT_ID

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / DEFAULT_PATHS["data"]
POLICY = ROOT / DEFAULT_PATHS["policy"]
FEATURES = ROOT / DEFAULT_PATHS["features"]
BASE_TIMESTAMP = "2025-05-05T09:30:00Z"


def _paths(tmp: Path, **changes) -> ApiPaths:
    paths = ApiPaths(
        policy=POLICY,
        model=ROOT / DEFAULT_PATHS["model"],
        features=FEATURES,
        data=DATA,
        feedback=tmp / "feedback.jsonl",
    )
    return replace(paths, **changes)


@pytest.fixture(scope="module")
def feedback_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("feedback")


@pytest.fixture(scope="module")
def client(feedback_dir):
    with TestClient(create_app(_paths(feedback_dir))) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def dataset():
    return read_dataset(DATA)


@pytest.fixture(scope="module")
def picks(dataset):
    """Example validation drafts chosen by rule, not by id."""
    scores = pd.read_csv(POLICY.parent / "validation_scores.csv", float_precision="round_trip")
    return example_draft_ids(dataset, scores)


@pytest.fixture(scope="module")
def validation_scores():
    return pd.read_csv(POLICY.parent / "validation_scores.csv", float_precision="round_trip").set_index("draft_id")


def _base(**changes) -> dict:
    payload = {
        "draft_timestamp": BASE_TIMESTAMP,
        "sender": {"address": "maya@demo.example", "display_name": "Maya"},
        "to": [{"address": "sam@demo.example", "display_name": "Sam"}],
        "cc": [],
        "bcc": [],
        "subject": "Facilities walkthrough",
        "body": "Can we confirm the badge list for the walkthrough on Thursday?",
        "context_snapshot_id": SNAPSHOT_ID,
    }
    payload.update(changes)
    return payload


def _values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _values(item)
    else:
        yield value


def _assert_unable(response, category):
    body = response.json()
    assert body["status"] == "unable_to_assess"
    assert body["category"] == category
    assert body["decision"] is None
    assert body["email_risk_score"] is None
    assert body["recipients"] is None
    assert body["flagged_recipients"] is None
    assert "allow" not in list(_values(body))
    assert body["contract_version"] == API_CONTRACT_VERSION
    return body


def test_repeated_address_merges_roles_before_transform(client, monkeypatch):
    seen = []
    original = decision_module.transform_draft

    def spy(directory, history, transformer, query):
        seen.append(tuple(contact for contact, _ in query.recipients))
        return original(directory, history, transformer, query)

    monkeypatch.setattr(decision_module, "transform_draft", spy)
    payload = _base(
        to=[{"address": " Sam@Demo.Example "}],
        cc=[{"address": "sam@demo.example", "display_name": "Sam R."}, {"address": "priya@demo.example"}],
    )
    body = client.post("/assess", json=payload).json()
    assert body["status"] == "assessed"
    assert [item["address"] for item in body["recipients"]] == ["sam@demo.example", "priya@demo.example"]
    assert body["recipients"][0]["roles"] == ["to", "cc"]
    assert body["recipients"][0]["display_name"] == "Sam R."
    assert seen and all(len(ids) == len(set(ids)) for ids in seen)


@pytest.mark.parametrize(
    "changes",
    [
        {"to": [], "cc": [], "bcc": []},
        {"to": [{"address": f"person{index}@demo.example"} for index in range(21)]},
        {"subject": "x" * 501},
        {"body": "x" * 20001},
        {"draft_timestamp": "2025-05-05T09:30:00"},
        {"to": [{"address": "not-an-email"}]},
        {"to": [{"address": "sam@demo.com"}]},
        {"to": [{"address": "sám@demo.example"}]},
        {"sender": {"address": "lee@vendor.example"}},
        {"scenario_id": "S01"},
        {"to": [{"address": "sam@demo.example", "intended": True}]},
        {"risk_score": 0.0},
    ],
)
def test_invalid_input_has_no_score_and_no_allow(client, changes):
    response = client.post("/assess", json=_base(**changes))
    assert response.status_code == 422
    _assert_unable(response, "invalid_input")


def test_malformed_json_is_invalid_input(client):
    response = client.post("/assess", content=b"{not json", headers={"content-type": "application/json"})
    assert response.status_code == 422
    _assert_unable(response, "invalid_input")


def test_unknown_snapshot_is_unavailable(client):
    response = client.post("/assess", json=_base(context_snapshot_id="other"))
    assert response.status_code == 503
    _assert_unable(response, "unavailable")


def test_unknown_well_formed_address_is_unavailable(client):
    response = client.post("/assess", json=_base(to=[{"address": "nobody@example"}]))
    assert response.status_code == 503
    _assert_unable(response, "unavailable")


def test_contact_listed_after_the_cutoff_is_unavailable(client, dataset):
    contacts = dataset.contacts
    later = contacts.loc[contacts["directory_visible_from"] > pd.Timestamp(BASE_TIMESTAMP)].sort_values("contact_id")
    assert not later.empty
    response = client.post("/assess", json=_base(to=[{"address": str(later.iloc[0]["email_address"])}]))
    _assert_unable(response, "unavailable")


def test_missing_policy_is_unavailable_and_ready_fails(tmp_path):
    with TestClient(create_app(_paths(tmp_path, policy=tmp_path / "missing.json"))) as broken:
        assert broken.get("/health").status_code == 200
        assert broken.get("/ready").status_code == 503
        body = _assert_unable(broken.post("/assess", json=_base()), "unavailable")
        assert "provenance" not in body
        _assert_unable(broken.post("/assess", json=_base(to=[{"address": "not-an-email"}])), "invalid_input")


def test_checksum_mismatch_is_unavailable(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["checksums"]["model.joblib"] = "0" * 64
    bad = tmp_path / "policy.json"
    bad.write_text(json.dumps(policy), encoding="utf-8")
    with TestClient(create_app(_paths(tmp_path, policy=bad))) as broken:
        assert broken.get("/ready").status_code == 503
        _assert_unable(broken.post("/assess", json=_base()), "unavailable")


def _altered_policy(tmp_path: Path, name: str, **changes) -> Path:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy.update(changes)
    path = tmp_path / name
    path.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    return path


def _assert_fails_closed(broken):
    ready = broken.get("/ready")
    assert ready.status_code == 503 and ready.json()["ready"] is False
    response = broken.post("/assess", json=_base())
    assert response.status_code == 503
    body = _assert_unable(response, "unavailable")
    assert "provenance" not in body
    return ready.json()["reason"]


@pytest.mark.parametrize(
    ("name", "changes", "reason"),
    [
        ("cutoff_above_one.json", {"T_warn": 2.0}, "outside the risk-score range"),
        ("cutoff_negative.json", {"T_warn": -0.5}, "outside the risk-score range"),
        ("cutoff_edited_in_range.json", {"T_warn": 0.5}, "Checksum mismatch for policy.json"),
    ],
)
def test_an_invalid_or_edited_policy_leaves_the_service_unready_and_failing_closed(tmp_path, name, changes, reason):
    """A cutoff of 2.0 would allow every score; it must never start. An edited file is refused too."""
    bad = _altered_policy(tmp_path, name, **changes)
    with TestClient(create_app(_paths(tmp_path, policy=bad))) as broken:
        assert reason in _assert_fails_closed(broken)


def test_a_policy_file_with_any_other_byte_changed_is_refused(tmp_path):
    bad = tmp_path / "policy_whitespace.json"
    bad.write_bytes(POLICY.read_bytes() + b"\n")
    with TestClient(create_app(_paths(tmp_path, policy=bad))) as broken:
        assert "Checksum mismatch for policy.json" in _assert_fails_closed(broken)


def test_an_unchanged_copy_of_the_policy_is_the_control_and_serves_with_three_tables_parsed(tmp_path, monkeypatch):
    """The control for the refused policies above. The same load shows the service parses only
    the contacts and the sent-mail history; every other dataset file is only checksummed."""
    parsed = []
    original = data_io._read_frame

    def spy(path, columns):
        parsed.append(Path(path).name)
        return original(path, columns)

    monkeypatch.setattr(data_io, "_read_frame", spy)
    control = tmp_path / "policy_copy.json"
    shutil.copyfile(POLICY, control)
    with TestClient(create_app(_paths(tmp_path, policy=control))) as served:
        ready = served.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["T_warn"] == json.loads(POLICY.read_text(encoding="utf-8"))["T_warn"]
        assert served.post("/assess", json=_base()).json()["status"] == "assessed"
    assert sorted(parsed) == ["contacts.csv", "message_recipients.csv", "messages.csv"]
    assert not hasattr(context_module, "read_dataset")
    manifest = json.loads((DATA / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert {"labels.csv", "drafts.csv", "draft_recipients.csv", "split_manifest.csv"} <= set(manifest["files"]) - set(parsed)


def test_health_works_when_bundle_path_is_missing(tmp_path):
    with TestClient(create_app(_paths(tmp_path, features=tmp_path / "nowhere"))) as broken:
        assert broken.get("/health").json()["status"] == "ok"
        ready = broken.get("/ready")
        assert ready.status_code == 503 and ready.json()["ready"] is False


def test_empty_subject_and_body_still_assess_with_limited_text(client):
    body = client.post("/assess", json=_base(subject="", body="")).json()
    assert body["status"] == "assessed"
    for recipient in body["recipients"]:
        codes = [item["code"] for item in recipient["evidence_limitations"]]
        assert "LIMITED_TEXT" in codes
        assert isinstance(recipient["risk_score"], float)


def test_score_equal_to_t_warn_warns_through_the_api(client, dataset, picks, validation_scores):
    """The lowest-scoring warned validation mistake warns through the API too."""
    body = client.post("/assess", json=request_from_draft(dataset, picks["warn"])).json()
    t_warn = json.loads(POLICY.read_text(encoding="utf-8"))["T_warn"]
    assert body["provenance"]["T_warn"] == t_warn
    assert abs(body["email_risk_score"] - float(validation_scores.loc[picks["warn"], "email_risk"])) <= 1e-12
    assert body["email_risk_score"] >= t_warn
    assert body["decision"] == "warn"
    assert body["flagged_recipients"] == [item["address"] for item in body["recipients"] if item["risk_score"] >= t_warn]


def test_routine_validation_draft_allows(client, dataset, picks):
    body = client.post("/assess", json=request_from_draft(dataset, picks["allow"])).json()
    assert body["status"] == "assessed"
    assert body["decision"] == "allow"
    assert body["flagged_recipients"] == []
    assert body["email_risk_score"] == max(item["risk_score"] for item in body["recipients"])
    assert body["draft_reference"] == f"fixture-{picks['allow']}"
    assert body["mode"] == "simulation"


def test_no_block_and_the_model_note_matches_the_model(client, dataset, picks):
    from med_models.package import load_model

    features = load_model(ROOT / DEFAULT_PATHS["model"]).feature_columns
    uses_content = any(name in features for name in CONTENT_FEATURES)
    for draft_id in picks.values():
        body = client.post("/assess", json=request_from_draft(dataset, draft_id)).json()
        assert "block" not in list(_values(body))
        assert body["provenance"]["blocking_enabled"] is False
        if not uses_content:
            assert "CONTENT_RELATIONSHIP_MISMATCH" not in json.dumps(body)
            assert any("Draft-text similarity was not used" in line for line in body["explanation"])
        else:
            assert any("Draft-text similarity" in line and "also an input" in line for line in body["explanation"])
        for item in body["recipients"] or []:
            if not item["flagged"]:
                assert item["reason_codes"] == []


def test_content_code_marks_content_sensitive_warnings(client, dataset, picks):
    """RC-02: a flagged recipient carries CONTENT_RELATIONSHIP_MISMATCH exactly when
    raising only its content cosine to the typical train value would drop it below T_warn."""
    from med_api.context import content_reference
    from med_api.service import content_sensitive
    from med_features.build import read_features
    from med_models.package import load_model

    model = load_model(ROOT / DEFAULT_PATHS["model"])
    reference = content_reference(FEATURES)
    t_warn = json.loads(POLICY.read_text(encoding="utf-8"))["T_warn"]
    features = pd.concat(
        [read_features(FEATURES / f"features_{name}.csv") for name in ("validation_product_like", "validation_diagnostic")],
        ignore_index=True,
    )
    body = client.post("/assess", json=request_from_draft(dataset, picks["warn"])).json()
    assert body["decision"] == "warn"
    frame = features.loc[features["draft_id"] == picks["warn"]]
    contacts = dict(zip(dataset.contacts["email_address"].str.casefold(), dataset.contacts["contact_id"], strict=True))
    seen = 0
    for item in body["recipients"]:
        codes = [code["code"] for code in item["reason_codes"]]
        expected = item["flagged"] and content_sensitive(model, frame, contacts[item["address"]], reference, t_warn)
        assert ("CONTENT_RELATIONSHIP_MISMATCH" in codes) == expected
        seen += int(expected)
    if "content_cosine" in model.feature_columns:
        assert seen >= 1


def test_content_sensitivity_rule_on_fixtures():
    from med_api.service import content_sensitive

    class Stub:
        feature_columns = ["content_cosine"]

        def score_frame(self, frame):
            return 1.0 - frame["content_cosine"].to_numpy()

    base = pd.DataFrame({"contact_id": ["a"], "content_similarity_observed": [1], "content_cosine": [0.05]})
    assert content_sensitive(Stub(), base, "a", 0.4, 0.9) is True
    assert content_sensitive(Stub(), base, "a", 0.4, 0.5) is False
    assert content_sensitive(Stub(), base.assign(content_cosine=0.6), "a", 0.4, 0.9) is False
    assert content_sensitive(Stub(), base.assign(content_similarity_observed=0), "a", 0.4, 0.9) is False
    assert content_sensitive(Stub(), base, "a", None, 0.9) is False
    Stub.feature_columns = ["pair_outbound_count"]
    assert content_sensitive(Stub(), base, "a", 0.4, 0.9) is False


def test_novelty_is_a_limitation_not_a_reason(client, dataset, picks, validation_scores):
    """A first contact carries LIMITED_RELATIONSHIP_HISTORY; novelty is never a reason code."""
    draft_id = picks["first_contact"]
    body = client.post("/assess", json=request_from_draft(dataset, draft_id)).json()
    assert body["status"] == "assessed"
    novel = [item for item in body["recipients"] if "LIMITED_RELATIONSHIP_HISTORY" in [code["code"] for code in item["evidence_limitations"]]]
    assert novel
    for item in body["recipients"]:
        codes = [code["code"] for code in item["reason_codes"]]
        assert "LIMITED_RELATIONSHIP_HISTORY" not in codes
        if not item["flagged"]:
            assert codes == []
    assert (body["decision"] == "warn") == any(item["flagged"] for item in body["recipients"])
    assert (body["decision"] == "warn") == bool(validation_scores.loc[draft_id, "warned"])


def test_feedback_appends_and_does_not_change_the_decision(client, dataset, feedback_dir, picks):
    payload = request_from_draft(dataset, picks["warn"])
    first = client.post("/assess", json=payload).json()
    address = first["recipients"][0]["address"]
    path = feedback_dir / "feedback.jsonl"
    before = path.read_text(encoding="utf-8").count("\n") if path.exists() else 0
    response = client.post("/feedback", json={"request_id": first["request_id"], "recipient": address, "label": "intended"})
    assert response.status_code == 200
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == before + 1
    record = json.loads(lines[-1])
    assert record["label"] == "intended" and "@" not in json.dumps(record)
    second = client.post("/assess", json=payload).json()
    assert second["decision"] == first["decision"]
    assert second["email_risk_score"] == first["email_risk_score"]


def test_feedback_for_unknown_request_or_recipient_writes_nothing(client, feedback_dir):
    path = feedback_dir / "feedback.jsonl"
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    unknown = client.post("/feedback", json={"request_id": "req_missing", "recipient": "sam@demo.example", "label": "unintended"})
    assert unknown.status_code == 422 and unknown.json()["category"] == "invalid_input"
    assessed = client.post("/assess", json=_base()).json()
    stranger = client.post("/feedback", json={"request_id": assessed["request_id"], "recipient": "priya@demo.example", "label": "unintended"})
    assert stranger.status_code == 422
    bad_label = client.post("/feedback", json={"request_id": assessed["request_id"], "recipient": "sam@demo.example", "label": "maybe"})
    assert bad_label.status_code == 422
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    assert after == before


def test_logs_omit_subject_body_and_addresses(client, caplog):
    marker = "ZEBRA-MARKER-4417"
    with caplog.at_level(logging.INFO, logger="med_api"):
        client.post("/assess", json=_base(subject=f"Subject {marker}", body=f"Body {marker}"))
        client.post("/assess", json=_base(to=[{"address": "not-an-email"}], body=marker))
    text = "\n".join(record.getMessage() for record in caplog.records if record.name == "med_api")
    assert text
    assert marker not in text
    assert "@" not in text
    assert "Sam" not in text
    line = format_log_record({"request_id": "r", "status": "assessed", "body": marker, "subject": marker, "address": "sam@demo.example"})
    assert marker not in line and "sam@demo.example" not in line


def test_scoring_timeout_is_unavailable(client, monkeypatch):
    original = decision_module.transform_draft

    def slow(*args, **kwargs):
        time.sleep(0.3)
        return original(*args, **kwargs)

    monkeypatch.setattr(decision_module, "transform_draft", slow)
    monkeypatch.setenv("MED_API_SCORING_TIMEOUT_SECONDS", "0.05")
    response = client.post("/assess", json=_base())
    assert response.status_code == 503
    body = _assert_unable(response, "unavailable")
    assert "timed out" in body["message"]
    time.sleep(0.4)


SECRET = "QUOKKA-SECRET-7731"


def _inject_scorer_runtime_error(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError(f"scorer failed for {SECRET}")

    monkeypatch.setattr(service_module, "assess_draft", explode)


def _inject_scorer_key_error(monkeypatch):
    def explode(*args, **kwargs):
        raise KeyError(f"{SECRET}@demo.example")

    monkeypatch.setattr(service_module, "assess_draft", explode)


def _inject_transform_runtime_error(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError(f"transform failed for {SECRET}")

    monkeypatch.setattr(decision_module, "transform_draft", explode)


def _inject_mapping_key_error(monkeypatch):
    def explode(self, *args, **kwargs):
        raise KeyError(SECRET)

    monkeypatch.setattr(service_module.AssessmentService, "_assessed", explode)


def _inject_mapping_runtime_error(monkeypatch):
    def explode(self, *args, **kwargs):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(service_module.AssessmentService, "_assessed", explode)


@pytest.mark.parametrize(
    "inject",
    [
        _inject_scorer_runtime_error,
        _inject_scorer_key_error,
        _inject_transform_runtime_error,
        _inject_mapping_key_error,
        _inject_mapping_runtime_error,
    ],
)
def test_an_unexpected_scoring_error_is_the_structured_unavailable_failure(client, monkeypatch, caplog, inject):
    inject(monkeypatch)
    with caplog.at_level(logging.INFO, logger="med_api"):
        response = client.post("/assess", json=_base(subject=f"Subject {SECRET}", body=f"Body {SECRET}"))
    assert response.status_code == 503
    body = _assert_unable(response, "unavailable")
    assert body["request_id"].startswith("req_")
    assert body["message"] == service_module.UNEXPECTED_MESSAGE
    # The body carries no draft text, no error text, and no stack trace.
    assert SECRET not in response.text and "Traceback" not in response.text and "scorer failed" not in response.text and "transform failed" not in response.text
    # One log line, allow-listed fields only, and none of the draft or the error text.
    lines = [record.getMessage() for record in caplog.records if record.name == "med_api"]
    assert len(lines) == 1
    assert set(json.loads(lines[0])) <= set(LOG_FIELDS)
    assert json.loads(lines[0])["category"] == "unavailable"
    assert SECRET not in "\n".join(record.getMessage() + str(record.exc_info) for record in caplog.records)


def test_the_service_keeps_assessing_after_an_unexpected_error(client, monkeypatch):
    with monkeypatch.context() as patch:
        _inject_scorer_runtime_error(patch)
        assert client.post("/assess", json=_base()).status_code == 503
    after = client.post("/assess", json=_base())
    assert after.status_code == 200 and after.json()["status"] == "assessed"


def test_the_service_scores_a_sample_of_validation_drafts_exactly_as_the_stored_table(client, dataset, validation_scores):
    """Decisions and scores through the API equal validation_scores.csv: every warned draft and a spread of the rest."""
    table = validation_scores.reset_index()
    warned = table.loc[table["warned"], "draft_id"].tolist()
    rest = table.loc[~table["warned"], "draft_id"].tolist()
    sample = warned + rest[:: max(len(rest) // 40, 1)]
    assert len(warned) == 8 and len(sample) >= 40
    for draft_id in sample:
        body = client.post("/assess", json=request_from_draft(dataset, draft_id)).json()
        assert body["status"] == "assessed"
        assert body["decision"] == ("warn" if validation_scores.loc[draft_id, "warned"] else "allow"), draft_id
        assert abs(body["email_risk_score"] - float(validation_scores.loc[draft_id, "email_risk"])) <= 1e-12, draft_id


def test_every_dataset_file_is_still_checksummed_before_the_serving_tables_are_parsed(tmp_path):
    copy = tmp_path / "data"
    shutil.copytree(DATA, copy)
    read_serving_tables(copy)
    for name in ("labels.csv", "drafts.csv", "quality_report.json", "messages.csv"):
        target = copy / name
        original = target.read_bytes()
        target.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with pytest.raises(AssertionError, match=f"Checksum mismatch for {name}"):
            read_serving_tables(copy)
        target.write_bytes(original)
    read_serving_tables(copy)


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def test_the_phase_6_report_reads_the_frozen_record_without_its_per_draft_members(tmp_path):
    """`stored_results` cuts the sealed members out of the text, so unparseable per-draft content is harmless."""
    from med_policy.report import stored_results

    sentinel = "SEALED-SENTINEL-4471"
    broken = '[{"draft_id": "d000001", "note": "' + sentinel + '", NOT JSON <<< }]'
    record = (
        '{"policy_version": "p", "subsets": {"test_product_like": {"policy": {"cutoff": 0.5}, "outcomes": ' + broken + ', '
        '"slices": {"email_by_scenario": [{"slice": "S01", "misdirected": 2, "warned_misdirected": 0}], "examples": ' + broken + '}}}, '
        '"examples_validation": ' + broken + "}"
    )
    with pytest.raises(json.JSONDecodeError):
        json.loads(record)
    shutil.copyfile(POLICY, tmp_path / "policy.json")
    (tmp_path / "test_evaluation.json").write_text(record, encoding="utf-8")
    results = stored_results(tmp_path)
    assert results["test"]["subsets"]["test_product_like"]["slices"]["email_by_scenario"][0]["misdirected"] == 2
    assert sentinel not in json.dumps(results) and not {"outcomes", "examples", "examples_validation"} & set(_keys(results["test"]))
    # Without a frozen record there is no test result.
    (tmp_path / "no_test").mkdir()
    shutil.copyfile(POLICY, tmp_path / "no_test" / "policy.json")
    assert stored_results(tmp_path / "no_test")["test"] is None


def test_the_phase_6_scoring_flow_page_is_what_the_generator_writes_from_aggregates_only():
    """The page equals the generator's output for the stored aggregates; no per-draft outcome is read to write it."""
    from med_api.report import _flow, _limits
    from med_policy.report import stored_results

    results = stored_results(POLICY.parent)
    assert not {"outcomes", "examples", "examples_validation"} & set(_keys(results["test"]))
    latency = json.loads((ROOT / "artifacts/med-api-latency" / json.loads(POLICY.read_text(encoding="utf-8"))["policy_version"] / "latency.json").read_text(encoding="utf-8"))
    page = (ROOT / "docs/phase_6/SCORING_FLOW.md").read_text(encoding="utf-8")
    assert _flow(latency, results) == page
    assert "- Scenarios never warned in the frozen test subsets: S01, S04, S11. The API does not change that." in _limits(results)
    assert "Scenarios never warned in the frozen test subsets: S01, S04, S11." in page


def test_no_frozen_test_writer_or_fixture(dataset):
    for path in (ROOT / "src" / "med_api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("features_test_product_like", "features_test_diagnostic", "test_evaluation", "run_frozen_evaluation", "in_memory_table"):
            assert forbidden not in text, (path, forbidden)
    frozen = dataset.drafts.loc[dataset.drafts["subset"] == "test_product_like", "draft_id"].iloc[0]
    with pytest.raises(FixtureError, match="frozen"):
        request_from_draft(dataset, frozen)
    assert not list(FEATURES.glob("features_test_*"))


def test_latency_path_is_keyed_by_bundle_and_never_overwrites(tmp_path):
    from med_api.latency import LatencyError, measure
    from med_api.version import LATENCY_PATH
    from med_policy.version import POLICY_VERSION

    assert LATENCY_PATH.parts[-2] == POLICY_VERSION
    assert LATENCY_PATH != Path("artifacts") / "med-api-v1" / "latency.json"
    existing = tmp_path / "latency.json"
    existing.write_text("{}", encoding="utf-8")
    with pytest.raises(LatencyError, match="not overwritten"):
        measure(_paths(tmp_path), existing)
    assert existing.read_text(encoding="utf-8") == "{}"


def test_latency_workload_covers_the_whole_subset_in_a_fixed_order(dataset):
    import numpy as np

    from med_api.fixtures import validation_draft_ids
    from med_api.latency import WORKLOAD_SEED, _workload_mix

    ids = validation_draft_ids(dataset, "validation_product_like")
    order = np.random.default_rng(WORKLOAD_SEED).permutation(len(ids))
    assert sorted(order.tolist()) == list(range(len(ids)))
    mix = _workload_mix(dataset, [ids[index] for index in order])
    assert sum(mix["recipients"].values()) == len(ids)
    assert sum(mix["months"].values()) == len(ids)
    assert sum(mix["sender_history_messages"]["bands"].values()) == len(ids)
    assert len(mix["months"]) > 1
