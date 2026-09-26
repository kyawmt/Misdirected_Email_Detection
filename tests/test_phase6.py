"""Phase 6 API contract: normalizer, failures, codes, feedback, and logging."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import med_policy.decision as decision_module
from med_data.io import read_dataset
from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.fixtures import FixtureError, request_from_draft
from med_api.service import format_log_record

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "med-synth-v2"
POLICY = ROOT / "artifacts" / "med-policy-v1" / "policy.json"
WARN_DRAFT = "d001019"
ROUTINE_DRAFT = "d001083"
FIRST_CONTACT_DRAFT = "d001065"


def _paths(tmp: Path, **changes) -> ApiPaths:
    paths = ApiPaths(
        policy=POLICY,
        model=ROOT / "artifacts" / "med-model-v1" / "model.joblib",
        features=ROOT / "artifacts" / "med-features-v1",
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


def _base(**changes) -> dict:
    payload = {
        "draft_timestamp": "2025-05-05T09:30:00Z",
        "sender": {"address": "maya@demo.example", "display_name": "Maya"},
        "to": [{"address": "sam@demo.example", "display_name": "Sam"}],
        "cc": [],
        "bcc": [],
        "subject": "Facilities walkthrough",
        "body": "Can we confirm the badge list for the walkthrough on Thursday?",
        "context_snapshot_id": "med-synth-v2",
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
    assert body["contract_version"] == "med-api-v1"
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


def test_contact_listed_after_the_cutoff_is_unavailable(client):
    # jordan@demo.example is listed in the directory from 2025-12-31.
    response = client.post("/assess", json=_base(to=[{"address": "jordan@demo.example"}]))
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


def test_score_equal_to_t_warn_warns_through_the_api(client, dataset):
    body = client.post("/assess", json=request_from_draft(dataset, WARN_DRAFT)).json()
    t_warn = json.loads(POLICY.read_text(encoding="utf-8"))["T_warn"]
    assert body["provenance"]["T_warn"] == t_warn
    assert body["email_risk_score"] >= t_warn
    assert body["decision"] == "warn"
    assert body["flagged_recipients"] == [item["address"] for item in body["recipients"] if item["risk_score"] >= t_warn]


def test_routine_validation_draft_allows(client, dataset):
    body = client.post("/assess", json=request_from_draft(dataset, ROUTINE_DRAFT)).json()
    assert body["status"] == "assessed"
    assert body["decision"] == "allow"
    assert body["flagged_recipients"] == []
    assert body["email_risk_score"] == max(item["risk_score"] for item in body["recipients"])
    assert body["draft_reference"] == f"fixture-{ROUTINE_DRAFT}"
    assert body["mode"] == "simulation"


def test_no_block_and_no_content_code(client, dataset):
    for draft_id in (WARN_DRAFT, ROUTINE_DRAFT, FIRST_CONTACT_DRAFT):
        body = client.post("/assess", json=request_from_draft(dataset, draft_id)).json()
        assert "block" not in list(_values(body))
        assert body["provenance"]["blocking_enabled"] is False
        assert "CONTENT_RELATIONSHIP_MISMATCH" not in json.dumps(body)
        assert any("Draft-text similarity was not used" in line for line in body["explanation"])


def test_allowed_novel_recipient_is_not_warned_for_novelty(client, dataset):
    body = client.post("/assess", json=request_from_draft(dataset, FIRST_CONTACT_DRAFT)).json()
    assert body["status"] == "assessed"
    novel = [item for item in body["recipients"] if "LIMITED_RELATIONSHIP_HISTORY" in [code["code"] for code in item["evidence_limitations"]]]
    assert novel
    assert body["decision"] == "allow"
    assert all(not item["flagged"] and item["reason_codes"] == [] for item in novel)


def test_feedback_appends_and_does_not_change_the_decision(client, dataset, feedback_dir):
    payload = request_from_draft(dataset, WARN_DRAFT)
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


def test_no_frozen_test_writer_or_fixture(dataset):
    for path in (ROOT / "src" / "med_api").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("features_test_product_like", "features_test_diagnostic", "test_evaluation", "run_frozen_evaluation", "in_memory_table"):
            assert forbidden not in text, (path, forbidden)
    frozen = dataset.drafts.loc[dataset.drafts["subset"] == "test_product_like", "draft_id"].iloc[0]
    with pytest.raises(FixtureError, match="frozen"):
        request_from_draft(dataset, frozen)
    assert not list((ROOT / "artifacts" / "med-features-v1").glob("features_test_*"))
