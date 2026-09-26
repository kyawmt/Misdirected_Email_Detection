"""Command line for fitting features on the fictional dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from med_features.build import build_artifacts
from med_features.version import FEATURE_SPEC_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-features", description="Build behavioral and text features.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Fit the text transformer and write train/validation features")
    build.add_argument("--data", default="data/med-synth-v2", type=Path)
    build.add_argument("--output", default=f"artifacts/{FEATURE_SPEC_VERSION}", type=Path)
    build.add_argument(
        "--quality-markdown",
        default=None,
        type=Path,
        help="Optional path for the human-readable quality report",
    )
    args = parser.parse_args(argv)
    if args.command == "build":
        path = build_artifacts(args.data, args.output, quality_markdown=args.quality_markdown)
        print(f"Wrote {FEATURE_SPEC_VERSION} to {path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
