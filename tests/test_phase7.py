"""Phase 7 UI: request fields, curated examples, stale results, rendering, exploration, feedback."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.normalize import denied_fields
from med_api.version import DEFAULT_PATHS
from med_data.calendar import FROZEN_SUBSETS
from med_ui import exploration as xp
from med_ui import presentation as pres
from med_ui.client import ApiClient, ApiResponse
from med_ui.config import EXAMPLE_RULES, EXAMPLE_SUBSETS, REQUEST_FIELDS, ExampleRule
from med_ui.examples import (
    FrozenSubsetError,
    display_names,
    invalid_address_form,
    load_catalog,
    select_draft,
    unknown_address_form,
)
from med_ui.walkthrough import generate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / DEFAULT_PATHS["data"]
POLICY = ROOT / DEFAULT_PATHS["policy"]
POLICY_DIR = POLICY.parent
UI_SRC = ROOT / "src" / "med_ui"
APP = UI_SRC / "app.py"
FORBIDDEN_IMPORTS = ("med_policy.decision", "med_models", "med_features.transform", "med_api.service", "med_api.app", "med_api.context")


class CountingHttp:
    """Delegates to an httpx client and records each (method, path, json body)."""

    def __init__(self, http):
        self.http = http
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get("json")))
        return self.http.request(method, path, **kwargs)

    def count(self, method, path):
        return sum(1 for call in self.calls if call[:2] == (method, path))


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    paths = replace(ApiPaths.from_env(ROOT), feedback=tmp_path_factory.mktemp("feedback") / "feedback.jsonl")
    with TestClient(create_app(paths)) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def client(api):
    return ApiClient(http=api)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(DATA, POLICY_DIR)


@pytest.fixture(scope="module")
def names(catalog):
    return display_names(catalog.contacts)


@pytest.fixture(scope="module")
def exploration():
    return xp.load_exploration(POLICY_DIR)


@pytest.fixture(scope="module")
def assessed(client, catalog, names):
    """One live API assessment per curated example."""
    out = {}
    for key, example in catalog.examples.items():
        request = pres.build_request(example.form, names)
        out[key] = (request, client.assess(request))
    return out


def _values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _values(item)
    else:
        yield value


def _assert_clean_wording(lines):
    text = "\n".join(lines).casefold()
    assert "probability" not in text
    for match in re.finditer(r"probabilit", text):
        assert text[max(0, match.start() - 4) : match.start()] == "not "
    assert re.search(r"\bblock\b", text) is None


# ----------------------------------------------------------------- requests


def test_requests_carry_only_phase1_fields(catalog, names):
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(503, json={"status": "unable_to_assess", "category": "unavailable", "message": "stub"})

    stub = ApiClient(http=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://stub"))
    forms = [example.form for example in catalog.examples.values()]
    forms += [unknown_address_form(catalog), invalid_address_form(catalog)]
    for form in forms:
        stub.assess(pres.build_request(form, names))
    assert len(sent) == len(forms)
    drafts = catalog.drafts.set_index("draft_id")
    hidden = set()
    for example in catalog.examples.values():
        row = drafts.loc[example.draft_id]
        hidden |= {example.draft_id, row["family_id"], row["scenario_id"], row["scenario_variant"], row["subset"], row["split"]}
    for payload in sent:
        assert set(payload) == set(REQUEST_FIELDS)
        assert denied_fields(payload) == []
        for value in _values(payload):
            if isinstance(value, str):
                assert value not in hidden
                assert not any(token in value for token in hidden if token.startswith(("fam_", "d0")))
    with pytest.raises(ValueError, match="Phase 1"):
        stub.assess({**pres.build_request(forms[0], names), "scenario_id": "S01"})
    with pytest.raises(ValueError, match="Phase 1"):
        stub.assess({**pres.build_request(forms[0], names), "draft_reference": "x"})


# ------------------------------------------------------------------ examples


def test_curated_examples_come_from_validation_by_rule(catalog):
    assert not catalog.unmatched
    required = {"routine", "added_recipient", "lookalike_miss", "topic_miss", "first_contact_miss", "first_contact", "topic_change", "cold_start"}
    assert required <= set(catalog.examples)
    assert set(catalog.drafts["subset"]) <= set(EXAMPLE_SUBSETS)
    assert not catalog.drafts["is_walkthrough"].eq("true").any()
    scores = pd.read_csv(POLICY_DIR / "validation_scores.csv", float_precision="round_trip").set_index("draft_id")
    drafts = catalog.drafts.set_index("draft_id")
    for key, example in catalog.examples.items():
        rule = example.rule
        assert example.subset in EXAMPLE_SUBSETS
        assert catalog.subset_of[example.draft_id] == rule.subset
        assert drafts.loc[example.draft_id, "scenario_id"] in rule.scenario_ids
        assert bool(scores.loc[example.draft_id, "misdirected"]) == rule.misdirected
        assert bool(scores.loc[example.draft_id, "warned"]) == (rule.stored_decision == "warn")
        # Re-applying the rule gives the same draft.
        assert select_draft(rule, catalog.drafts, catalog.draft_recipients, scores.reset_index())[0] == example.draft_id


def test_frozen_subset_drafts_are_refused(catalog):
    for subset in FROZEN_SUBSETS:
        frozen = next(draft for draft, name in catalog.subset_of.items() if name == subset)
        with pytest.raises(FrozenSubsetError):
            catalog.form_for(frozen)
    rule = ExampleRule(
        key="x", title="x", subset="test_diagnostic", scenario_ids=("S01",), variants=("lookalike_replacement",),
        misdirected=True, stored_decision="allow", pick="highest", rule="x",
    )
    with pytest.raises(FrozenSubsetError):
        select_draft(rule, catalog.drafts, catalog.draft_recipients, pd.DataFrame(columns=["draft_id", "email_risk", "misdirected", "warned"]))


def test_catalog_never_materializes_frozen_records(monkeypatch):
    """At the file-read boundary: the draft-keyed tables are streamed, and only validation records are kept."""
    import med_ui.examples as examples_module

    frozen = set(pd.read_csv(DATA / "split_manifest.csv", usecols=["draft_id", "subset"]).query("subset in @FROZEN_SUBSETS")["draft_id"])
    assert frozen
    read_paths = []
    original_read_csv = examples_module.pd.read_csv

    def spy_read_csv(path, *args, **kwargs):
        read_paths.append(Path(path).name)
        return original_read_csv(path, *args, **kwargs)

    kept = []
    original_stream = examples_module.stream_rows

    def spy_stream(path, keep_ids):
        assert not (keep_ids & frozen)
        frame = original_stream(path, keep_ids)
        kept.append((Path(path).name, set(frame["draft_id"])))
        return frame

    monkeypatch.setattr(examples_module.pd, "read_csv", spy_read_csv)
    monkeypatch.setattr(examples_module, "stream_rows", spy_stream)
    catalog = examples_module.load_catalog(DATA, POLICY_DIR)
    # No whole-table read of a draft-keyed table, which would hold frozen rows.
    assert not {"drafts.csv", "draft_recipients.csv", "labels.csv"} & set(read_paths)
    assert sorted(name for name, _ in kept) == ["draft_recipients.csv", "drafts.csv", "labels.csv"]
    for name, ids in kept:
        assert ids and not (ids & frozen), name
    assert not (set(catalog.drafts["draft_id"]) & frozen)
    assert set(catalog.drafts["subset"]) <= set(EXAMPLE_SUBSETS)


def test_ui_source_has_no_draft_ids_or_version_strings():
    for path in UI_SRC.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert re.search(r"\bd\d{6}\b", text) is None, path.name
        assert "fam_" not in text, path.name
        assert re.search(r"med-(synth|features|model|policy|api)-v\d", text) is None, path.name
    for rule in EXAMPLE_RULES:
        assert rule.subset in EXAMPLE_SUBSETS


# -------------------------------------------------------------- stale results


def test_edited_draft_hides_the_previous_decision(client, catalog, names):
    form = catalog.examples["added_recipient"].form
    request = pres.build_request(form, names)
    record = pres.AssessmentRecord(pres.fingerprint(request), client.assess(request))
    assert pres.result_view(record, pres.fingerprint(request)).decision == "warn"
    flagged = pres.result_view(record, pres.fingerprint(request)).flagged
    edits = [
        replace(form, subject=form.subject + " (edited)"),
        replace(form, body=form.body + "\nOne more line."),
        replace(form, draft_timestamp="2025-06-01T09:00:00Z"),
        replace(form, cc=tuple(item for item in form.cc if item not in flagged)),
        replace(form, bcc=form.cc, cc=()),
        replace(form, to=form.to + ("priya@demo.example",)),
        replace(form, sender="noah@demo.example"),
    ]
    for edited in edits:
        view = pres.result_view(record, pres.fingerprint(pres.build_request(edited, names)))
        assert view.kind == "stale"
        assert view.decision is None and view.email_risk_score is None and view.recipients == ()
        text = " ".join(pres.view_lines(view)).casefold()
        assert "allow" not in text and "warn" not in text
    # Removing the flagged recipient is a new request with its own result.
    removed = replace(form, cc=tuple(item for item in form.cc if item not in flagged))
    new_request = pres.build_request(removed, names)
    fresh = pres.result_view(pres.AssessmentRecord(pres.fingerprint(new_request), client.assess(new_request)), pres.fingerprint(new_request))
    assert fresh.kind == "assessed" and fresh.decision in ("allow", "warn")


# ---------------------------------------------------------------- rendering


def test_unable_to_assess_renders_no_decision_score_or_table(client, catalog, names):
    cases = {
        "unavailable": pres.build_request(unknown_address_form(catalog), names),
        "invalid_input": pres.build_request(invalid_address_form(catalog), names),
    }
    views = []
    for category, request in cases.items():
        response = client.assess(request)
        assert response.body["status"] == "unable_to_assess" and response.body["category"] == category
        views.append(pres.response_view(response))
    views.append(pres.response_view(ApiResponse(status_code=None, body=None, error="ConnectError: refused")))
    for view in views:
        assert view.kind == "unable"
        assert view.decision is None and view.email_risk_score is None and view.email_risk_text is None
        assert view.recipients == () and pres.recipient_table(view) == []
        text = " ".join(pres.view_lines(view)).casefold()
        assert "allow" not in text
        assert "risk score:" not in text
        _assert_clean_wording(pres.view_lines(view))
    assert pres.DIRECTORY_SENTENCE in views[0].detail
    assert pres.DIRECTORY_SENTENCE not in views[1].detail


def test_warned_response_renders_exactly_the_api_codes(assessed):
    body = assessed["added_recipient"][1].body
    assert body["decision"] == "warn" and body["flagged_recipients"]
    view = pres.response_view(assessed["added_recipient"][1])
    assert list(view.flagged) == body["flagged_recipients"]
    assert [row.address for row in view.recipients] == [item["address"] for item in body["recipients"]]
    sent_codes = set()
    for row, item in zip(view.recipients, body["recipients"], strict=True):
        assert row.flagged == item["flagged"]
        assert [(line.code, line.text) for line in row.codes] == [(code["code"], code["text"]) for code in item["reason_codes"]]
        assert [(line.code, line.text) for line in row.limitations] == [(code["code"], code["text"]) for code in item["evidence_limitations"]]
        sent_codes |= {code["code"] for code in item["reason_codes"] + item["evidence_limitations"]}
    flagged_rows = [row for row in view.recipients if row.flagged]
    assert {row.address for row in flagged_rows} == set(body["flagged_recipients"])
    assert all(row.codes for row in flagged_rows)
    shown = set(re.findall(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b", "\n".join(pres.view_lines(view))))
    assert shown <= sent_codes
    assert list(view.explanation) == body["explanation"]

    # A code the UI does not know is shown as sent, not dropped or renamed; nothing is added.
    stub = json.loads(json.dumps(body))
    stub["recipients"][0]["reason_codes"] = [{"code": "SOME_NEW_CODE", "text": "Sent by the service."}]
    stub["recipients"][0]["evidence_limitations"] = []
    row = pres.response_view(ApiResponse(200, stub)).recipients[0]
    assert [(line.code, line.text) for line in row.codes] == [("SOME_NEW_CODE", "Sent by the service.")]
    assert row.limitations == ()


def test_displayed_decision_is_the_api_decision_and_exploration_never_changes_it(assessed, exploration):
    for key, (_, response) in assessed.items():
        before = pres.response_view(response)
        assert before.kind == "assessed", key
        assert before.decision == response.body["decision"]
        assert before.email_risk_score == response.body["email_risk_score"]
        for cutoff in xp.cutoff_options(exploration):
            xp.counts_at(exploration, cutoff)
            xp.position_of(exploration, before.email_risk_score)
            assert pres.response_view(response) == before


def test_known_misses_are_shown_as_allowed(assessed, catalog):
    for key in ("lookalike_miss", "topic_miss", "first_contact_miss"):
        view = pres.response_view(assessed[key][1])
        assert view.decision == "allow", key
        assert catalog.examples[key].rule.misdirected and catalog.examples[key].story.recorded


def test_rendered_text_never_says_probability_or_block_as_an_outcome(assessed, client, exploration):
    lines = []
    for _, response in assessed.values():
        lines += pres.view_lines(pres.response_view(response))
    lines += [label + " " + value for label, value in pres.readiness_view(client.ready(), xp.expected_bundle(exploration)).items]
    lines += xp.exploration_notes(exploration) + [xp.counts_sentence(row) for row in xp.tradeoff_rows(exploration)]
    _assert_clean_wording(lines)
    # A response claiming a block is not rendered as a decision.
    body = json.loads(json.dumps(assessed["added_recipient"][1].body))
    body["decision"] = "block"
    view = pres.response_view(ApiResponse(200, body))
    assert view.kind == "unable" and view.decision is None
    _assert_clean_wording(pres.view_lines(view))


def _ready_body(expected, **changes) -> dict:
    body = {
        "ready": True,
        "contract_version": expected.contract_version,
        "snapshot_id": expected.snapshot_id,
        "model_version": expected.model_version,
        "feature_spec_version": expected.feature_spec_version,
        "policy_version": expected.policy_version,
        "T_warn": expected.t_warn,
        "blocking_enabled": False,
    }
    body.update(changes)
    return body


def test_readiness_requires_the_local_bundle_and_cutoff(client, exploration):
    expected = xp.expected_bundle(exploration)
    assert pres.readiness_view(client.ready(), expected).ok
    assert pres.readiness_view(ApiResponse(200, _ready_body(expected)), expected).ok
    for changes in (
        {"policy_version": "other-policy"},
        {"model_version": "other-model"},
        {"feature_spec_version": "other-features"},
        {"T_warn": 0.5},
        {"T_warn": expected.t_warn - 1e-12},
        {"snapshot_id": "other-snapshot"},
        {"contract_version": "other-contract"},
        {"blocking_enabled": True},
        {"ready": False},
    ):
        view = pres.readiness_view(ApiResponse(200, _ready_body(expected, **changes)), expected)
        assert not view.ok, changes


def test_response_from_another_bundle_shows_no_decision(assessed, exploration):
    expected = xp.expected_bundle(exploration)
    body = assessed["added_recipient"][1].body
    assert pres.response_view(ApiResponse(200, body), expected).kind == "assessed"
    for key, value in (("policy_version", "other-policy"), ("T_warn", 0.5), ("model_version", "other-model")):
        changed = json.loads(json.dumps(body))
        changed["provenance"][key] = value
        view = pres.response_view(ApiResponse(200, changed), expected)
        assert view.kind == "unable" and view.decision is None and view.email_risk_score is None


def _malformed_bodies(body: dict) -> dict:
    def change(fn):
        copy = json.loads(json.dumps(body))
        fn(copy)
        return copy

    return {
        "blocking enabled": change(lambda b: b["provenance"].update(blocking_enabled=True)),
        "blocking missing": change(lambda b: b["provenance"].pop("blocking_enabled")),
        "not simulation": change(lambda b: b.update(mode="live")),
        "recipient score text": change(lambda b: b["recipients"][0].update(risk_score="high")),
        "recipient score above one": change(lambda b: b["recipients"][0].update(risk_score=1.5)),
        "email score missing": change(lambda b: b.pop("email_risk_score")),
        "warn without flagged": change(lambda b: (b.update(flagged_recipients=[]), [r.update(flagged=False) for r in b["recipients"]])),
        "flagged list mismatch": change(lambda b: b.update(flagged_recipients=[b["recipients"][0]["address"]])),
        "flagged not boolean": change(lambda b: b["recipients"][0].update(flagged="yes")),
        "bad roles": change(lambda b: b["recipients"][0].update(roles=["reply-to"])),
        "codes not objects": change(lambda b: b["recipients"][1].update(reason_codes=["EXTERNAL_RECIPIENT"])),
        "recipient not object": change(lambda b: b["recipients"].__setitem__(0, "someone")),
        "no recipients": change(lambda b: b.update(recipients=[])),
        "explanation missing": change(lambda b: b.pop("explanation")),
        "provenance missing": change(lambda b: b.pop("provenance")),
        "block decision": change(lambda b: b.update(decision="block")),
    }


def test_malformed_assessed_responses_show_no_decision_and_never_raise(assessed, exploration):
    expected = xp.expected_bundle(exploration)
    body = assessed["added_recipient"][1].body
    for name, bad in _malformed_bodies(body).items():
        for view in (pres.response_view(ApiResponse(200, bad), expected), pres.response_view(ApiResponse(200, bad))):
            assert view.kind == "unable" and view.category == "unexpected_response", name
            assert view.decision is None and view.email_risk_score is None and view.recipients == (), name
            assert "allow" not in " ".join(pres.view_lines(view)).casefold(), name
    unknown = {"status": "unable_to_assess", "category": "maybe", "message": "?"}
    assert pres.response_view(ApiResponse(503, unknown)).category == "unexpected_response"


# -------------------------------------------------------------- exploration


def test_exploration_reads_only_validation_scores_and_matches_the_policy(tmp_path):
    for name in ("validation_scores.csv", "policy.json"):
        shutil.copy(POLICY_DIR / name, tmp_path / name)
    data = xp.load_exploration(tmp_path)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    confusion = policy["validation_confusion"]["email"]
    at_default = xp.counts_at(data, data.t_warn)
    assert at_default["is_policy"]
    assert data.t_warn == policy["T_warn"]
    assert at_default["warned_mistakes"] == confusion["true_positives"]
    assert at_default["false_warnings"] == confusion["false_positives"]
    assert at_default["mistakes"] == confusion["positives"]
    assert at_default["legitimate"] == confusion["legitimate"]
    assert data.subset == policy["selection"]["subset"]
    assert data.t_warn in xp.cutoff_options(data)
    rows = xp.tradeoff_rows(data)
    assert rows[0] == at_default and all(row["cutoff"] < data.t_warn for row in rows[1:])
    source = (UI_SRC / "exploration.py").read_text(encoding="utf-8")
    assert "test_evaluation" not in source and "test_product_like" not in source


# ----------------------------------------------------------------- feedback


def test_feedback_posts_once_per_click_and_changes_nothing(api, catalog, names):
    spy = CountingHttp(api)
    counted = ApiClient(http=spy)
    request = pres.build_request(catalog.examples["added_recipient"].form, names)
    first = pres.response_view(counted.assess(request))
    target = first.flagged[0]
    note = pres.feedback_note(counted.feedback(first.request_id, target, "unintended"))
    assert spy.count("POST", "/feedback") == 1
    assert "not a label until reviewed" in note
    again = pres.response_view(counted.assess(request))
    assert (again.decision, again.email_risk_score, again.flagged) == (first.decision, first.email_risk_score, first.flagged)
    assert spy.count("POST", "/feedback") == 1


# ------------------------------------------------------------------ imports


def test_ui_modules_do_not_import_scoring_internals():
    for path in UI_SRC.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                assert not any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN_IMPORTS), f"{path.name} imports {name}"
    # Every module the UI loads from the scoring packages must be a package
    # marker or a version module. Any other module (scoring, estimators,
    # transforms, the API app or service) fails this check.
    probe = (
        "import sys, med_ui.client, med_ui.config, med_ui.examples, med_ui.exploration, med_ui.presentation, med_ui.walkthrough, med_ui.cli\n"
        "print('\\n'.join(sorted(m for m in sys.modules if m.split('.')[0] in ('med_models', 'med_features', 'med_policy', 'med_api'))))"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT, check=True)
    loaded = set(result.stdout.split())
    allowed = {
        "med_models", "med_models.version", "med_features", "med_features.version",
        "med_policy", "med_policy.version", "med_api", "med_api.version", "med_api.fixtures",
    }
    assert loaded and loaded <= allowed, sorted(loaded - allowed)


def test_package_version_and_ui_extra():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == "0.7.0"
    assert any(item.startswith("streamlit") for item in project["optional-dependencies"]["ui"])
    assert not any(item.startswith("streamlit") for item in project["dependencies"])


# --------------------------------------------------------------- walkthrough


def test_walkthrough_document_is_reproducible_from_the_api(client, catalog):
    text = generate(client, DATA, POLICY_DIR)
    assert text == (ROOT / "docs" / "phase_7" / "WALKTHROUGH.md").read_text(encoding="utf-8")
    shown = set(re.findall(r"\bd\d{6}\b", text))
    assert shown and all(catalog.subset_of[draft] in EXAMPLE_SUBSETS for draft in shown)
    _assert_clean_wording(text.splitlines())


# ------------------------------------------------------------- Streamlit app


def _app_texts(at) -> list[str]:
    texts = []
    for group in (at.title, at.header, at.subheader, at.markdown, at.caption, at.success, at.info, at.warning, at.error):
        texts += [str(element.value) for element in group]
    for metric in at.metric:
        texts += [str(metric.label), str(metric.value)]
    for frame in at.dataframe:
        texts += [str(frame.value.to_dict())]
    return texts


def _app(monkeypatch, http):
    testing = pytest.importorskip("streamlit.testing.v1")
    import med_ui.client as client_module

    monkeypatch.setenv("MED_UI_ROOT", str(ROOT))
    monkeypatch.setattr(client_module, "make_client", lambda settings: ApiClient(http=http))
    return testing.AppTest.from_file(str(APP), default_timeout=60)


def test_app_disables_assessment_when_the_service_is_unavailable(monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    at = _app(monkeypatch, httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://stub"))
    at.run()
    assert not at.exception
    assert any("unavailable" in element.value for element in at.error)
    assert at.button(key="assess").disabled


def test_app_assesses_marks_stale_and_posts_feedback_once(monkeypatch, api, catalog, names):
    spy = CountingHttp(api)
    at = _app(monkeypatch, spy)
    at.run()
    assert not at.exception
    at.selectbox(key="example_choice").set_value("added_recipient").run()
    at.button(key="load_example").click().run()
    at.button(key="assess").click().run()
    assert not at.exception
    assert any("Simulated decision: warn" in element.value for element in at.warning)
    texts = _app_texts(at)
    assert any("CONTENT_RELATIONSHIP_MISMATCH" in text for text in texts)
    _assert_clean_wording(texts)
    assessments = spy.count("POST", "/assess")

    # The flagged recipient's position, from a direct API call outside the counted client.
    direct = pres.response_view(ApiClient(http=api).assess(pres.build_request(catalog.examples["added_recipient"].form, names)))
    index = next(i for i, row in enumerate(direct.recipients) if row.flagged)
    at.button(key=f"fb_{index}_unintended").click().run()
    assert spy.count("POST", "/feedback") == 1
    assert spy.count("POST", "/assess") == assessments
    assert any("not a label until reviewed" in text for text in _app_texts(at))

    at.text_input(key="f_subject").input("Edited subject").run()
    texts = _app_texts(at)
    assert any(pres.STALE_HEADLINE in text for text in texts)
    assert not any("Simulated decision" in text for text in texts)
    assert spy.count("POST", "/assess") == assessments


def test_app_shows_no_decision_for_a_malformed_response(monkeypatch, assessed, exploration):
    expected = xp.expected_bundle(exploration)
    bad = _malformed_bodies(assessed["added_recipient"][1].body)["blocking enabled"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/ready":
            return httpx.Response(200, json=_ready_body(expected))
        return httpx.Response(200, json=bad)

    at = _app(monkeypatch, httpx.Client(transport=httpx.MockTransport(handler), base_url="http://stub"))
    at.run()
    assert not at.exception and not at.button(key="assess").disabled
    at.button(key="assess").click().run()
    assert not at.exception
    texts = _app_texts(at)
    assert any(pres.UNABLE_HEADLINE in text for text in texts)
    assert not any("Simulated decision" in text for text in texts)
    assert not at.metric


def test_app_disables_assessment_for_another_bundle(monkeypatch, exploration):
    expected = xp.expected_bundle(exploration)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ready_body(expected, policy_version="other-policy", T_warn=0.5))

    at = _app(monkeypatch, httpx.Client(transport=httpx.MockTransport(handler), base_url="http://stub"))
    at.run()
    assert not at.exception
    assert at.button(key="assess").disabled
    assert any("different contract, snapshot, or bundle" in element.value for element in at.error)
