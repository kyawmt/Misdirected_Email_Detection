"""Read and write the versioned dataset as CSV plus JSON manifests."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from med_data.calendar import SPLIT_WINDOWS, format_ts, parse_ts
from med_data.generate import Dataset, generate_dataset
from med_data.schema import MODEL_INPUT_DENYLIST, TABLES
from med_data.validate import assert_valid, report_payload, validate_dataset
from med_data.version import DATASET_VERSION, GENERATOR_VERSION, SEED

TABLE_FILES = {
    "contacts": "contacts.csv",
    "messages": "messages.csv",
    "message_recipients": "message_recipients.csv",
    "drafts": "drafts.csv",
    "draft_recipients": "draft_recipients.csv",
    "labels": "labels.csv",
    "reviewer_feedback": "reviewer_feedback.csv",
    "split_manifest": "split_manifest.csv",
    "invalid_fixtures": "invalid_fixtures.csv",
}
QUALITY_FILE = "quality_report.json"
MANIFEST_FILE = "dataset_manifest.json"

BOOL_COLUMNS = {
    "is_internal",
    "is_counterfactual",
    "is_walkthrough",
    "intended",
    "is_misdirected_email",
    "frozen",
}
TIME_COLUMNS = {"directory_visible_from", "sent_at", "submitted_at"}


def write_dataset(dataset: Dataset, output_dir: str | Path, *, validate: bool = True) -> Path:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    if validate:
        checks = assert_valid(dataset)
    else:
        checks = validate_dataset(dataset)
        failed = [check for check in checks if not check.passed]
        if failed:
            raise AssertionError(failed[0].detail)
    frames = {
        "contacts": dataset.contacts,
        "messages": dataset.messages,
        "message_recipients": dataset.message_recipients,
        "drafts": dataset.drafts,
        "draft_recipients": dataset.draft_recipients,
        "labels": dataset.labels,
        "reviewer_feedback": dataset.reviewer_feedback,
        "split_manifest": dataset.split_manifest,
        "invalid_fixtures": dataset.invalid_fixtures,
    }
    for name, filename in TABLE_FILES.items():
        _write_frame(frames[name], target / filename, TABLES[name])
    quality_path = target / QUALITY_FILE
    quality_path.write_text(json.dumps(report_payload(checks), indent=2) + "\n", encoding="utf-8")
    manifest = _manifest(dataset, target)
    (target / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def read_dataset(input_dir: str | Path) -> Dataset:
    source = Path(input_dir)
    frames = {
        name: _read_frame(source / filename, TABLES[name]) for name, filename in TABLE_FILES.items()
    }
    manifest = json.loads((source / MANIFEST_FILE).read_text(encoding="utf-8"))
    summary = {
        "seed": manifest["seed"],
        "generator_version": manifest["generator_version"],
        "dataset_version": manifest["dataset_version"],
        "messages": int(len(frames["messages"])),
        "drafts": int(len(frames["drafts"])),
        "subsets": manifest["row_counts"]["subsets"],
    }
    return Dataset(
        contacts=frames["contacts"],
        messages=frames["messages"],
        message_recipients=frames["message_recipients"],
        drafts=frames["drafts"],
        draft_recipients=frames["draft_recipients"],
        labels=frames["labels"],
        reviewer_feedback=frames["reviewer_feedback"],
        split_manifest=frames["split_manifest"],
        invalid_fixtures=frames["invalid_fixtures"],
        seed=int(manifest["seed"]),
        summary=summary,
    )


def verify_files(input_dir: str | Path) -> None:
    source = Path(input_dir)
    manifest = json.loads((source / MANIFEST_FILE).read_text(encoding="utf-8"))
    for filename, expected in manifest["files"].items():
        path = source / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected["sha256"]:
            raise AssertionError(f"Checksum mismatch for {filename}")
        frame_rows = expected["rows"]
        if filename.endswith(".csv"):
            with path.open(encoding="utf-8") as handle:
                rows = sum(1 for _ in handle) - 1
            if rows != frame_rows:
                raise AssertionError(f"Row count mismatch for {filename}")


def _manifest(dataset: Dataset, directory: Path) -> dict:
    files = {}
    for filename in list(TABLE_FILES.values()) + [QUALITY_FILE]:
        path = directory / filename
        files[filename] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "rows": _row_count(path),
        }
    return {
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": dataset.seed,
        "prevalence_assumption": {
            "product_like_rate": "0.005",
            "product_like_meaning": "Five misdirected emails per 1,000 product-like emails.",
            "train_enriched_rate": "0.10",
            "statement": (
                "Product-like prevalence is a simulation assumption, not a measured "
                "real-world rate. The training subset is enriched and is not an "
                "operating point. Precision at a fixed recall and false-positive rate "
                "changes when prevalence changes."
            ),
        },
        "freeze": {
            "subsets": ["test_product_like", "test_diagnostic"],
            "policy": (
                "Do not use the frozen test subsets to choose features, models, or "
                "thresholds. A new seed or generator version requires a new dataset version."
            ),
        },
        "splits": {
            name: {"start": start, "end": end, "end_exclusive": True}
            for name, start, end in SPLIT_WINDOWS
        },
        "row_counts": dataset.summary,
        "model_input_denylist": sorted(MODEL_INPUT_DENYLIST),
        "files": files,
    }


def _row_count(path: Path) -> int:
    if path.suffix == ".json":
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _write_frame(frame: pd.DataFrame, path: Path, columns: list[str]) -> None:
    ordered = frame.loc[:, columns]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in ordered.itertuples(index=False, name=None):
            writer.writerow([_cell(value) for value in row])


def _cell(value) -> str:
    if value is None or value is pd.NA:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, pd.Timestamp):
        return format_ts(value.to_pydatetime())
    if isinstance(value, datetime):
        return format_ts(value)
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value)


def _read_frame(path: Path, columns: list[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != columns:
        raise ValueError(f"{path.name} columns do not match the schema")
    for column in columns:
        if column in BOOL_COLUMNS:
            frame[column] = frame[column].map({"true": True, "false": False})
        elif column in TIME_COLUMNS:
            frame[column] = frame[column].map(parse_ts)
    return frame


def build_to(output_dir: str | Path, seed: int = SEED) -> Path:
    return write_dataset(generate_dataset(seed), output_dir)
