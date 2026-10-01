"""Is the published bundle a process would serve present, complete, and compatible?

`check_bundle` runs the same verification the API performs at startup
(dataset checksums and record counts, feature-artifact checksums and spec
version, policy, model, and cutoff), without loading the history index and
without scoring anything. It never fits, never writes, and never opens a file
that holds frozen test outcomes. CI and the image builds call it so a missing
or incompatible bundle fails before anything is served.

Two scopes match the two processes:

- `api`: everything `med_api` loads at startup.
- `ui`: the files `med_ui` reads. The UI has no model or feature artifact and
  cannot score.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path

from med_deploy.version import (
    DEPLOY_VERSION,
    DIGESTS_RECORD,
    FORBIDDEN_FILES,
    FORBIDDEN_PREFIXES,
    FROZEN_SUBSETS,
    SNAPSHOT_ID,
)

API_SCOPE = "api"
UI_SCOPE = "ui"
# The tables `med_ui` streams (validation records only are kept) and the stored
# validation files it reads from the policy directory.
UI_DATA_FILES = ("contacts.csv", "draft_recipients.csv", "drafts.csv", "labels.csv", "split_manifest.csv")
UI_POLICY_FILES = ("policy.json", "validation_evaluation.json", "validation_scores.csv")
VALIDATION_SCORE_COLUMNS = ("draft_id", "email_risk", "misdirected", "warned")
# Files in the policy directory that no other checksum covers: the dataset manifest covers the tables, the feature
# manifest covers the feature files, and policy.json covers the model and the feature manifest, but nothing covers
# policy.json itself (a changed T_warn is still a finite number) or the two stored validation files. Each scope checks
# the ones it copies against `bundle_digests.json`, which was verified against the published blobs in git when recorded.
UNANCHORED = {
    API_SCOPE: ("policy.json",),
    UI_SCOPE: ("policy.json", "validation_evaluation.json", "validation_scores.csv"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    """Parsed CSV records without the header. A quoted body can hold newlines."""
    with open(path, encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in csv.reader(handle)) - 1, 0)


class _Checks:
    """Run named checks, keep every outcome, and never let one failure hide the next."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def run(self, name: str, function):
        try:
            detail = function()
        except Exception as error:  # the checker reports; it does not crash
            self.items.append({"name": name, "passed": False, "detail": f"{type(error).__name__}: {error}"})
            return None
        self.items.append({"name": name, "passed": True, "detail": detail if isinstance(detail, str) else "ok"})
        return detail

    @property
    def ok(self) -> bool:
        return all(item["passed"] for item in self.items)


# ------------------------------------------------------------------ required files


def _relative(path: Path, root: Path) -> str:
    """The path under `root`, without following symlinks."""
    try:
        return Path(os.path.abspath(path)).relative_to(os.path.abspath(root)).as_posix()
    except ValueError:
        return Path(path).as_posix()


