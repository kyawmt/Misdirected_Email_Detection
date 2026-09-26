"""Phase 5 policy contract: selection scope, decisions, load checks, and the one-shot test."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from med_data.io import read_dataset
from med_features.build import queries_for
from med_features.profiles import directory_from_dataset, history_index_from_dataset
from med_features.schema import FeatureError
from med_features.text_model import FittedText
from med_features.transform import query_from_dataset
from med_policy.decision import PolicyBundle, assess_draft, decide, load_bundle, try_load_bundle
from med_policy.evaluate import clopper_pearson, operating_point
from med_policy.pipeline import TEST_EVALUATION_FILE, run_frozen_evaluation, run_selection
from med_policy.select import email_scores, select_cutoff
from med_policy.version import POLICY_VERSION, PolicyError

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "artifacts" / POLICY_VERSION
MODEL = ROOT / "artifacts" / "med-model-v1" / "model.joblib"
FEATURES = ROOT / "artifacts" / "med-features-v1"
MANIFEST = FEATURES / "artifact_manifest.json"
DATA = ROOT / "data" / "med-synth-v2"


def _table(rows, subset="validation_product_like"):
    """rows: (draft_id, contact_id, positive, score)."""
    frame = pd.DataFrame(rows, columns=["draft_id", "contact_id", "positive", "risk_score"])
    frame["subset"] = subset
    frame["family_id"] = "fam_" + frame["draft_id"]
    frame["scenario_id"] = "S05"
    frame["assessed"] = True
    frame["recipient_order"] = 0
    frame["addressed_recipient_count"] = frame.groupby("draft_id")["contact_id"].transform("size")
    frame["recipient_is_internal"] = 1
    frame["recipient_novel_to_sender"] = 0
    return frame


def _bundle(t_warn: float) -> PolicyBundle:
    policy = {"model_version": "med-model-v1", "feature_spec_version": "med-features-v1", "policy_version": POLICY_VERSION}
    return PolicyBundle(policy=policy, model=None, t_warn=t_warn)


def _scores(pairs):
    return pd.DataFrame(pairs, columns=["contact_id", "risk_score"])


def test_cutoff_search_uses_validation_only():
    table = _table([("d1", "a", True, 0.9), ("d2", "a", False, 0.4), ("d3", "a", True, 0.3), ("d4", "a", False, 0.1)])
    result = select_cutoff(email_scores(table), "validation_product_like")
    assert result["chosen"]["cutoff"] == pytest.approx(0.9)
    assert result["chosen"]["false_interventions"] == 0
    assert result["chosen"]["recall"] == pytest.approx(0.5)
    with pytest.raises(PolicyError, match="frozen"):
        select_cutoff(email_scores(table), "test_product_like")
    with pytest.raises(PolicyError, match="only"):
        select_cutoff(email_scores(table), "validation_diagnostic")
    mislabeled = email_scores(_table([("d1", "a", True, 0.9), ("d2", "a", False, 0.1)], subset="test_diagnostic"))
    with pytest.raises(PolicyError, match="tagged"):
        select_cutoff(mislabeled, "validation_product_like")


def test_cutoff_can_warn_on_nobody_and_ties_keep_the_highest():
    table = _table([("d1", "a", True, 0.2), ("d2", "a", False, 0.9)])
    result = select_cutoff(email_scores(table), "validation_product_like")
    assert result["recall_is_zero"]
    assert result["chosen"]["cutoff"] > 0.9
    assert result["chosen"]["warnings"] == 0


def test_threshold_equality_warns_and_below_allows():
    bundle = _bundle(0.5)
    assert decide(bundle, _scores([("a", 0.5)]))["decision"] == "warn"
    below = decide(bundle, _scores([("a", float(np.nextafter(0.5, 0)))]))
    assert below["decision"] == "allow"
    assert below["flagged_recipient_ids"] == []


def test_blocking_is_disabled():
    result = decide(_bundle(0.5), _scores([("a", 1.0)]))
    assert result["decision"] == "warn"
    assert result["decision"] != "block"


def test_max_aggregation_flags_every_recipient_and_counts_one_intervention():
    result = decide(_bundle(0.5), _scores([("a", 0.2), ("b", 0.7), ("c", 0.5)]))
    assert result["email_risk"] == pytest.approx(0.7)
    assert result["flagged_recipient_ids"] == ["b", "c"]
    table = _table([("d1", "a", True, 0.8), ("d1", "b", True, 0.6), ("d1", "c", False, 0.1), ("d2", "a", False, 0.2)])
    point = operating_point(table, 0.5)
    assert point["interventions"]["warnings"] == 1
    assert point["email"]["true_positives"] == 1
    assert point["recipient"]["true_positives"] == 2
    assert point["interventions"]["blocks"] == 0


def test_missing_policy_is_unable_to_assess(tmp_path):
    bundle, reason = try_load_bundle(tmp_path / "policy.json", MODEL, MANIFEST)
    assert bundle is None and "does not exist" in reason
    result = assess_draft(bundle, None, None, None, None, reason=reason)
    assert result["status"] == "unable_to_assess"
    assert result["decision"] is None
    assert result["email_risk"] is None
    assert decide(None, _scores([("a", 0.0)]))["status"] == "unable_to_assess"


def test_non_finite_score_is_unable_to_assess():
    assert decide(_bundle(0.5), _scores([("a", float("nan"))]))["status"] == "unable_to_assess"


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("model_version", "med-model-v0", "model"),
        ("feature_spec_version", "med-features-v0", "features"),
        ("policy_version", "med-policy-v0", "Policy version"),
        ("blocking_enabled", True, "Blocking"),
        ("T_warn", None, "T_warn"),
    ],
)
def test_policy_version_and_field_mismatch_is_refused(tmp_path, field, value, match):
    policy = json.loads((POLICY_DIR / "policy.json").read_text(encoding="utf-8"))
    policy[field] = value
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(PolicyError, match=match):
        load_bundle(path, MODEL, MANIFEST)


def test_checksum_mismatch_is_refused(tmp_path):
    policy = json.loads((POLICY_DIR / "policy.json").read_text(encoding="utf-8"))
    policy["checksums"]["model.joblib"] = "0" * 64
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    with pytest.raises(PolicyError, match="Checksum"):
        load_bundle(path, MODEL, MANIFEST)
    copied = tmp_path / "artifact_manifest.json"
    copied.write_text(MANIFEST.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(PolicyError, match="Checksum"):
        load_bundle(POLICY_DIR / "policy.json", MODEL, copied)


def test_frozen_command_needs_policy_and_runs_once(tmp_path):
    with pytest.raises(PolicyError, match="missing"):
        run_frozen_evaluation(tmp_path, MODEL, FEATURES, DATA)
    shutil.copy(POLICY_DIR / "policy.json", tmp_path / "policy.json")
    (tmp_path / TEST_EVALUATION_FILE).write_text("{}", encoding="utf-8")
    with pytest.raises(PolicyError, match="already exists"):
        run_frozen_evaluation(tmp_path, MODEL, FEATURES, DATA)
    with pytest.raises(PolicyError, match="cannot be reselected"):
        run_selection(FEATURES, DATA, MODEL, tmp_path)


def test_no_writer_for_frozen_feature_files():
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "features_test_product_like" not in text, path
        assert "features_test_diagnostic" not in text, path
    assert not list(FEATURES.glob("features_test_*"))
    with pytest.raises(FeatureError, match="frozen"):
        queries_for(read_dataset(DATA), ("test_product_like",))


def test_published_policy_matches_its_validation_table():
    policy = json.loads((POLICY_DIR / "policy.json").read_text(encoding="utf-8"))
    table = pd.read_csv(POLICY_DIR / "validation_scores.csv", float_precision="round_trip")
    assert len(table) == policy["validation_confusion"]["email"]["n"]
    warned = table["warned"].astype(bool)
    assert (warned == (table["email_risk"] >= policy["T_warn"])).all()
    misdirected = table["misdirected"].astype(bool)
    assert int((warned & misdirected).sum()) == policy["validation_confusion"]["email"]["true_positives"]
    assert int((warned & ~misdirected).sum()) == policy["validation_confusion"]["email"]["false_positives"] == 0
    assert policy["test_subsets_used"] is False
    assert policy["blocking_enabled"] is False and policy["T_block"] is None
    assert policy["calibration"] == "not_fit"


def test_warned_column_needs_no_exact_float_parse():
    policy = json.loads((POLICY_DIR / "policy.json").read_text(encoding="utf-8"))
    table = pd.read_csv(POLICY_DIR / "validation_scores.csv")
    warned = table["warned"].astype(bool) & table["misdirected"].astype(bool)
    assert int(warned.sum()) == policy["validation_confusion"]["email"]["true_positives"]


def test_refresh_keeps_the_policy_file(tmp_path):
    from med_models.data import sha256_file
    from med_policy.pipeline import refresh_validation_scores

    shutil.copy(POLICY_DIR / "policy.json", tmp_path / "policy.json")
    before = sha256_file(tmp_path / "policy.json")
    result = refresh_validation_scores(FEATURES, DATA, MODEL, tmp_path)
    assert sha256_file(tmp_path / "policy.json") == before
    refreshed = pd.read_csv(tmp_path / "validation_scores.csv")
    assert int(refreshed["warned"].sum()) == result["warned"]


def test_test_evaluation_used_the_current_policy():
    from med_models.data import sha256_file

    evaluation = json.loads((POLICY_DIR / TEST_EVALUATION_FILE).read_text(encoding="utf-8"))
    policy = json.loads((POLICY_DIR / "policy.json").read_text(encoding="utf-8"))
    assert evaluation["policy_sha256"] == sha256_file(POLICY_DIR / "policy.json")
    assert evaluation["T_warn"] == policy["T_warn"]
    for block in evaluation["subsets"].values():
        assert block["policy"]["interventions"]["blocks"] == 0


def test_clopper_pearson_zero_count_upper_bound():
    interval = clopper_pearson(0, 1990)
    assert interval["low"] == 0.0
    assert interval["high"] * 1000 == pytest.approx(1.852, abs=1e-3)
    assert clopper_pearson(0, 995)["high"] * 1000 > 1.0


def test_decision_path_does_not_fit(monkeypatch):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    from med_models.preprocess import CountLogScaler

    dataset = read_dataset(DATA)
    transformer = FittedText.load(FEATURES / "text_transformer.joblib")
    bundle = load_bundle(POLICY_DIR / "policy.json", MODEL, MANIFEST)
    directory = directory_from_dataset(dataset)
    index = history_index_from_dataset(dataset)
    index.bind(transformer)

    def refuse(*args, **kwargs):
        raise AssertionError("fit called on the decision path")

    for owner, name in ((LogisticRegression, "fit"), (TfidfVectorizer, "fit"), (TfidfVectorizer, "fit_transform"), (CountLogScaler, "fit")):
        monkeypatch.setattr(owner, name, refuse)
    scores = pd.read_csv(POLICY_DIR / "validation_scores.csv", float_precision="round_trip")
    sample = pd.concat([scores.loc[scores["misdirected"]].head(2), scores.loc[~scores["misdirected"]].head(2)])
    for row in sample.itertuples(index=False):
        result = assess_draft(bundle, directory, index, transformer, query_from_dataset(dataset, row.draft_id))
        assert result["status"] == "assessed"
        assert result["email_risk"] == pytest.approx(row.email_risk, abs=1e-12)
        assert result["decision"] == ("warn" if row.email_risk >= bundle.t_warn else "allow")
        assert result["policy_version"] == POLICY_VERSION
