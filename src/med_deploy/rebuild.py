"""A rebuild of the feature artifact and the model into a scratch directory, compared with the published files.

This is a demonstration that the published bundle can be reproduced, not part of
installing, building an image, or CI. Every output goes to a scratch directory:

    python -m med_features build --output <scratch>/features
    python -m med_models run --features <scratch>/features --output <scratch>/model --docs <scratch>/docs

The feature and model commands do not refuse to overwrite their default output
directories, and `med_models run` rewrites `docs/phase_4` by default, so this
module never runs either without all of its output paths. It reads the
published dataset, never a frozen subset's features, and never selects a
cutoff or runs the frozen evaluation. The published files are hashed before and
after to show they were not touched.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from med_deploy.records import machine, now_utc
from med_deploy.version import DEPLOY_VERSION, FEATURES_DIR, MODEL_PATH

MODEL_DIR = Path(MODEL_PATH).parent
DOCS_PHASE_4 = Path("docs/phase_4")
# Keys that hold a wall-clock measurement or a time stamp; a rebuild is expected to differ in them.
TIMING_KEYS = ("seconds", "runtime", "elapsed", "created_at", "duration", "time")


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tree_hashes(root: Path, directory: Path) -> dict[str, str]:
    base = Path(root) / directory
    return {path.relative_to(root).as_posix(): _digest(path) for path in sorted(base.rglob("*")) if path.is_file()}


def _json_differences(left, right, path: str = "") -> list[str]:
    """Paths at which two JSON values differ, ignoring keys that hold a timing or time stamp."""
    if isinstance(left, dict) and isinstance(right, dict):
        found = []
        for key in sorted(set(left) | set(right)):
            if any(word in str(key).lower() for word in TIMING_KEYS):
                continue
            if key not in left or key not in right:
                found.append(f"{path}/{key} (present only in the {'published' if key in left else 'rebuilt'} file)")
            else:
                found += _json_differences(left[key], right[key], f"{path}/{key}")
        return found
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return [f"{path} (length {len(left)} against {len(right)})"]
        found = []
        for index, (a, b) in enumerate(zip(left, right)):
            found += _json_differences(a, b, f"{path}[{index}]")
        return found
    if isinstance(left, float) and isinstance(right, float) and not (np.isnan(left) or np.isnan(right)):
        return [] if left == right else [f"{path} ({left!r} against {right!r})"]
    return [] if left == right else [f"{path}"]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _header_of(lines: list[str], index: int) -> list[str] | None:
    """The header row of the markdown table that line `index` belongs to, if it is a table row."""
    if not lines[index].lstrip().startswith("|"):
        return None
    start = index
    while start > 0 and lines[start - 1].lstrip().startswith("|"):
        start -= 1
    return _cells(lines[start])


def _differing_columns(changed: list[tuple]) -> set[str] | None:
    """The table columns in which every differing line differs, or None if a difference is outside table cells."""
    columns: set[str] = set()
    for old, new, header in changed:
        if header is None or not new.lstrip().startswith("|"):
            return None
        left, right = _cells(old), _cells(new)
        if len(left) != len(right) or len(left) != len(header):
            return None
        columns |= {header[i] for i in range(len(left)) if left[i] != right[i]}
    return columns


def _compare_file(published: Path, rebuilt: Path) -> tuple[bool, str]:
    if not rebuilt.exists():
        return False, "not produced by the rebuild"
    if _digest(published) == _digest(rebuilt):
        return True, "byte-identical"
    if published.suffix == ".json":
        differences = _json_differences(json.loads(published.read_text(encoding="utf-8")), json.loads(rebuilt.read_text(encoding="utf-8")))
        if not differences:
            return False, "same content apart from timing and time-stamp fields"
        return False, f"{len(differences)} differing value(s), for example: " + "; ".join(differences[:3])
    if published.suffix == ".csv":
        left, right = pd.read_csv(published, float_precision="round_trip"), pd.read_csv(rebuilt, float_precision="round_trip")
        if left.shape != right.shape or list(left.columns) != list(right.columns):
            return False, f"shape {left.shape} against {right.shape}"
        numeric = left.select_dtypes("number").columns
        worst = float(np.nanmax(np.abs(left[numeric].to_numpy() - right[numeric].to_numpy()))) if len(numeric) else 0.0
        return False, f"same shape; largest numeric difference {worst:.3e}"
    if published.suffix == ".md":
        a, b = published.read_text(encoding="utf-8").splitlines(), rebuilt.read_text(encoding="utf-8").splitlines()
        if len(a) != len(b):
            return False, f"{len(a)} lines against {len(b)}"
        changed = [(x, y, _header_of(a, index)) for index, (x, y) in enumerate(zip(a, b)) if x != y]
        columns = _differing_columns(changed)
        if columns is not None:
            return False, f"{len(changed)} of {len(a)} lines differ, only in the table column(s): {', '.join(sorted(columns))}"
        return False, f"{len(changed)} differing line(s) of {len(a)}, not limited to table cells"
    return False, "bytes differ"


def _scores_on_validation(published_model: Path, rebuilt_model: Path, features: Path) -> dict:
    """Both models score the published validation features; how far apart are the scores?"""
    from med_features.build import read_features
    from med_models.package import load_model

    frame = read_features(Path(features) / "features_validation_product_like.csv")
    a, b = load_model(published_model), load_model(rebuilt_model)
    first, second = a.score_frame(frame), b.score_frame(frame)
    return {
        "rows": int(len(frame)),
        "same_feature_columns": a.feature_columns == b.feature_columns,
        "same_run_name": a.metadata.get("run_name") == b.metadata.get("run_name"),
        "max_abs_score_difference": float(np.max(np.abs(first - second))),
        "identical_scores": bool(np.array_equal(first, second)),
    }


def rebuild_demo(root: Path) -> dict:
    root = Path(root).resolve()
    watched = [FEATURES_DIR, MODEL_DIR, DOCS_PHASE_4]
    before = {str(item): _tree_hashes(root, item) for item in watched}
    with tempfile.TemporaryDirectory(prefix="med-rebuild-") as raw:
        scratch = Path(raw)
        commands = [
            [sys.executable, "-m", "med_features", "build", "--output", str(scratch / "features")],
            [sys.executable, "-m", "med_models", "run", "--features", str(scratch / "features"), "--output", str(scratch / "model"), "--docs", str(scratch / "docs")],
        ]
        seconds = []
        for command in commands:
            begin = time.perf_counter()
            completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
            seconds.append(round(time.perf_counter() - begin, 1))
            if completed.returncode != 0:
                raise RuntimeError(f"{' '.join(command[1:4])} failed: {completed.stderr.strip()[-400:]}")
        files = []
        for published in sorted((root / FEATURES_DIR).iterdir()):
            identical, note = _compare_file(published, scratch / "features" / published.name)
            files.append({"file": (FEATURES_DIR / published.name).as_posix(), "identical": identical, "note": note})
        for published in sorted((root / MODEL_DIR).iterdir()):
            identical, note = _compare_file(published, scratch / "model" / published.name)
            files.append({"file": (MODEL_DIR / published.name).as_posix(), "identical": identical, "note": note})
        for published in sorted((root / DOCS_PHASE_4).iterdir()):
            identical, note = _compare_file(published, scratch / "docs" / published.name)
            files.append({"file": (DOCS_PHASE_4 / published.name).as_posix(), "identical": identical, "note": note})
        scores = _scores_on_validation(root / MODEL_PATH, scratch / "model" / "model.joblib", root / FEATURES_DIR)
    after = {str(item): _tree_hashes(root, item) for item in watched}
    identical_count = sum(1 for item in files if item["identical"])
    summary = (
        f"{identical_count} of {len(files)} compared files are byte-identical. "
        f"Scoring the published validation features ({scores['rows']:,} rows) with the rebuilt model and the published model gives "
        + ("identical scores" if scores["identical_scores"] else f"scores that differ by at most {scores['max_abs_score_difference']:.2e}")
        + f"; same feature columns: {scores['same_feature_columns']}; same selected run: {scores['same_run_name']}. "
        "Files that are not byte-identical are listed with what differs. The rebuilt files were written to a scratch directory and discarded; the published files were not used as outputs."
    )
    return {
        "kind": "rebuild_comparison",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "commands": [
            "python -m med_features build --output <scratch>/features",
            "python -m med_models run --features <scratch>/features --output <scratch>/model --docs <scratch>/docs",
        ],
        "seconds": {"features_build": seconds[0], "models_run": seconds[1]},
        "published_files_unchanged": before == after,
        "published_files_hashed": {key: len(value) for key, value in after.items()},
        "files": files,
        "scores_on_published_validation_features": scores,
        "summary": summary,
        "machine": machine(),
    }
