"""Phase 3 feature contract: history cutoffs, missing evidence, and train-only text."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from med_data.calendar import parse_ts
from med_data.generate import Dataset
from med_data.history import visible_history
from med_data.schema import MODEL_INPUT_DENYLIST
from med_data.text import body_hash
from med_data.views import scoring_view
from med_features.checks import schema_problems, validate_feature_frame
from med_features.build import queries_for
from med_features.preprocess import analyze, unigrams
from med_features.profiles import EventHistory, directory_from_dataset, history_index_from_dataset
from med_features.quality import quality_report
from med_features.schema import (
    EXPORT_SUBSETS,
    FEATURE_COLUMNS,
    FEATURE_SPEC_VERSION,
    MATRIX_COLUMNS,
    RECENCY_FALLBACK_DAYS,
    FeatureError,
)
from med_features.similarity import normalized_similarity
from med_features.text_model import fit_on_dataset, fit_text_transformer, training_documents
from med_features.transform import (
    DraftQuery,
    events_from_scoring_view,
    query_from_dataset,
    query_from_scoring_view,
    transform_draft,
    transform_drafts,
)
from med_features.version import ARTIFACT_DIR
from med_features.version import DATASET_VERSION as FEATURE_DATASET_VERSION
from med_features.version import FEATURE_SPEC_VERSION as SPEC_VERSION

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = parse_ts("2024-09-15T12:00:00Z")
EARLY = parse_ts("2024-08-10T12:00:00Z")
LONG = "weekly staffing headcount update shares the hiring plan today now"
ZEBRA = "zebra quilt pattern"
FAMILY = "fam_draft"


def test_load_rejects_a_changed_preprocessor_regex(tmp_path):
    import joblib

    from med_features.text_model import FittedText

    fitted = fit_text_transformer(["staffing headcount update", "staffing headcount update"])
    path = tmp_path / "text_transformer.joblib"
    fitted.save(path)
    payload = joblib.load(path)
    payload["config"] = {**payload["config"], "id_regex": r"changed"}
    joblib.dump(payload, path)
    with pytest.raises(FeatureError, match="config"):
        FittedText.load(path)


def test_tokenizer_drops_generator_slots():
    text = "Ref: m000123 Ack m000124 Ticket T-00007 on 2024-09-15. Please review headcount."
    tokens = unigrams(text)
    assert "headcount" in tokens
    assert "m000123" not in tokens
    assert "m000124" not in tokens
    assert "t-00007" not in tokens
    assert "2024-09-15" not in tokens
    assert "ref" not in tokens
    assert "ack" not in tokens
    assert "please" not in tokens
    assert "salary band" in analyze("Salary band notes for the partners")


def test_schema_has_no_audit_features():
    assert schema_problems() == []
    assert set(FEATURE_COLUMNS).isdisjoint(MODEL_INPUT_DENYLIST)
    assert "role" not in DraftQuery.__dataclass_fields__
    assert FEATURE_SPEC_VERSION == SPEC_VERSION


def test_name_similarity_is_one_edit():
    assert normalized_similarity("alex chen", "alex chan") == pytest.approx(1 - 1 / 9)
    assert normalized_similarity("alex.chen", "alex.chan") == pytest.approx(1 - 1 / 9)


def test_counts_recency_window_and_exclusions(world):
    frame = _rows(world, "d_counts")
    alex = _one(frame, "c_alex_chen")
    sam = _one(frame, "c_sam")
    jordan = _one(frame, "c_jordan")
    assert alex["pair_outbound_count"] == 4
    assert alex["pair_outbound_count_28d"] == 2
    assert alex["pair_inbound_count"] == 1
    assert alex["pair_inbound_count_28d"] == 1
    assert alex["pair_recency_days"] == pytest.approx(14.125)
    assert alex["pair_recency_observed"] == 1
    assert alex["recipient_novel_to_sender"] == 0
    assert alex["sender_outbound_count"] == 5
    assert alex["sender_history_available"] == 1
    assert alex["sender_history_span_days"] == pytest.approx(45.125)
    assert alex["pair_outbound_rate_per_day"] == pytest.approx(4 / 45.125)
    assert alex["domain_outbound_count"] == 5
    assert alex["domain_novel_to_sender"] == 0
    assert alex["domain_seen_in_history"] == 1
    assert alex["recipient_is_internal"] == 1
    assert sam["pair_outbound_count"] == 2
    assert sam["pair_outbound_count_28d"] == 2
    assert sam["pair_inbound_count"] == 0
    assert sam["pair_recency_days"] == pytest.approx(5.125)
    assert jordan["pair_outbound_count"] == 0
    assert jordan["pair_inbound_count"] == 0
    assert jordan["pair_recency_observed"] == 0
    assert jordan["pair_recency_days"] == RECENCY_FALLBACK_DAYS
    assert jordan["recipient_novel_to_sender"] == 1
    assert jordan["domain_outbound_count"] == 0
    assert jordan["domain_novel_to_sender"] == 1
    assert jordan["domain_seen_in_history"] == 0
    assert jordan["recipient_is_internal"] == 0
    zebra = _one(_rows(world, "d_zebra"), "c_alex_chen")
    assert zebra["pair_outbound_count"] == 5
    assert zebra["pair_outbound_count_28d"] == 2
    assert validate_feature_frame(frame) == []


def test_co_support_single_recipient_and_unseen_partner(world):
    grouped = _rows(world, "d_counts")
    alex = _one(grouped, "c_alex_chen")
    sam = _one(grouped, "c_sam")
    jordan = _one(grouped, "c_jordan")
    assert alex["addressed_recipient_count"] == 3
    assert alex["co_support_applicable"] == 1
    assert alex["co_joint_message_count"] == 1
    assert alex["co_partner_fraction"] == pytest.approx(0.5)
    assert alex["co_focus_conditional_fraction"] == pytest.approx(0.25)
    assert alex["co_focus_history_available"] == 1
    assert sam["co_joint_message_count"] == 1
    assert sam["co_partner_fraction"] == pytest.approx(0.5)
    assert sam["co_focus_conditional_fraction"] == pytest.approx(0.5)
    assert jordan["co_joint_message_count"] == 0
    assert jordan["co_partner_fraction"] == pytest.approx(0.0)
    assert jordan["co_focus_history_available"] == 0
    assert jordan["co_focus_conditional_fraction"] == pytest.approx(0.0)
    single = _one(_rows(world, "d_single"), "c_alex_chen")
    assert single["co_support_applicable"] == 0
    assert single["co_joint_message_count"] == 0
    assert single["co_partner_fraction"] == pytest.approx(0.0)
    assert single["co_focus_conditional_fraction"] == pytest.approx(0.0)
    assert single["co_focus_history_available"] == 1
    inbound_only = _one(_rows(world, "d_quinn"), "c_quinn")
    assert inbound_only["pair_outbound_count"] == 0
    assert inbound_only["pair_inbound_count"] == 1
    assert inbound_only["recipient_novel_to_sender"] == 1
    assert inbound_only["pair_recency_observed"] == 1


def test_similarity_excludes_self_and_future_contacts(world):
    alex = _one(_rows(world, "d_counts"), "c_alex_chen")
    assert alex["contact_similarity_observed"] == 1
    assert alex["name_similarity_max"] == pytest.approx(1 - 1 / 9)
    assert alex["address_similarity_max"] == pytest.approx(1 - 1 / 9)
    assert alex["near_name_count"] == 1
    candidates = world.directory.candidate_ids("c_alex_chen", CUTOFF)
    assert "c_alex_chen" not in candidates
    assert "c_hidden" not in candidates
    assert "c_alex_chan" in candidates
    alone = directory_from_dataset(_only_self_dataset())
    assert alone.candidate_ids("c_alex_chen", CUTOFF) == []
    stats = alone.similarity("c_alex_chen", CUTOFF)
    assert stats["contact_similarity_observed"] == 0
    assert stats["name_similarity_max"] == 0.0


def test_content_distinguishes_missing_and_zero(world):
    empty = _one(_rows(world, "d_empty"), "c_alex_chen")
    assert empty["draft_text_empty"] == 1
    assert empty["draft_text_oov"] == 0
    assert empty["draft_text_short"] == 1
    assert empty["content_similarity_observed"] == 0
    assert empty["content_cosine"] == 0.0
    assert empty["pair_text_message_count"] > 0
    oov = _one(_rows(world, "d_oov"), "c_alex_chen")
    assert oov["draft_text_empty"] == 0
    assert oov["draft_text_oov"] == 1
    assert oov["content_similarity_observed"] == 0
    assert oov["content_cosine"] == 0.0
    assert oov["pair_text_message_count"] > 0
    zebra = _one(_rows(world, "d_zebra"), "c_alex_chen")
    assert zebra["draft_text_oov"] == 0
    assert zebra["content_similarity_observed"] == 1
    assert zebra["content_cosine"] == pytest.approx(0.0)
    assert zebra["pair_text_message_count"] > 0
    long = _one(_rows(world, "d_long"), "c_alex_chen")
    assert long["draft_text_short"] == 0
    assert long["draft_text_empty"] == 0
    assert long["content_similarity_observed"] == 1
    assert 0 < long["content_cosine"] < 1
    assert "zephyr" not in world.transformer.vectorizer.vocabulary_
    assert "staffing" in world.transformer.vectorizer.vocabulary_
    cold = _one(_rows(world, "d_cold"), "c_alex_chen")
    assert cold["sender_outbound_count"] == 0
    assert cold["sender_history_available"] == 0
    assert cold["sender_history_span_days"] == 0.0
    assert cold["pair_outbound_rate_per_day"] == 0.0
    assert cold["pair_recency_observed"] == 0
    assert cold["pair_recency_days"] == RECENCY_FALLBACK_DAYS
    assert cold["content_similarity_observed"] == 0
    assert cold["pair_text_message_count"] == 0
    assert cold["domain_seen_in_history"] == 1
    assert cold["domain_novel_to_sender"] == 1
    assert validate_feature_frame(_rows(world, "d_cold")) == []


def test_vectorized_centroid_matches_an_explicit_row_mean(world):
    """B4: one slice per recipient gives the per-row mean, skipping empty rows."""
    from med_features.transform import _content_cosine

    query = query_from_dataset(world.dataset, "d_counts")
    cutoff = parse_ts("2024-09-15T12:00:00Z")
    positions = world.index.pair_positions("c_maya", "c_alex_chen", None, cutoff, query.exclude_family_id, query.exclude_body_hashes)
    draft = world.transformer.vectorizer.transform([LONG + "\nHeadcount"])
    value, count = _content_cosine(draft, world.index, positions)
    rows = [world.index.vectors[pos].toarray().ravel() for pos in positions]
    rows = [row for row in rows if row.any()]
    assert count == len(rows) > 0
    centroid = np.mean(rows, axis=0)
    expected = float(draft.toarray().ravel() @ centroid / np.linalg.norm(centroid))
    assert value == pytest.approx(expected, abs=1e-12)
    assert _content_cosine(draft, world.index, []) == (0.0, 0)


def test_identical_text_cosine_is_one():
    dataset = _tiny_pair_dataset()
    transformer = fit_text_transformer([LONG, LONG, ZEBRA, ZEBRA])
    index = history_index_from_dataset(dataset)
    index.bind(transformer)
    directory = directory_from_dataset(dataset)
    frame = transform_draft(directory, index, transformer, query_from_dataset(dataset, "d_match"))
    assert frame.loc[0, "content_similarity_observed"] == 1
    assert frame.loc[0, "content_cosine"] == pytest.approx(1.0, abs=1e-9)
    assert "quokka" not in transformer.vectorizer.vocabulary_
    leaked = fit_text_transformer(
        [LONG, LONG, "quokka marsupial extra wording", "quokka marsupial extra wording"]
    )
    assert "quokka" in leaked.vectorizer.vocabulary_


def test_labels_roles_and_withheld_ids_do_not_change_features(world):
    original = _rows(world, "d_counts")
    drafts = world.dataset.drafts.copy()
    drafts["scenario_id"] = "S01"
    drafts["scenario_variant"] = "lookalike_replacement"
    drafts["withheld_contact_id"] = "c_alex_chan"
    drafts["split"] = "test"
    drafts["subset"] = "test_diagnostic"
    drafts["is_counterfactual"] = True
    labels = world.dataset.labels.copy()
    labels["intended"] = False
    labels["stipulation"] = "changed for the isolation test"
    recipients = world.dataset.draft_recipients.copy()
    recipients["role"] = "bcc"
    mutated = replace(
        world.dataset,
        drafts=drafts,
        labels=labels,
        draft_recipients=recipients,
        split_manifest=world.dataset.split_manifest.assign(scenario_id="S08", frozen=True),
    )
    again = transform_drafts(
        world.directory,
        world.index,
        world.transformer,
        [query_from_dataset(mutated, "d_counts")],
    )
    pd.testing.assert_frame_equal(original, again)


def test_batch_single_reload_and_scoring_view_match(world, tmp_path):
    queries = [query_from_dataset(world.dataset, "d_counts"), query_from_dataset(world.dataset, "d_cold")]
    batch = transform_drafts(world.directory, world.index, world.transformer, queries)
    single = pd.concat(
        [transform_draft(world.directory, world.index, world.transformer, query) for query in queries],
        ignore_index=True,
    )
    pd.testing.assert_frame_equal(batch, single)
    pd.testing.assert_frame_equal(batch, transform_drafts(world.directory, world.index, world.transformer, queries))
    path = tmp_path / "text_transformer.joblib"
    world.transformer.save(path)
    loaded = type(world.transformer).load(path)
    rebound = history_index_from_dataset(world.dataset)
    rebound.bind(loaded)
    reloaded = transform_drafts(world.directory, rebound, loaded, queries)
    pd.testing.assert_frame_equal(batch, reloaded)
    view = scoring_view(world.dataset, "d_counts")
    from_view = transform_draft(
        world.directory,
        EventHistory(events_from_scoring_view(view), world.transformer),
        world.transformer,
        query_from_scoring_view(view),
    )
    pd.testing.assert_frame_equal(_rows(world, "d_counts"), from_view)
    assert list(from_view.columns) == list(MATRIX_COLUMNS)


def test_earlier_draft_ignores_later_mail(world):
    early = _one(_rows(world, "d_early"), "c_alex_chen")
    assert early["pair_outbound_count"] == 2
    assert early["sender_outbound_count"] == 2
    later = _one(_rows(world, "d_zebra"), "c_alex_chen")
    assert later["pair_outbound_count"] > early["pair_outbound_count"]


def test_history_index_matches_visible_history_ids(world):
    query = query_from_dataset(world.dataset, "d_counts")
    indexed = world.index.visible_message_ids(CUTOFF, query.exclude_family_id, query.exclude_body_hashes)
    history = visible_history(world.dataset, "d_counts")
    assert indexed == history["message_id"].tolist()
    assert history.loc[history["sent_at"] >= CUTOFF].empty
    assert FAMILY not in set(history["family_id"])
    assert LONG not in set(history["body"])


def test_export_and_quality_report_refuse_frozen_subsets(world):
    with pytest.raises(FeatureError, match="frozen"):
        queries_for(world.dataset, ("test_product_like",))
    with pytest.raises(FeatureError, match="refuses"):
        quality_report(world.dataset, {"test_diagnostic": _rows(world, "d_counts")}, fit_scope={})
    report = quality_report(
        world.dataset,
        {"train": _rows(world, "d_counts")},
        fit_scope=world.transformer.fit_scope,
    )
    assert report["populations"] == ["train"]
    assert "test_product_like" in report["frozen_subsets_excluded"]
    assert report["subsets"]["train"]["scenarios"]


def test_unknown_contact_and_duplicate_recipient_fail(world):
    query = query_from_dataset(world.dataset, "d_single")
    broken = replace(query, recipients=(("c_missing", 0),))
    with pytest.raises(FeatureError, match="directory"):
        transform_draft(world.directory, world.index, world.transformer, broken)
    duplicated = replace(query, recipients=(("c_alex_chen", 0), ("c_alex_chen", 1)))
    with pytest.raises(FeatureError, match="repeats"):
        transform_draft(world.directory, world.index, world.transformer, duplicated)


def test_real_training_fit_excludes_later_text_and_slots(dataset, fitted_real):
    transformer = fitted_real[0]
    documents = training_documents(dataset)
    again = fit_text_transformer(documents, fit_scope=transformer.fit_scope)
    assert transformer.vectorizer.vocabulary_ == again.vectorizer.vocabulary_
    assert np.allclose(transformer.vectorizer.idf_, again.vectorizer.idf_)
    end = parse_ts(transformer.fit_scope["fit_sent_at_end_exclusive"])
    assert dataset.messages.loc[dataset.messages["sent_at"] >= end, "message_id"].shape[0] > 0
    assert parse_ts(transformer.fit_scope["last_sent_at"]) < end
    assert transformer.fit_scope["validation_and_test_excluded"] is True
    vocabulary = set(transformer.vectorizer.vocabulary_)
    assert "headcount" in vocabulary
    assert "ref" not in vocabulary
    assert "ack" not in vocabulary
    assert not any(_generator_slot(term) for term in vocabulary)
    from med_features.preprocess import analyze, document_text

    picked = ""
    later = dataset.messages.loc[dataset.messages["sent_at"] >= end]
    for row in later.itertuples(index=False):
        text = document_text(row.subject, row.body)
        if analyze(text):
            picked = text
            break
    assert picked
    wider = fit_text_transformer(documents + [picked, picked])
    changed = wider.vectorizer.vocabulary_ != transformer.vectorizer.vocabulary_ or not np.allclose(
        _aligned_idf(transformer.vectorizer, wider.vectorizer),
        wider.vectorizer.idf_,
    )
    assert changed


def test_published_artifact_matches_training_fit(dataset, fitted_real):
    """The published feature artifact equals a fresh fit on the dataset it names."""
    import json

    from med_data.io import read_dataset, verify_files
    from med_features.build import read_features

    artifact = ROOT / ARTIFACT_DIR
    metadata = json.loads((artifact / "fit_metadata.json").read_text(encoding="utf-8"))
    assert metadata["feature_spec_version"] == FEATURE_SPEC_VERSION
    assert metadata["dataset_version"] == FEATURE_DATASET_VERSION
    data_dir = ROOT / "data" / metadata["dataset_version"]
    manifest = json.loads((data_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    assert metadata["dataset_checksums"] == {name: item["sha256"] for name, item in manifest["files"].items()}
    assert metadata["exported_subsets"] == list(EXPORT_SUBSETS)
    schema = json.loads((artifact / "feature_schema.json").read_text(encoding="utf-8"))
    assert schema["feature_columns"] == list(FEATURE_COLUMNS)
    if dataset.summary.get("dataset_version") == metadata["dataset_version"]:
        source = dataset
        transformer, index, directory = fitted_real
    else:
        verify_files(data_dir)
        source = read_dataset(data_dir)
        transformer = fit_on_dataset(source)
        index = history_index_from_dataset(source)
        index.bind(transformer)
        directory = directory_from_dataset(source)
    loaded = type(transformer).load(artifact / "text_transformer.joblib")
    assert loaded.vectorizer.vocabulary_ == transformer.vectorizer.vocabulary_
    assert np.array_equal(loaded.vectorizer.idf_, transformer.vectorizer.idf_)
    frozen_ids = set(
        source.drafts.loc[
            source.drafts["subset"].isin(["test_product_like", "test_diagnostic"]),
            "draft_id",
        ]
    )
    for subset in EXPORT_SUBSETS:
        frame = read_features(artifact / f"features_{subset}.csv")
        assert len(frame) == metadata["row_counts"][subset]
        assert list(frame.columns) == list(MATRIX_COLUMNS)
        assert set(frame["draft_id"]).isdisjoint(frozen_ids)
        ids = frame["draft_id"].drop_duplicates()
        for draft_id in (ids.iloc[0], ids.iloc[len(ids) // 2], ids.iloc[-1]):
            fresh = transform_draft(directory, index, transformer, query_from_dataset(source, str(draft_id)))
            stored = frame.loc[frame["draft_id"] == draft_id].reset_index(drop=True)
            # Lossless CSV: the stored floats are the in-memory floats, bit for bit.
            pd.testing.assert_frame_equal(fresh, stored, check_exact=True)
            assert validate_feature_frame(fresh) == []
    assert not (artifact / "features_test_product_like.csv").exists()
    assert not (artifact / "features_test_diagnostic.csv").exists()


def test_feature_csv_round_trips_every_float(tmp_path):
    from med_features.build import read_features, write_features

    frame = pd.DataFrame(
        {
            "a": [0.1, 1 / 3, 0.13455666515724893, np.nextafter(1.0, 0.0), 5e-324, 1e300],
            "b": [1, 2, 3, 4, 5, 6],
        }
    )
    path = tmp_path / "features.csv"
    write_features(frame, path)
    back = read_features(path)
    assert back["a"].to_numpy().tobytes() == frame["a"].to_numpy().tobytes()
    assert back["b"].dtype == np.int64


def test_real_history_and_scoring_view_agree(dataset, fitted_real):
    transformer, index, directory = fitted_real
    sample = _sample_drafts(dataset)
    assert set(sample["subset"]) <= set(EXPORT_SUBSETS)
    for draft_id in sample["draft_id"]:
        query = query_from_dataset(dataset, draft_id)
        indexed = index.visible_message_ids(query.sent_at, query.exclude_family_id, query.exclude_body_hashes)
        history = visible_history(dataset, draft_id)
        assert indexed == history["message_id"].tolist()
        view = scoring_view(dataset, draft_id)
        from_index = transform_draft(directory, index, transformer, query)
        from_view = transform_draft(
            directory,
            EventHistory(events_from_scoring_view(view), transformer),
            transformer,
            query_from_scoring_view(view),
        )
        pd.testing.assert_frame_equal(from_index, from_view)
        assert validate_feature_frame(from_index) == []
        assert set(from_index.columns).isdisjoint(MODEL_INPUT_DENYLIST)


@pytest.fixture(scope="module")
def fitted_real(dataset):
    transformer = fit_on_dataset(dataset)
    index = history_index_from_dataset(dataset)
    index.bind(transformer)
    return transformer, index, directory_from_dataset(dataset)


@pytest.fixture(scope="module")
def world():
    dataset = _fixture_dataset()
    documents = []
    for text in (
        "staffing headcount update",
        "staffing headcount followup",
        "staffing headcount reply",
        "staffing headcount edge",
        "badge facilities request",
        ZEBRA,
        LONG,
        "family leak staffing headcount update",
    ):
        documents.extend([text, text])
    documents.append("zephyr token")
    transformer = fit_text_transformer(documents)
    index = history_index_from_dataset(dataset)
    index.bind(transformer)
    return _World(dataset, transformer, index, directory_from_dataset(dataset))


class _World:
    def __init__(self, dataset, transformer, index, directory):
        self.dataset = dataset
        self.transformer = transformer
        self.index = index
        self.directory = directory


def _rows(world, draft_id: str) -> pd.DataFrame:
    return transform_draft(world.directory, world.index, world.transformer, query_from_dataset(world.dataset, draft_id))


def _one(frame: pd.DataFrame, contact_id: str) -> pd.Series:
    return frame.loc[frame["contact_id"] == contact_id].iloc[0]


def _sample_drafts(dataset) -> pd.DataFrame:
    chosen = []
    for subset in EXPORT_SUBSETS:
        group = dataset.drafts.loc[dataset.drafts["subset"] == subset].sort_values(["sent_at", "draft_id"])
        picks = [group.iloc[0], group.iloc[-1]]
        chosen.extend(picks)
    return pd.DataFrame(chosen)


def _generator_slot(term: str) -> bool:
    if " " in term:
        return any(_generator_slot(part) for part in term.split(" "))
    if term in {"ref", "ack"}:
        return True
    if len(term) == 7 and term[0] in {"m", "d"} and term[1:].isdigit():
        return True
    if len(term) == 10 and term[4] == "-" and term[7] == "-" and term.replace("-", "").isdigit():
        return True
    return term.startswith("t-") and term[2:].isdigit()


def _aligned_idf(left, right) -> np.ndarray:
    """IDF of the left model mapped into the right vocabulary order."""
    mapped = np.zeros(len(right.vocabulary_), dtype=np.float64)
    for term, index in right.vocabulary_.items():
        mapped[index] = left.idf_[left.vocabulary_[term]] if term in left.vocabulary_ else -1.0
    return mapped


def _only_self_dataset() -> Dataset:
    when = parse_ts("2024-01-01T00:00:00Z")
    contacts = pd.DataFrame(
        [
            _contact("c_alex_chen", "Alex Chen", "alex.chen@demo.example", "demo.example", True, when),
        ]
    )
    return _dataset(contacts, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())


def _tiny_pair_dataset() -> Dataset:
    visible = parse_ts("2024-01-01T00:00:00Z")
    sent = parse_ts("2024-08-01T09:00:00Z")
    contacts = pd.DataFrame(
        [
            _contact("c_maya", "Maya Okonkwo", "maya@demo.example", "demo.example", True, visible),
            _contact("c_alex_chen", "Alex Chen", "alex.chen@demo.example", "demo.example", True, visible),
        ]
    )
    messages = pd.DataFrame([_message("m000001", "fam_m", "c_maya", sent, "Status", LONG + "\nRef: m000001")])
    recipients = pd.DataFrame([_recipient("m000001", "c_alex_chen", 0)])
    drafts = pd.DataFrame(
        [
            _draft(
                "d_match",
                "fam_match",
                "c_maya",
                sent + timedelta(days=1),
                "Status",
                LONG + "\nRef: m000002",
                "train",
                "routine",
            )
        ]
    )
    draft_recipients = pd.DataFrame([_draft_recipient("d_match", "c_alex_chen", 0, "to")])
    labels = pd.DataFrame([_label("d_match", "c_alex_chen")])
    return _dataset(contacts, messages, recipients, drafts, draft_recipients, labels)


def _fixture_dataset() -> Dataset:
    visible = parse_ts("2024-01-01T00:00:00Z")
    hidden_from = parse_ts("2024-12-01T00:00:00Z")
    contacts = pd.DataFrame(
        [
            _contact("c_maya", "Maya Okonkwo", "maya@demo.example", "demo.example", True, visible),
            _contact("c_alex_chen", "Alex Chen", "alex.chen@demo.example", "demo.example", True, visible),
            _contact("c_alex_chan", "Alex Chan", "alex.chan@demo.example", "demo.example", True, visible),
            _contact("c_sam", "Sam Rivera", "sam@demo.example", "demo.example", True, visible),
            _contact("c_jordan", "Jordan Quinn", "jordan@partner.example", "partner.example", False, visible),
            _contact("c_nina", "Nina Shah", "nina@demo.example", "demo.example", True, visible),
            _contact("c_quinn", "Quinn Hale", "quinn@demo.example", "demo.example", True, visible),
            _contact(
                "c_hidden",
                "Alex Chen",
                "alex.chen@later.example",
                "later.example",
                False,
                hidden_from,
            ),
        ]
    )
    specs = [
        ("m000001", FAMILY, "c_maya", "2024-08-01T08:00:00Z", "family leak staffing headcount update", ("c_alex_chen",)),
        ("m000002", "fam_keep", "c_maya", "2024-08-01T09:00:00Z", "staffing headcount update", ("c_alex_chen",)),
        ("m000003", "fam_copy", "c_maya", "2024-08-05T09:00:00Z", LONG, ("c_alex_chen",)),
        ("m000004", "fam_early_edge", "c_maya", "2024-08-18T11:59:59Z", "staffing headcount edge", ("c_alex_chen",)),
        ("m000005", "fam_edge", "c_maya", "2024-08-18T12:00:00Z", "staffing headcount edge", ("c_alex_chen",)),
        ("m000006", "fam_group", "c_maya", "2024-08-20T09:00:00Z", "staffing headcount followup", ("c_alex_chen", "c_sam")),
        ("m000007", "fam_reply", "c_alex_chen", "2024-09-01T09:00:00Z", "staffing headcount reply", ("c_maya",)),
        ("m000008", "fam_quinn", "c_quinn", "2024-09-02T09:00:00Z", "staffing headcount reply", ("c_maya",)),
        ("m000009", "fam_sam", "c_maya", "2024-09-10T09:00:00Z", "badge facilities request", ("c_sam",)),
        ("m000010", "fam_exact", "c_maya", "2024-09-15T12:00:00Z", "staffing headcount update", ("c_alex_chen",)),
        ("m000011", "fam_future", "c_maya", "2024-09-16T09:00:00Z", "staffing headcount update", ("c_alex_chen",)),
    ]
    messages = pd.DataFrame(
        [
            _message(message_id, family, sender, parse_ts(moment), "Note", body)
            for message_id, family, sender, moment, body, _people in specs
        ]
    )
    recipient_rows = []
    for message_id, _family, _sender, _moment, _body, people in specs:
        for order, contact_id in enumerate(people):
            recipient_rows.append(_recipient(message_id, contact_id, order))
    draft_specs = [
        ("d_counts", CUTOFF, "c_maya", "Headcount", LONG, "train", (("c_alex_chen", "to"), ("c_sam", "cc"), ("c_jordan", "bcc"))),
        ("d_zebra", CUTOFF, "c_maya", "Other", ZEBRA, "validation_product_like", (("c_alex_chen", "to"), ("c_sam", "cc"), ("c_jordan", "bcc"))),
        ("d_empty", CUTOFF, "c_maya", "", "", "validation_product_like", (("c_alex_chen", "to"),)),
        ("d_oov", CUTOFF, "c_maya", "Hello", "quokka marsupial", "validation_product_like", (("c_alex_chen", "to"),)),
        ("d_long", CUTOFF, "c_maya", "Plan", LONG, "validation_product_like", (("c_alex_chen", "to"),)),
        ("d_single", CUTOFF, "c_maya", "Other", ZEBRA, "validation_product_like", (("c_alex_chen", "to"),)),
        ("d_quinn", CUTOFF, "c_maya", "Hello", LONG, "validation_product_like", (("c_quinn", "to"),)),
        ("d_cold", CUTOFF, "c_nina", "Plan", LONG, "validation_product_like", (("c_alex_chen", "to"),)),
        ("d_early", EARLY, "c_maya", "Badge", "badge facilities request", "validation_product_like", (("c_alex_chen", "to"),)),
    ]
    drafts = pd.DataFrame(
        [
            _draft(draft_id, FAMILY, sender, moment, subject, body, subset, "routine")
            for draft_id, moment, sender, subject, body, subset, _recipients in draft_specs
        ]
    )
    draft_recipients = []
    labels = []
    for draft_id, _moment, _sender, _subject, _body, _subset, recipients in draft_specs:
        for order, (contact_id, role) in enumerate(recipients):
            draft_recipients.append(_draft_recipient(draft_id, contact_id, order, role))
            labels.append(_label(draft_id, contact_id))
    return _dataset(
        contacts,
        messages,
        pd.DataFrame(recipient_rows),
        drafts,
        pd.DataFrame(draft_recipients),
        pd.DataFrame(labels),
    )


def _dataset(contacts, messages, recipients, drafts, draft_recipients, labels) -> Dataset:
    if not messages.empty and "body_hash" not in messages:
        messages = messages.copy()
        messages["body_hash"] = messages["body"].map(body_hash)
    if drafts.empty:
        manifest = pd.DataFrame(columns=["draft_id", "subset", "scenario_id", "frozen"])
    else:
        manifest = pd.DataFrame(
            {
                "draft_id": drafts["draft_id"],
                "subset": drafts["subset"],
                "scenario_id": drafts["scenario_id"],
                "frozen": False,
            }
        )
    return Dataset(
        contacts=contacts,
        messages=messages if not messages.empty else _empty_messages(),
        message_recipients=recipients if not recipients.empty else pd.DataFrame(columns=["message_id", "contact_id", "role", "recipient_order"]),
        drafts=drafts,
        draft_recipients=draft_recipients,
        labels=labels,
        reviewer_feedback=pd.DataFrame(),
        split_manifest=manifest,
        invalid_fixtures=pd.DataFrame(),
        seed=1,
        summary={"dataset_version": "fixture"},
    )


def _empty_messages() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "message_id",
            "family_id",
            "sender_contact_id",
            "sent_at",
            "subject",
            "body",
            "body_hash",
        ]
    )


def _contact(contact_id, name, email, domain, internal, visible) -> dict:
    return {
        "contact_id": contact_id,
        "display_name": name,
        "email_address": email,
        "domain": domain,
        "is_internal": internal,
        "department": "operations",
        "directory_visible_from": visible,
    }


def _message(message_id, family, sender, moment, subject, body) -> dict:
    return {
        "message_id": message_id,
        "family_id": family,
        "sender_contact_id": sender,
        "sent_at": moment,
        "subject": subject,
        "body": body,
        "body_hash": body_hash(body),
    }


def _recipient(message_id, contact_id, order) -> dict:
    return {"message_id": message_id, "contact_id": contact_id, "role": "to", "recipient_order": order}


def _draft(draft_id, family, sender, moment, subject, body, subset, scenario) -> dict:
    return {
        "draft_id": draft_id,
        "family_id": family,
        "sender_contact_id": sender,
        "sent_at": moment,
        "subject": subject,
        "body": body,
        "subset": subset,
        "scenario_id": scenario,
        "scenario_variant": "fixture",
        "withheld_contact_id": "",
        "split": "train",
        "is_counterfactual": False,
    }


def _draft_recipient(draft_id, contact_id, order, role) -> dict:
    return {"draft_id": draft_id, "contact_id": contact_id, "role": role, "recipient_order": order}


def _label(draft_id, contact_id) -> dict:
    return {
        "draft_id": draft_id,
        "contact_id": contact_id,
        "intended": True,
        "scenario_id": "routine",
        "stipulation": "fixture",
    }
