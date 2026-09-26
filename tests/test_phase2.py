"""Phase 2 data contract: labels, splits, leakage, and reproducibility."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from med_data.history import visible_history
from med_data.io import _row_count, read_dataset, write_dataset
from med_data.prevalence import precision_from_rates
from med_data.schema import MODEL_INPUT_DENYLIST, TABLES
from med_data.validate import assert_valid
from med_data.version import DATASET_VERSION, SEED
from med_data.views import denied_keys, scoring_view

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "data" / DATASET_VERSION


def test_published_contract_passes_validation(dataset):
    checks = assert_valid(dataset)
    assert len(checks) == 31
    assert dataset.seed == SEED
    assert {check.check_id for check in checks} >= {"Q29", "Q30", "Q31"}


def test_product_like_prevalence_and_enrichment(dataset):
    manifest = dataset.split_manifest
    expected = {
        "train": (300, 3000),
        "validation_product_like": (20, 4000),
        "test_product_like": (30, 6000),
    }
    for subset, (misdirected, total) in expected.items():
        group = manifest.loc[manifest["subset"] == subset]
        assert len(group) == total
        assert int(group["is_misdirected_email"].sum()) == misdirected
    frozen = manifest.loc[manifest["frozen"], "subset"].unique()
    assert set(frozen) == {"test_product_like", "test_diagnostic"}


def test_walkthrough_history_respects_relationships(dataset):
    drafts = dataset.drafts
    walk = drafts.loc[drafts["is_walkthrough"]].set_index(["scenario_id", "scenario_variant"])
    s01 = walk.loc[("S01", "lookalike_replacement")]
    history = visible_history(dataset, s01["draft_id"])
    assert (history["sent_at"] < s01["sent_at"]).all()
    assert (history["family_id"] != s01["family_id"]).all()
    chan_staffing = history.loc[history["generator_topic"] == "staffing"]
    chan_ids = set(chan_staffing["message_id"].map(lambda message_id: _recipients(dataset, message_id)).explode())
    assert "c_alex_chan" in chan_ids
    assert _involvements(dataset, "c_alex_chen", s01["sent_at"]) > 0

    s03 = walk.loc[("S03", "legitimate_first_contact")]
    assert _involvements(dataset, "c_jordan", s03["sent_at"]) == 0
    s06 = walk.loc[("S06", "legitimate_new_domain")]
    assert _involvements(dataset, "c_rina", s06["sent_at"]) == 0
    s11 = walk.loc[("S11", "mistaken_first_contact")]
    assert _involvements(dataset, "c_blake", s11["sent_at"]) == 0


def test_scoring_view_hides_labels(dataset):
    draft_id = dataset.split_manifest.loc[
        dataset.split_manifest["is_walkthrough"] & (dataset.split_manifest["scenario_id"] == "S02"),
        "draft_id",
    ].iloc[0]
    view = scoring_view(dataset, draft_id)
    assert not denied_keys(view)
    assert MODEL_INPUT_DENYLIST.isdisjoint(view["features"])
    assert view["features"]["history"]
    assert all(
        item["sent_at"] < view["features"]["sent_at"] for item in view["features"]["history"]
    )


def test_feedback_is_not_applied(dataset):
    feedback = dataset.reviewer_feedback
    assert set(feedback["review_status"]) == {"pending_review", "rejected"}
    assert (feedback["confidence"] == "uncertain").any()
    assert set(dataset.labels["label_source"]) == {"synthetic_stipulated"}


def test_precision_moves_with_prevalence():
    at_budget = precision_from_rates(0.5, 0.001, 0.005)
    rarer = precision_from_rates(0.5, 0.001, 0.001)
    more_common = precision_from_rates(0.5, 0.001, 0.02)
    assert rarer < at_budget < more_common
    assert round(at_budget, 4) == 0.7153


def test_two_generations_match(dataset):
    from med_data.generate import generate_dataset

    again = generate_dataset()
    assert dataset.messages["body"].tolist() == again.messages["body"].tolist()
    assert dataset.drafts["draft_id"].tolist() == again.drafts["draft_id"].tolist()
    assert dataset.labels["intended"].tolist() == again.labels["intended"].tolist()


def test_roundtrip_and_published_checksums(dataset, tmp_path):
    written = write_dataset(dataset, tmp_path / "fresh", validate=False)
    loaded = read_dataset(written)
    assert loaded.drafts["draft_id"].tolist() == dataset.drafts["draft_id"].tolist()
    assert loaded.labels["intended"].tolist() == dataset.labels["intended"].tolist()
    assert loaded.messages["message_id"].tolist() == dataset.messages["message_id"].tolist()
    manifest = json.loads((written / "dataset_manifest.json").read_text(encoding="utf-8"))
    published = json.loads((PUBLISHED / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == published["files"]
    assert manifest["seed"] == SEED
    assert manifest["files"]["messages.csv"]["rows"] == len(dataset.messages)
    assert manifest["files"]["drafts.csv"]["rows"] == len(dataset.drafts)


def test_csv_record_count_ignores_embedded_newlines(tmp_path):
    path = tmp_path / "multiline.csv"
    path.write_text('id,body\n"m1","alpha\nbeta\ngamma"\n"m2","ok"\n', encoding="utf-8")
    assert _row_count(path) == 2
    physical_rows = sum(1 for _ in path.open(encoding="utf-8")) - 1
    assert physical_rows == 4


def test_swapped_manifest_assignment_is_rejected(dataset):
    manifest = dataset.split_manifest.copy()
    train_index = manifest.index[manifest["subset"].eq("train")][0]
    test_index = manifest.index[manifest["subset"].eq("test_product_like")][0]
    for column in ("split", "subset", "frozen"):
        train_value = manifest.at[train_index, column]
        manifest.at[train_index, column] = manifest.at[test_index, column]
        manifest.at[test_index, column] = train_value
    broken = replace(dataset, split_manifest=manifest)
    with pytest.raises(AssertionError, match="manifest"):
        assert_valid(broken)


def test_manifest_timestamp_and_family_must_match_draft(dataset):
    manifest = dataset.split_manifest.copy()
    train_index = manifest.index[manifest["subset"].eq("train")][0]
    test_index = manifest.index[manifest["subset"].eq("test_product_like")][0]
    manifest.at[train_index, "family_id"] = manifest.at[test_index, "family_id"]
    manifest.at[train_index, "sent_at"] = manifest.at[test_index, "sent_at"]
    broken = replace(dataset, split_manifest=manifest)
    with pytest.raises(AssertionError, match="manifest"):
        assert_valid(broken)


def test_data_dictionary_lists_every_column():
    text = (ROOT / "docs" / "phase_2" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    missing = [column for columns in TABLES.values() for column in columns if f"`{column}`" not in text]
    assert not missing


def _recipients(dataset, message_id: str) -> list[str]:
    rows = dataset.message_recipients.loc[dataset.message_recipients["message_id"] == message_id]
    return rows["contact_id"].tolist()


def _involvements(dataset, contact_id: str, cutoff) -> int:
    messages = dataset.messages
    early = set(messages.loc[messages["sent_at"] < cutoff, "message_id"])
    sent = int(((messages["sender_contact_id"] == contact_id) & (messages["sent_at"] < cutoff)).sum())
    received = int(
        (
            dataset.message_recipients["contact_id"].eq(contact_id)
            & dataset.message_recipients["message_id"].isin(early)
        ).sum()
    )
    return sent + received
