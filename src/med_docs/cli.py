"""Phase 10 commands.

report   regenerate docs/RESULTS.md and the generated blocks of the other Phase 10 documents from stored records
check    exit 1 if any generated file differs from what the records produce

Both read stored records only. Neither scores a draft, fits a model, opens a data
table, or reads a per-draft outcome of the frozen test record.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from med_docs.documents import build, differing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-docs", description="Documents generated from stored records (simulation).")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("report", "regenerate the generated documents and blocks"), ("check", "fail if a generated file is out of date")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--root", default=Path("."), type=Path, help="repository root (default: the working directory)")
    args = parser.parse_args(argv)

    if args.command == "report":
        for path, text in build(args.root).items():
            target = args.root / path
            if target.is_file() and target.read_text(encoding="utf-8") == text:
                print(f"Unchanged {path}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            print(f"Wrote {path}")
        return 0

    stale = differing(args.root)
    for path in stale:
        print(f"Out of date: {path}")
    if stale:
        print("Run `python -m med_docs report`.")
        return 1
    print("Generated documents match the stored records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
