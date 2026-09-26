"""Build versioned feature artifacts from a published dataset directory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from med_data.calendar import FROZEN_SUBSETS
from med_data.io import read_dataset, verify_files
from med_features.profiles import directory_from_dataset, history_index_from_dataset
from med_features.quality import quality_report, render_quality_markdown
from med_features.schema import EXPORT_SUBSETS, FEATURE_SPEC_VERSION, FeatureError
from med_features.text_model import fit_on_dataset
from med_features.transform import query_from_dataset, transform_drafts
from med_features.version import FEATURE_SPEC_VERSION as SPEC_VERSION


def queries_for(dataset, subsets: tuple[str, ...]) -> list:
    blocked = set(subsets) & set(FROZEN_SUBSETS)
    if blocked:
        raise FeatureError(
            "Refusing to materialize frozen subsets: " + ", ".join(sorted(blocked))
        )
    unknown = set(subsets) - set(EXPORT_SUBSETS)
    if unknown:
        raise FeatureError("Unknown export subset: " + ", ".join(sorted(unknown)))
    chosen = dataset.drafts.loc[dataset.drafts["subset"].isin(list(subsets))]
    chosen = chosen.sort_values(["sent_at", "draft_id"], kind="mergesort")
    return [query_from_dataset(dataset, draft_id) for draft_id in chosen["draft_id"].tolist()]


def feature_schema_payload() -> dict:
    from med_features.schema import (
        FEATURE_COLUMNS,
        FLOAT_FEATURES,
        KEY_COLUMNS,
        NEAR_NAME_THRESHOLD,
        RECENCY_FALLBACK_DAYS,
        RECENT_WINDOW_DAYS,
        SHORT_TOKEN_MAX,
        SPAN_FLOOR_DAYS,
        feature_dtype,
    )

    return {
        "feature_spec_version": SPEC_VERSION,
        "key_columns": list(KEY_COLUMNS),
        "feature_columns": list(FEATURE_COLUMNS),
        "dtypes": {name: feature_dtype(name) for name in FEATURE_COLUMNS},
        "fallbacks": {
            "pair_recency_days": {
                "value": RECENCY_FALLBACK_DAYS,
                "when": "pair_recency_observed == 0",
            },
            "sender_history_span_days": {"value": 0.0, "when": "sender_history_available == 0"},
            "pair_outbound_rate_per_day": {"value": 0.0, "when": "sender_history_available == 0"},
            "co_partner_fraction": {"value": 0.0, "when": "co_support_applicable == 0"},
            "co_focus_conditional_fraction": {
                "value": 0.0,
                "when": "co_support_applicable == 0 or co_focus_history_available == 0",
            },
            "co_joint_message_count": {"value": 0, "when": "co_support_applicable == 0"},
            "name_similarity_max": {"value": 0.0, "when": "contact_similarity_observed == 0"},
            "address_similarity_max": {"value": 0.0, "when": "contact_similarity_observed == 0"},
            "near_name_count": {"value": 0, "when": "contact_similarity_observed == 0"},
            "content_cosine": {"value": 0.0, "when": "content_similarity_observed == 0"},
        },
        "windows": {
            "recent_days": RECENT_WINDOW_DAYS,
            "span_floor_days": SPAN_FLOOR_DAYS,
            "short_token_max": SHORT_TOKEN_MAX,
            "near_name_threshold": NEAR_NAME_THRESHOLD,
        },
        "model_matrix": list(FEATURE_COLUMNS),
        "notes": [
            "Key columns are join keys. Do not train on them.",
            "Do not join split, subset, scenario, label, family, or role into the model matrix.",
            "Role is omitted on purpose. A Bcc recipient is not evidence of a mistake.",
        ],
    }


def build_artifacts(
    data_dir: str | Path,
    output_dir: str | Path,
    *,
    quality_markdown: str | Path | None = None,
) -> Path:
    source = Path(data_dir)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    verify_files(source)
    dataset = read_dataset(source)
    if dataset.summary.get("dataset_version") != "med-synth-v2":
        raise FeatureError("Feature build expects dataset med-synth-v2")
    checksums = _checksums(source)
    transformer = fit_on_dataset(dataset)
    index = history_index_from_dataset(dataset)
    index.bind(transformer)
    directory = directory_from_dataset(dataset)
    frames = {}
    for subset in EXPORT_SUBSETS:
        queries = queries_for(dataset, (subset,))
        frames[subset] = transform_drafts(directory, index, transformer, queries)
        frames[subset].to_csv(target / f"features_{subset}.csv", index=False, lineterminator="\n")
    report = quality_report(dataset, frames, fit_scope=transformer.fit_scope)
    (target / "quality_report.json").write_text(_dump(report), encoding="utf-8")
    if quality_markdown is not None:
        Path(quality_markdown).write_text(render_quality_markdown(report), encoding="utf-8")
    schema = feature_schema_payload()
    (target / "feature_schema.json").write_text(_dump(schema), encoding="utf-8")
    metadata = {
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "dataset_version": dataset.summary["dataset_version"],
        "dataset_checksums": checksums,
        "fit_scope": transformer.fit_scope,
        "preprocessing": transformer.config,
        "feature_columns": schema["feature_columns"],
        "key_columns": schema["key_columns"],
        "exported_subsets": list(EXPORT_SUBSETS),
        "frozen_subsets_not_exported": list(FROZEN_SUBSETS),
        "row_counts": {subset: int(len(frame)) for subset, frame in frames.items()},
    }
    (target / "fit_metadata.json").write_text(_dump(metadata), encoding="utf-8")
    transformer.save(target / "text_transformer.joblib")
    manifest = {"feature_spec_version": FEATURE_SPEC_VERSION, "files": {}}
    for path in sorted(target.iterdir()):
        if path.name == "artifact_manifest.json" or not path.is_file():
            continue
        manifest["files"][path.name] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
    (target / "artifact_manifest.json").write_text(_dump(manifest), encoding="utf-8")
    return target


def _checksums(data_dir: Path) -> dict:
    manifest = json.loads((data_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    return {name: meta["sha256"] for name, meta in manifest["files"].items()}


def _dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
