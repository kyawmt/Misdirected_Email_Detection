"""Command line for building and checking the fictional dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from med_data.io import build_to, read_dataset, verify_files
from med_data.validate import assert_valid
from med_data.version import DATA_DIR, DATASET_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-data", description="Build or validate the fictional email dataset.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Generate the versioned dataset")
    build.add_argument("--output", default=DATA_DIR, type=Path)
    validate = sub.add_parser("validate", help="Check a generated dataset and its checksums")
    validate.add_argument("--data", default=DATA_DIR, type=Path)
    args = parser.parse_args(argv)
    if args.command == "build":
        path = build_to(args.output)
        print(f"Wrote {DATASET_VERSION} to {path}")
        return 0
    verify_files(args.data)
    dataset = read_dataset(args.data)
    checks = assert_valid(dataset)
    print(f"{DATASET_VERSION}: {len(checks)} checks passed")
    for subset, counts in sorted(dataset.summary["subsets"].items()):
        print(
            f"  {subset}: {counts['drafts']} drafts, "
            f"{counts['misdirected']} misdirected, {counts['legitimate']} legitimate"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
