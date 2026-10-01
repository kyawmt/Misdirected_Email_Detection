"""Read the stored records the documents are generated from.

Standard library only. Two rules hold for every read:

* Members named in `SEALED_KEYS` are removed from the raw text before the JSON
  is parsed, and only explicit key paths are taken from what is left. The
  frozen test record also holds per-draft outcomes for frozen test drafts. The
  scanner reads past their characters to find where each member ends, the way
  a CSV reader reads past a row it skips, but never decodes them: no per-draft
  object, string, or number is constructed, kept, or emitted (`strip_members`,
  `read_json`, `allow_listed`).
* Nothing here scores, fits, or opens a data table. The dataset is represented by
  its manifest and its quality report, which hold counts and checksums only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from med_docs.version import (
    API_LATENCY_PATH,
    DATASET_DIR,
    DEPLOY_DIR,
    FEATURES_DIR,
    FROZEN_SUBSETS,
    MODEL_DIR,
    MONITOR_DIR,
    POLICY_DIR,
    SEALED_KEYS,
    SELECTION_SUBSET,
    DIAGNOSTIC_SUBSET,
    TEST_SUBSET_PATHS,
    TEST_TOP_PATHS,
    VALIDATION_SUBSET_PATHS,
    VALIDATION_SUBSETS,
    VALIDATION_TOP_PATHS,
)


class RecordError(ValueError):
    """A stored record is missing or lacks a field the documents need."""


# ------------------------------------------------------------------ low level


def _string_end(text: str, i: int) -> int:
    """Index just past the JSON string that starts at `text[i]` (a quote). Escapes are stepped over, not decoded."""
    i += 1
    while True:
        char = text[i]
        if char == "\\":
            i += 2
        elif char == '"':
            return i + 1
        else:
            i += 1


def _skip_space(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _value_end(text: str, i: int) -> int:
    """Index just past the JSON value that starts at or after `i`, found by structure alone."""
    i = _skip_space(text, i)
    if text[i] == '"':
        return _string_end(text, i)
    if text[i] in "{[":
        depth = 0
        while True:
            char = text[i]
            if char == '"':
                i = _string_end(text, i)
                continue
            if char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
    while i < len(text) and text[i] not in ",}] \t\r\n":
        i += 1
    return i


def strip_members(text: str, drop: Iterable[str]) -> str:
    """The JSON text without any object member whose key is in `drop`, at any depth.

    Works on the characters only: a dropped member's value is skipped by matching
    brackets and strings, never decoded, so none of its content becomes a Python
    object. Keys are decoded only to compare them with `drop`.
    """
    dropped = frozenset(drop)
    if not dropped:
        return text
    out: list[str] = []
    stack: list[str] = []
    expect_key = False
    i, n = 0, len(text)
    while i < n:
        char = text[i]
        if char == '"':
            end = _string_end(text, i)
            if stack and stack[-1] == "{" and expect_key and json.loads(text[i:end]) in dropped:
                colon = _skip_space(text, end)
                if text[colon] != ":":
                    raise RecordError("A record is not valid JSON")
                after = _value_end(text, colon + 1)
                while out and out[-1].isspace():
                    out.pop()
                if out and out[-1] == ",":
                    out.pop()  # a later member: drop the comma before it
                else:
                    after = _skip_space(text, after)
                    if after < n and text[after] == ",":
                        after += 1  # the first member: drop the comma after it
                i = after
                continue
            out.append(text[i:end])
            expect_key = False
            i = end
            continue
        if char in "{[":
            stack.append(char)
            expect_key = char == "{"
        elif char in "}]":
            stack.pop()
            expect_key = False
        elif char == ",":
            expect_key = bool(stack) and stack[-1] == "{"
        out.append(char)
        i += 1
    return "".join(out)


def read_json(path: Path, drop: Iterable[str] = ()) -> Any:
    """Parse a JSON file after removing every object member named in `drop` from its text."""
    path = Path(path)
    if not path.is_file():
        raise RecordError(f"{path} does not exist. The documents are generated from stored records only.")
    return json.loads(strip_members(path.read_text(encoding="utf-8"), drop))


def pick(tree: Any, path: str) -> Any:
    """Follow one key path. Siblings are never touched."""
    node = tree
    for part in path.split("/"):
        if not isinstance(node, dict) or part not in node:
            raise RecordError(f"A record lacks {path!r}")
        node = node[part]
    return node


def allow_listed(tree: Any, paths: Iterable[str]) -> dict[str, Any]:
    """The listed paths and nothing else."""
    return {path: pick(tree, path) for path in paths}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _nest(flat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, value in flat.items():
        node = out
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return out


# ----------------------------------------------------------- evaluation files


def evaluation_aggregates(path: Path, subsets: tuple[str, ...], top_paths: tuple[str, ...], subset_paths: tuple[str, ...]) -> dict:
    """Aggregates from an evaluation record, through an explicit allow-list of key paths."""
    tree = read_json(path, SEALED_KEYS)
    top = _nest(allow_listed(tree, top_paths))
    blocks = pick(tree, "subsets")
    chosen = {}
    for name in subsets:
        chosen[name] = _nest(allow_listed(pick(blocks, name), subset_paths))
    del tree, blocks
    return {"top": top, "subsets": chosen}


def test_aggregates(path: Path) -> dict:
    """The one recorded test pass: the allow-listed aggregate fields only."""
    return evaluation_aggregates(path, FROZEN_SUBSETS, TEST_TOP_PATHS, TEST_SUBSET_PATHS)


def validation_aggregates(path: Path) -> dict:
    return evaluation_aggregates(path, VALIDATION_SUBSETS, VALIDATION_TOP_PATHS, VALIDATION_SUBSET_PATHS)


# ------------------------------------------------------------- other records


def _dataset(root: Path) -> dict:
    manifest = read_json(root / DATASET_DIR / "dataset_manifest.json")
    quality = read_json(root / DATASET_DIR / "quality_report.json")
    checks = {item["id"]: {"passed": item["passed"], "name": item["name"], "detail": item["detail"]} for item in quality["checks"]}
    return {
        "dataset_version": manifest["dataset_version"],
        "generator_version": manifest["generator_version"],
        "seed": manifest["seed"],
        "prevalence": manifest["prevalence_assumption"],
        "freeze": manifest["freeze"],
        "splits": manifest["splits"],
        "row_counts": manifest["row_counts"],
        "files": {name: info["sha256"] for name, info in manifest["files"].items()},
        "quality": {"passed": bool(quality["passed"]), "checks": checks},
    }


def _features(root: Path) -> dict:
    manifest = read_json(root / FEATURES_DIR / "artifact_manifest.json")
    quality = read_json(root / FEATURES_DIR / "quality_report.json")
    return {
        "feature_spec_version": manifest["feature_spec_version"],
        "files": {name: {"bytes": info["bytes"], "sha256": info["sha256"]} for name, info in manifest["files"].items()},
        "fit_scope": {key: quality["fit_scope"][key] for key in ("corpus", "document_count", "vocabulary_size", "fit_sent_at_end_exclusive", "warmup_included")},
        "five_minute_recency": quality["shortcut_checks"]["five_minute_recency"],
    }


def _model(root: Path) -> dict:
    meta = read_json(root / MODEL_DIR / "model_metadata.json")
    experiments = read_json(root / MODEL_DIR / "experiments.json")
    runs = []
    for run in experiments["runs"]:
        email = run["validation_product_like"]["email"]
        diagnostic = run["validation_diagnostic"]["email"]
        runs.append(
            {
                "name": run["name"],
                "kind": run["kind"],
                "ablation": run["ablation"],
                "n_features": run["n_features"],
                "simplicity": run["simplicity"],
                "eligible": run["eligible"],
                "config": run["config"],
                "cv_mean": run["cv"]["mean"],
                "ap": email["average_precision"],
                "ap_low": email["bootstrap"]["average_precision"]["low"],
                "ap_high": email["bootstrap"]["average_precision"]["high"],
                "positives": email["positives"],
                "emails": email["n"],
                "diagnostic_ap": diagnostic["average_precision"],
            }
        )
    family = experiments["eligibility"]["families"]["logistic_balanced"]
    return {
        "metadata": {key: meta[key] for key in ("model_version", "kind", "ablation", "run_name", "config", "recency_fill_days", "scores_are", "calibration", "thresholds", "seed", "sklearn_version", "numpy_version", "training_subset")}
        | {"n_features": len(meta["feature_columns"])},
        "selected": experiments["selected"],
        "c_grid": experiments["c_grid"],
        "train": {"recipient_rows": experiments["train_rows"], "positive_rows": experiments["train_positive_rows"], "positive_emails": experiments["train_positive_emails"]},
        "folds_scored": next(run for run in experiments["runs"] if run["name"] == experiments["selected"])["cv"]["n_folds_scored"],
        "folds": [{"fold": item["fold"], "week_start": item["week_start"], "week_end": item["week_end"], "n_drafts": item["n_drafts"], "n_positive_emails": item["n_positive_emails"]} for item in experiments["folds"]],
        "audit": {
            "passed": experiments["eligibility"]["audit"]["passed"],
            "flagged_content": list(experiments["eligibility"]["audit"]["flagged_content"]),
            "content_separation": experiments["eligibility"]["audit"]["content_separation"],
            "auc_bounds": list(experiments["eligibility"]["audit"]["auc_bounds"]),
        },
        "eligibility": {
            "checks": family["checks"],
            "eligible": family["eligible"],
            "min_margin_over_behavior_only": family["fold_stability"]["min_margin"],
            "min_margin_over_content_only": family["not_content_alone"]["min_margin"],
        },
        "runs": runs,
    }


def _api_latency(root: Path) -> dict:
    record = read_json(root / API_LATENCY_PATH)
    keys = (
        "boundary",
        "subset",
        "warmup_calls",
        "measured_calls",
        "concurrency",
        "statuses",
        "client_p50_ms",
        "client_p95_ms",
        "client_p99_ms",
        "cold_start_seconds",
        "target_p95_ms",
        "ac05",
        "environment",
        "versions",
    )
    return {key: record[key] for key in keys} | {"parity": {k: record["parity"][k] for k in ("assessed", "decisions_matching_validation_table")}}


def _monitor(root: Path) -> dict:
    directory = root / MONITOR_DIR
    replay = read_json(directory / "replay.json")
    windows = []
    for window in replay["windows"]:
        summary = window["summary"]
        windows.append(
            {
                "window": window["window"],
                "role": window["role"],
                "injected_emails": window["injected_emails"],
                "planned_injected_share": window["planned_injected_share"],
                "requests": summary["requests"],
                "warnings": summary["warnings"],
                "unable_to_assess": summary["unable_to_assess"],
                "limited_history_emails": summary["emails_with_limited_relationship_history"],
                "near_band_emails": summary["near_band_emails"],
                "highest_allowed": summary["highest_allowed_email_risk"],
                "margin_to_cutoff": summary["margin_to_cutoff"],
            }
        )
    reference = replay["blocks"]["reference"]["summary"]
    bundle_checks = read_json(directory / "bundle_checks.json")
    feedback = read_json(directory / "feedback_review.json")
    return {
        "monitor_version": replay["monitor_version"],
        "plan_checksum": replay["plan_checksum"],
        "environment": replay["environment"],
        "windows": windows,
        "reference": {key: reference[key] for key in ("requests", "assessed", "warnings", "unable_to_assess", "emails_with_limited_relationship_history", "near_band_emails", "highest_allowed_email_risk", "margin_to_cutoff")},
        "bundle_checks": {
            "all_altered_bundles_refused": bundle_checks["all_altered_bundles_refused"],
            "control_served": bundle_checks["control_served"],
            "frozen_files_edited": bundle_checks["frozen_files_edited"],
            "cases": [{"case": item["case"], "outcome": item["outcome"]} for item in bundle_checks["cases"]],
        },
        "feedback": {
            "reviewed_labels_on_monitored_traffic": feedback["real_reviewed_labels"]["reviewed_labels_on_monitored_traffic"],
            "labels_changed_by_feedback": feedback["labels_changed_by_feedback"],
            "policy_and_model_unchanged": feedback["policy_and_model_unchanged"],
            "label_source": feedback["simulation"]["label_source"],
        },
    }


def _deploy(root: Path) -> dict:
    directory = root / DEPLOY_DIR
    scenario = read_json(directory / "scenario_regression.json")
    fixtures = {}
    for item in scenario["fixtures"]:
        fixtures[item["key"]] = {
            "title": item["title"],
            "kind": item["kind"],
            "draft_id": item["source"].get("draft_id"),
            "scenario": item["scenario"]["id"] if item.get("scenario") else None,
            "desired": item.get("desired"),
            "known_miss": item.get("known_miss", False),
            "derived_from": item.get("derived_from"),
            "expected": item["expected"],
        }
    mutation = read_json(directory / "mutation_checks.json")
    latency = read_json(directory / "latency_api_image.json")
    smoke = {name: read_json(directory / f"smoke_{name}.json") for name in ("process", "container")}
    rehearsal = {mode: read_json(directory / f"rollback_rehearsal_{mode}.json") for mode in ("container", "process")}
    images = read_json(directory / "images.json")
    other = read_json(directory / "other_platform_check.json")
    clean = read_json(directory / "clean_checkout.json")
    digests = read_json(directory / "bundle_digests.json")
    bundle_api = read_json(directory / "bundle_check_api.json")
    return {
        "deploy_version": scenario["deploy_version"],
        "bundle": scenario["bundle"],
        "fixtures": fixtures,
        "mutation": {
            "control_passed": mutation["control_passed"],
            "control_fixtures": mutation["control"]["fixtures"],
            "all_detected": mutation["all_detected"],
            "mutations": [{"mutation": item["mutation"], "change": item["change"], "detected": item["detected"]} for item in mutation["mutations"]],
        },
        "latency": {
            "boundary": latency["boundary"],
            "date_utc": latency["date_utc"],
            "target_p95_ms": latency["target_p95_ms"],
            "ac05": {
                key: latency["ac05"][key]
                for key in ("result", "concurrency", "requests", "failures", "client_p95_ms", "statuses")
            }
            | {"client": latency["ac05"]["client"], "parity": latency["ac05"]["parity_with_stored_validation_scores"]},
            "concurrent_probe": {
                "requests": latency["concurrent_probe"]["requests"],
                "clients": latency["workload"]["concurrent_clients"],
                "failures": latency["concurrent_probe"]["failures"],
                "client": latency["concurrent_probe"]["client"],
            },
            "maximum_input_probe": {"requests": latency["maximum_input_probe"]["requests"], "failures": latency["maximum_input_probe"]["failures"], "client": latency["maximum_input_probe"]["client"]},
            "served": latency["served"],
            "client_machine": latency["client"],
            "target": {"kind": latency["target"]["kind"], "image_id": latency["target"]["container"]["image_id"], "cpus": latency["target"]["container"]["cpus"]},
            "runtime": {"platform": latency["environment_of_measured_process"]["platform"], "python": latency["environment_of_measured_process"]["python"]},
            "docker": latency["target"].get("docker"),
        },
        "smoke": {
            name: {
                "passed": record["passed"],
                "date_utc": record["date_utc"],
                "checks": [{"name": check["name"], "passed": check["passed"]} for check in record["checks"]],
            }
            for name, record in smoke.items()
        },
        "rehearsal": {mode: _rehearsal(record) for mode, record in rehearsal.items()},
        "images": {
            name: {
                "reference": item["identity"]["reference"],
                "id": item["identity"]["id"],
                "size_bytes": item["identity"]["size_bytes"],
                "architecture": item["identity"]["architecture"],
                "user": item["identity"]["user"],
                "base_image": item["base_image"],
                "pyarrow_importable": item["environment"]["pyarrow_importable"],
                "packages": item["environment"]["packages"],
                "files_in_app": len(item["files_in_app"]),
            }
            for name, item in images["images"].items()
        },
        "other_platform": {
            "platform": other["platform"],
            "passed": other["regression"]["passed"],
            "failed": other["regression"]["failed"],
            "cutoff_fixture_decision": other["cutoff_fixture"]["decision"],
        },
        "clean_checkout": {"passed": clean["passed"], "steps": len(clean["steps"]), "not_verified": [clean["not_verified"]] if isinstance(clean["not_verified"], str) else list(clean["not_verified"])},
        "digests": {"files": {name: info["sha256"] for name, info in digests["files"].items()}, "commit": digests["verified_against"]["commit"]},
        "bundle_files": {item["path"]: item["sha256"] for item in bundle_api["files"]},
    }


def _rehearsal(record: dict) -> dict:
    candidates = {}
    healthy = 0
    for step in record["steps"]:
        deployable = step.get("deployable")
        if deployable in (None, "known_good"):
            if "scenario_fixtures" in step and step["scenario_fixtures"]["failed"] == 0:
                healthy += 1
            continue
        candidates[deployable] = {
            "fault": step["fault"],
            "ready_http": step["ready_http"],
            "ready_reason": step["ready_reason"],
            "assess_status": sorted({item["status"] for item in step["assess"].values()}),
            "assess_decisions": sorted({str(item["decision"]) for item in step["assess"].values()}),
            "assess_scores": sorted({str(item["email_risk_score"]) for item in step["assess"].values()}),
            "assessed_fixtures": step["scenario_suite"]["assessed_fixtures"],
            "flagged_by_the_suite": step["scenario_suite"]["flagged_by_the_suite"],
            "assessment_disabled_on_screen": step["review_screen"]["assessment_disabled"],
            "no_decision_shown": step["review_screen"]["no_decision_shown"],
        }
    restores = [step for step in record["steps"] if step["step"].startswith("restore")]
    return {
        "mode": record["mode"],
        "date_utc": record["date_utc"],
        "passed": record["passed"],
        "known_good_unchanged": record["identities"]["known_good_unchanged"],
        "known_good_id": record["identities"]["known_good"].get("id"),
        "steps": len(record["steps"]),
        "steps_passed": sum(1 for step in record["steps"] if step["passed"]),
        "candidates": candidates,
        "restores": [{"step": step["step"], "fixtures_passed": step["scenario_fixtures"]["passed"], "fixtures_failed": step["scenario_fixtures"]["failed"], "ready_http": step["ready_http"]} for step in restores],
        "published_bundle_files_unchanged": record["published_bundle_files_unchanged"],
    }


# --------------------------------------------------------------------- loader


def load(root: Path | str = ".") -> dict:
    """Every record the documents need, reduced to the fields they use."""
    root = Path(root)
    policy_path = root / POLICY_DIR / "policy.json"
    policy = read_json(policy_path)
    return {
        "dataset": _dataset(root),
        "features": _features(root),
        "model": _model(root),
        "policy": policy,
        "policy_sha256": sha256_file(policy_path),
        "validation": validation_aggregates(root / POLICY_DIR / "validation_evaluation.json"),
        "test": test_aggregates(root / POLICY_DIR / "test_evaluation.json"),
        "api_latency": _api_latency(root),
        "monitor": _monitor(root),
        "deploy": _deploy(root),
    }


SOURCES = {
    "dataset": [DATASET_DIR / "dataset_manifest.json", DATASET_DIR / "quality_report.json"],
    "features": [FEATURES_DIR / "artifact_manifest.json", FEATURES_DIR / "quality_report.json"],
    "model": [MODEL_DIR / "model_metadata.json", MODEL_DIR / "experiments.json"],
    "policy": [POLICY_DIR / "policy.json"],
    "validation": [POLICY_DIR / "validation_evaluation.json"],
    "test": [POLICY_DIR / "test_evaluation.json"],
    "api_latency": [API_LATENCY_PATH],
    "monitor": [MONITOR_DIR / name for name in ("replay.json", "bundle_checks.json", "feedback_review.json")],
    "deploy": [
        DEPLOY_DIR / name
        for name in (
            "scenario_regression.json",
            "mutation_checks.json",
            "latency_api_image.json",
            "smoke_process.json",
            "smoke_container.json",
            "rollback_rehearsal_container.json",
            "rollback_rehearsal_process.json",
            "images.json",
            "other_platform_check.json",
            "clean_checkout.json",
            "bundle_digests.json",
            "bundle_check_api.json",
        )
    ],
}
