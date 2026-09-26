"""Phase 5 commands.

select         choose T_warn on validation_product_like and write the policy
evaluate-test  score the frozen test subsets once under that policy
latency        in-process preliminary timing on validation_product_like
report         regenerate docs/phase_5 from the policy artifacts
refresh-validation-scores  rewrite validation_scores.csv under the existing policy
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from med_policy.version import DATA_DIR, DOCS_DIR, FEATURES_DIR, MODEL_PATH, POLICY_DIR, POLICY_VERSION

DEFAULTS = {
    "policy_dir": POLICY_DIR,
    "model": MODEL_PATH,
    "features": FEATURES_DIR,
    "data": DATA_DIR,
    "docs": Path(DOCS_DIR),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-policy", description="Frozen warning policy for the risk scorer.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("select", "evaluate-test", "latency", "report", "refresh-validation-scores"):
        command = sub.add_parser(name)
        command.add_argument("--policy-dir", default=DEFAULTS["policy_dir"], type=Path)
        command.add_argument("--model", default=DEFAULTS["model"], type=Path)
        command.add_argument("--features", default=DEFAULTS["features"], type=Path)
        command.add_argument("--data", default=DEFAULTS["data"], type=Path)
        if name == "report":
            command.add_argument("--docs", default=DEFAULTS["docs"], type=Path)
    args = parser.parse_args(argv)

    if args.command == "select":
        from med_policy.pipeline import run_selection

        result = run_selection(args.features, args.data, args.model, args.policy_dir)
        chosen = result["policy"]["selection"]["chosen"]
        print(f"Wrote {POLICY_VERSION}: T_warn={result['policy']['T_warn']!r}")
        print(f"Validation recall {chosen['true_positives']}/{result['policy']['validation_confusion']['email']['positives']}, false interventions {chosen['false_interventions']}")
        return 0
    if args.command == "evaluate-test":
        from med_policy.pipeline import run_frozen_evaluation

        result = run_frozen_evaluation(args.policy_dir, args.model, args.features, args.data)
        for subset, block in result["subsets"].items():
            email = block["policy"]["email"]
            print(f"{subset}: warned {email['true_positives']}/{email['positives']} misdirected, {email['false_positives']}/{email['legitimate']} legitimate")
        return 0
    if args.command == "latency":
        from med_policy.latency import measure_latency
        from med_policy.pipeline import LATENCY_FILE

        result = measure_latency(args.policy_dir / "policy.json", args.model, args.features, args.data)
        (args.policy_dir / LATENCY_FILE).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"p50 {result['p50_ms']:.2f} ms, p95 {result['p95_ms']:.2f} ms over {result['measured_calls']} calls")
        return 0
    if args.command == "refresh-validation-scores":
        from med_policy.pipeline import refresh_validation_scores

        result = refresh_validation_scores(args.features, args.data, args.model, args.policy_dir)
        print(f"Rewrote validation_scores.csv: {result['rows']} rows, {result['warned']} warned")
        return 0
    if args.command == "report":
        from med_policy.report import write_documents

        written = write_documents(args.policy_dir, args.docs)
        for path in written:
            print(f"Wrote {path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
