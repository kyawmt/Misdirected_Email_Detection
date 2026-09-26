"""In-process scoring latency, a preliminary for AC05.

The timed call is `assess_draft`: the shared feature transform on the loaded
history index, the loaded model, and the policy decision. Request parsing,
HTTP, and query construction are outside the timing boundary because no
backend exists yet. Assumption A10 starts timing at backend receipt, so these
numbers are not the product latency result.
"""

from __future__ import annotations

import os
import platform
import time
from pathlib import Path

import numpy as np

from med_data.io import read_dataset
from med_features.profiles import directory_from_dataset, history_index_from_dataset
from med_features.text_model import FittedText
from med_features.transform import query_from_dataset
from med_policy.decision import assess_draft, load_bundle
from med_policy.version import SELECTION_SUBSET

WARMUP_CALLS = 20
MIN_MEASURED = 1000


def measure_latency(policy_path: Path, model_path: Path, features_dir: Path, data_dir: Path) -> dict:
    started = time.perf_counter()
    dataset = read_dataset(data_dir)
    transformer = FittedText.load(Path(features_dir) / "text_transformer.joblib")
    bundle = load_bundle(policy_path, model_path, Path(features_dir) / "artifact_manifest.json")
    directory = directory_from_dataset(dataset)
    index = history_index_from_dataset(dataset)
    index.bind(transformer)
    cold_start = time.perf_counter() - started

    drafts = dataset.drafts.loc[dataset.drafts["subset"] == SELECTION_SUBSET]
    drafts = drafts.sort_values(["sent_at", "draft_id"], kind="mergesort")
    queries = [query_from_dataset(dataset, draft_id) for draft_id in drafts["draft_id"].tolist()]
    if len(queries) < MIN_MEASURED:
        raise ValueError(f"Need {MIN_MEASURED} drafts, found {len(queries)}")

    for query in queries[:WARMUP_CALLS]:
        assess_draft(bundle, directory, index, transformer, query)
    timings = []
    statuses = {}
    for query in queries:
        begin = time.perf_counter()
        result = assess_draft(bundle, directory, index, transformer, query)
        timings.append((time.perf_counter() - begin) * 1000)
        statuses[result["status"]] = statuses.get(result["status"], 0) + 1
    values = np.asarray(timings)
    recipients = np.asarray([len(query.recipients) for query in queries])
    characters = np.asarray([len(query.subject) + len(query.body) for query in queries])
    return {
        "timing_boundary": "assess_draft: transform_draft on the loaded history index, loaded model, policy decision",
        "excluded": "request parsing, HTTP, query construction, dataset loading",
        "subset": SELECTION_SUBSET,
        "warmup_calls": WARMUP_CALLS,
        "measured_calls": int(len(values)),
        "concurrency": 1,
        "statuses": statuses,
        "p50_ms": float(np.percentile(values, 50)),
        "p95_ms": float(np.percentile(values, 95)),
        "max_ms": float(values.max()),
        "cold_start_seconds": float(cold_start),
        "cold_start_includes": "read dataset, load transformer, load policy and model with checksum checks, build directory and history index, vectorize history",
        "request_mix": {
            "recipients_per_draft": {str(int(k)): int(v) for k, v in zip(*np.unique(recipients, return_counts=True), strict=True)},
            "characters_p50": float(np.percentile(characters, 50)),
            "characters_max": int(characters.max()),
        },
        "versions": {
            **bundle.versions,
            "dataset_version": bundle.policy["dataset_version"],
            "numpy": np.__version__,
            "scikit_learn": _sklearn_version(),
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
        },
    }


def _sklearn_version() -> str:
    import sklearn

    return sklearn.__version__