def required_files(scope: str, *, data_dir: Path, features_dir: Path | None, model_path: Path | None, policy_dir: Path, root: Path) -> list[Path]:
    """The files a process of this scope reads, derived from the bundle's own manifests."""
    data_dir, policy_dir = Path(data_dir), Path(policy_dir)
    if scope == UI_SCOPE:
        files = [data_dir / name for name in UI_DATA_FILES] + [policy_dir / name for name in UI_POLICY_FILES]
        return sorted(files, key=lambda path: _relative(path, root))
    dataset_manifest = json.loads((data_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    files = [data_dir / "dataset_manifest.json"] + [data_dir / name for name in dataset_manifest["files"]]
    feature_manifest = json.loads((Path(features_dir) / "artifact_manifest.json").read_text(encoding="utf-8"))
    files += [Path(features_dir) / "artifact_manifest.json"] + [Path(features_dir) / name for name in feature_manifest["files"]]
    files += [Path(model_path), policy_dir / "policy.json"]
    return sorted(files, key=lambda path: _relative(path, root))


def _image_contents(root: Path, needed: list[Path]) -> str:
    """The application directory holds exactly `needed`: nothing missing, nothing else, no frozen-outcome file."""
    root = Path(root)
    wanted = {_relative(path, root) for path in needed}
    present = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    missing, extra = sorted(wanted - present), sorted(present - wanted)
    forbidden = sorted(item for item in present if Path(item).name in FORBIDDEN_FILES or Path(item).name.startswith(FORBIDDEN_PREFIXES))
    if missing or extra or forbidden:
        raise ValueError(f"missing {missing}; unexpected {extra}; frozen-outcome files {forbidden}")
    return f"{len(present)} files, exactly the {len(wanted)} this process reads"


# ------------------------------------------------------------------ the check


def check_bundle(
    scope: str = API_SCOPE,
    *,
    root: Path = Path("."),
    data_dir: Path | None = None,
    features_dir: Path | None = None,
    model_path: Path | None = None,
    policy_path: Path | None = None,
    dataset_manifest: Path | None = None,
    digests: Path | None = None,
    image: bool = False,
) -> dict:
    """Verify the bundle for one process. The result lists every check and its outcome.

    With `image`, `root` is an image's application directory and must hold
    exactly the files this scope reads: nothing missing and nothing extra.
    `digests` is the manifest of expected SHA-256 values for the files nothing
    else checksums; it defaults to the one under `root`.
    """
    from med_api.version import DEFAULT_PATHS

    root = Path(root)
    data_dir = Path(data_dir) if data_dir else root / DEFAULT_PATHS["data"]
    features_dir = Path(features_dir) if features_dir else root / DEFAULT_PATHS["features"]
    model_path = Path(model_path) if model_path else root / DEFAULT_PATHS["model"]
    policy_path = Path(policy_path) if policy_path else root / DEFAULT_PATHS["policy"]
    checks = _Checks()
    bundle: dict = {}

    if scope == API_SCOPE:
        _api_checks(checks, bundle, data_dir, features_dir, model_path, policy_path)
    elif scope == UI_SCOPE:
        _ui_checks(checks, bundle, data_dir, policy_path, dataset_manifest or data_dir / "dataset_manifest.json")
    else:
        raise ValueError(f"Unknown scope {scope!r}")
    checks.run("anchored_digests", lambda: _anchored_digests(scope, root, policy_path.parent, Path(digests) if digests else root / DIGESTS_RECORD))

    files = []
    try:
        needed = required_files(scope, data_dir=data_dir, features_dir=features_dir, model_path=model_path, policy_dir=policy_path.parent, root=root)
        if image:
            checks.run("image_contents_exact", lambda: _image_contents(root, needed))
        for path in needed:
            exists = path.is_file()
            files.append(
                {
                    "path": _relative(path, root),
                    "bytes": path.stat().st_size if exists else None,
                    "sha256": sha256_file(path) if exists else None,
                }
            )
    except Exception as error:  # a missing manifest is already reported by a check above
        files.append({"path": None, "bytes": None, "sha256": None, "error": f"{type(error).__name__}: {error}"})
    return {
        "kind": "bundle_check",
        "deploy_version": DEPLOY_VERSION,
        "scope": scope,
        "ok": checks.ok,
        "bundle": bundle,
        "checks": checks.items,
        "files": files,
    }


def _anchored_digests(scope: str, root: Path, policy_dir: Path, manifest_path: Path) -> str:
    """Each file this scope copies that no other checksum covers must equal its anchored SHA-256."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    names = UNANCHORED[scope]
    for name in names:
        relative = _relative(policy_dir / name, root)
        entry = manifest["files"].get(relative)
        if entry is None:
            raise ValueError(f"{relative} has no anchored digest in {Path(manifest_path).name}")
        actual = sha256_file(policy_dir / name)
        if actual != entry["sha256"]:
            raise ValueError(f"{relative} differs from its anchored digest (found {actual[:16]}..., anchored {entry['sha256'][:16]}...)")
    return f"{len(names)} file(s) equal the digests anchored in {Path(manifest_path).name}: {', '.join(names)}"


def _api_checks(checks: _Checks, bundle: dict, data_dir: Path, features_dir: Path, model_path: Path, policy_path: Path) -> None:
    from med_data.io import verify_files
    from med_features.text_model import FittedText
    from med_models.data import verify_feature_artifact
    from med_policy.decision import load_bundle

    def dataset_files():
        verify_files(data_dir)
        return "every table and the quality report match dataset_manifest.json (checksums and record counts)"

    def dataset_version():
        manifest = json.loads((data_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
        if manifest["dataset_version"] != SNAPSHOT_ID:
            raise ValueError(f"dataset is {manifest['dataset_version']}, expected {SNAPSHOT_ID}")
        bundle["dataset_version"] = manifest["dataset_version"]
        bundle["generator_version"] = manifest["generator_version"]
        return f"{manifest['dataset_version']}, generator {manifest['generator_version']}"

    def feature_artifact():
        manifest = verify_feature_artifact(features_dir)
        bundle["feature_spec_version"] = manifest["feature_spec_version"]
        return f"{manifest['feature_spec_version']}: {len(manifest['files'])} files match artifact_manifest.json"

    def policy_and_model():
        loaded = load_bundle(policy_path, model_path, features_dir / "artifact_manifest.json")
        bundle.update(
            {
                "policy_version": loaded.policy["policy_version"],
                "model_version": loaded.policy["model_version"],
                "model_run_name": loaded.policy["model_run_name"],
                "T_warn": loaded.t_warn,
                "blocking_enabled": loaded.policy["blocking_enabled"],
                "calibration": loaded.policy["calibration"],
                "scores_are": loaded.policy["scores_are"],
                "checksums": dict(loaded.policy["checksums"]),
            }
        )
        return "versions, run name, model and feature-manifest checksums, blocking disabled, cutoff finite, calibration not fit"

    def policy_matches_snapshot():
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        if policy["dataset_version"] != SNAPSHOT_ID:
            raise ValueError(f"policy names dataset {policy['dataset_version']}, the served snapshot is {SNAPSHOT_ID}")
        return f"policy dataset {policy['dataset_version']}"

    def text_transformer():
        FittedText.load(features_dir / "text_transformer.joblib")
        return "loads without refitting"

    def no_frozen_features():
        found = sorted(path.name for path in features_dir.glob("features_test_*"))
        if found:
            raise ValueError(f"frozen feature matrices present: {found}")
        return "no features_test_* file in the feature artifact"

    checks.run("dataset_files", dataset_files)
    checks.run("dataset_version", dataset_version)
    checks.run("feature_artifact", feature_artifact)
    checks.run("policy_and_model", policy_and_model)
    checks.run("policy_matches_snapshot", policy_matches_snapshot)
    checks.run("text_transformer", text_transformer)
    checks.run("no_frozen_features", no_frozen_features)


def _ui_checks(checks: _Checks, bundle: dict, data_dir: Path, policy_path: Path, dataset_manifest: Path) -> None:
    from med_policy.decision import REQUIRED_KEYS
    from med_features.schema import FEATURE_SPEC_VERSION
    from med_models.version import MODEL_VERSION
    from med_policy.version import POLICY_VERSION

    policy_dir = policy_path.parent

    def policy_file():
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        missing = [key for key in REQUIRED_KEYS if key not in policy]
        if missing:
            raise ValueError(f"policy is missing {missing}")
        for key, expected in (("policy_version", POLICY_VERSION), ("model_version", MODEL_VERSION), ("feature_spec_version", FEATURE_SPEC_VERSION), ("dataset_version", SNAPSHOT_ID)):
            if policy[key] != expected:
                raise ValueError(f"policy {key} is {policy[key]}, this code expects {expected}")
        if policy["blocking_enabled"] is not False or policy["T_block"] is not None:
            raise ValueError("blocking must be disabled with T_block null")
        t_warn = policy["T_warn"]
        if isinstance(t_warn, bool) or not isinstance(t_warn, (int, float)) or not math.isfinite(t_warn):
            raise ValueError("T_warn must be a finite number")
        bundle.update(
            {
                "policy_version": policy["policy_version"],
                "model_version": policy["model_version"],
                "feature_spec_version": policy["feature_spec_version"],
                "dataset_version": policy["dataset_version"],
                "T_warn": t_warn,
                "blocking_enabled": policy["blocking_enabled"],
                "calibration": policy["calibration"],
                "scores_are": policy["scores_are"],
            }
        )
        return "versions match this code, blocking disabled, cutoff finite"

    def validation_files():
        with open(policy_dir / "validation_scores.csv", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [name for name in VALIDATION_SCORE_COLUMNS if name not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"validation_scores.csv lacks {missing}")
            warned = sum(1 for row in reader if row["warned"] == "True")
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        expected = policy["validation_confusion"]["warnings"]
        if warned != expected:
            raise ValueError(f"validation_scores.csv warns on {warned} drafts, policy.json records {expected}")
        json.loads((policy_dir / "validation_evaluation.json").read_text(encoding="utf-8"))
        return f"validation_scores.csv warns on {warned} drafts, as policy.json records; validation_evaluation.json parses"

    def dataset_files():
        manifest = json.loads(Path(dataset_manifest).read_text(encoding="utf-8"))
        if manifest["dataset_version"] != SNAPSHOT_ID:
            raise ValueError(f"dataset is {manifest['dataset_version']}, expected {SNAPSHOT_ID}")
        for name in UI_DATA_FILES:
            expected = manifest["files"][name]
            path = data_dir / name
            if sha256_file(path) != expected["sha256"]:
                raise ValueError(f"checksum mismatch for {name}")
            if _record_count(path) != expected["rows"]:
                raise ValueError(f"record count mismatch for {name}")
        return f"{len(UI_DATA_FILES)} tables match dataset_manifest.json (checksums and record counts)"

    checks.run("policy_file", policy_file)
    checks.run("validation_files", validation_files)
    checks.run("dataset_files", dataset_files)
    bundle["frozen_subsets"] = list(FROZEN_SUBSETS)
