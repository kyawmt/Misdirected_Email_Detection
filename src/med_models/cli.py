"""Rerun the recorded experiments and rebuild the model artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from med_models.experiments import run_experiments
from med_models.package import artifact_metadata, save_model
from med_models.report import write_documents
from med_models.version import ARTIFACT_DIR, DATA_DIR, DOCS_DIR, FEATURES_DIR, MODEL_VERSION, SEED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-models", description="Train the recorded misdirection baselines.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help=f"Refit every recorded configuration and write {MODEL_VERSION}")
    run.add_argument("--features", default=FEATURES_DIR, type=Path)
    run.add_argument("--data", default=DATA_DIR, type=Path)
    run.add_argument("--output", default=ARTIFACT_DIR, type=Path)
    run.add_argument("--docs", default=DOCS_DIR, type=Path)
    args = parser.parse_args(argv)
    if args.command != "run":
        return 1
    result = run_experiments(args.features, args.data)
    fitted = result.pop("fitted")
    selected_name = result["selected"]
    selected = next(run for run in result["runs"] if run["name"] == selected_name)
    selected["seed"] = SEED
    metadata = artifact_metadata(args.features, args.data, selected, result["folds"])
    metadata["seed"] = SEED
    args.output.mkdir(parents=True, exist_ok=True)
    save_model(args.output / "model.joblib", fitted[selected_name], metadata)
    payload = _ready(result)
    (args.output / "experiments.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (args.output / "model_metadata.json").write_text(json.dumps(_ready(metadata), indent=2) + "\n", encoding="utf-8")
    write_documents(args.docs, payload, metadata)
    print(f"Wrote {MODEL_VERSION} to {args.output}")
    print(f"Selected {selected_name}")
    return 0


def _ready(value):
    from med_models.experiments import _json_ready

    return _json_ready(value)


if __name__ == "__main__":
    raise SystemExit(main())
