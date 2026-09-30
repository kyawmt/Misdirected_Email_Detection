"""Phase 8 commands.

build-reference  train-only input reference and the fixed operating numbers
replay           run the replay plan through the scoring API and store window aggregates
feedback         summarize API and dataset feedback and the simulated review of the replay queue
bundle-checks    hand the API mismatched and corrupted bundles and record what it does
report           regenerate docs/phase_8 from the stored records

Every command that writes a record refuses to overwrite one. Nothing here fits,
recalibrates, or changes a model, a policy, or the cutoff.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from med_monitor.version import (
    API_FEEDBACK_PATH,
    BUNDLE_CHECKS_PATH,
    DATA_DIR,
    DOCS_DIR,
    FEATURES_DIR,
    FEEDBACK_REVIEW_PATH,
    LATENCY_PATH,
    MODEL_PATH,
    PLAN_PATH,
    POLICY_DIR,
    POLICY_PATH,
    REFERENCE_PATH,
    REPLAY_PATH,
    TRAFFIC_SUBSET,
    VALIDATION_SUBSETS,
)


def _refuse_existing(*paths: Path) -> None:
    for path in paths:
        if Path(path).exists():
            raise SystemExit(f"{path} exists. A monitor record is not overwritten; use a new MONITOR_VERSION.")


def _quiet_api() -> None:
    """The API logs one line per assessment and httpx one per request; a replay makes thousands."""
    for name in ("med_api", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-monitor", description="Monitoring, reviewed feedback, and rollout evidence (simulation).")
    sub = parser.add_subparsers(dest="command", required=True)

    reference = sub.add_parser("build-reference", help="train-only input reference")
    reference.add_argument("--features", default=FEATURES_DIR, type=Path)
    reference.add_argument("--policy-dir", default=POLICY_DIR, type=Path)
    reference.add_argument("--latency", default=LATENCY_PATH, type=Path)
    reference.add_argument("--output", default=REFERENCE_PATH, type=Path)

    replay = sub.add_parser("replay", help="run the replay plan through the scoring API")
    replay.add_argument("--api", default=None, help="base URL of a running API; default runs the app in process")
    replay.add_argument("--data", default=DATA_DIR, type=Path)
    replay.add_argument("--features", default=FEATURES_DIR, type=Path)
    replay.add_argument("--policy-dir", default=POLICY_DIR, type=Path)
    replay.add_argument("--reference", default=REFERENCE_PATH, type=Path)
    replay.add_argument("--plan-output", default=PLAN_PATH, type=Path)
    replay.add_argument("--output", default=REPLAY_PATH, type=Path)

    feedback = sub.add_parser("feedback", help="summarize feedback and the simulated review queue")
    feedback.add_argument("--replay", default=REPLAY_PATH, type=Path)
    feedback.add_argument("--data", default=DATA_DIR, type=Path)
    feedback.add_argument("--feedback-file", default=API_FEEDBACK_PATH, type=Path)
    feedback.add_argument("--policy", default=POLICY_PATH, type=Path)
    feedback.add_argument("--model", default=MODEL_PATH, type=Path)
    feedback.add_argument("--output", default=FEEDBACK_REVIEW_PATH, type=Path)

    bundles = sub.add_parser("bundle-checks", help="hand the API mismatched and corrupted bundles")
    bundles.add_argument("--data", default=DATA_DIR, type=Path)
    bundles.add_argument("--plan", default=PLAN_PATH, type=Path)
    bundles.add_argument("--output", default=BUNDLE_CHECKS_PATH, type=Path)

    report = sub.add_parser("report", help="regenerate docs/phase_8 from the stored records")
    report.add_argument("--docs", default=DOCS_DIR, type=Path)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    if args.command == "build-reference":
        from med_monitor import reference as ref

        _refuse_existing(args.output)
        payload = ref.build_all(args.features, args.policy_dir, args.latency)
        ref.write_once(payload, args.output)
        print(f"Wrote {args.output}: {payload['rows']} train rows, {payload['drafts']} train emails, source {payload['source']['file']}")
        return 0

    if args.command == "replay":
        return _replay(args)

    if args.command == "feedback":
        from med_monitor import feedback as fb
        from med_monitor import reference as ref

        _refuse_existing(args.output)
        replay_record = ref.load(args.replay)
        payload = fb.summarize(replay_record, args.data, policy_path=args.policy, model_path=args.model, feedback_path=args.feedback_file)
        ref.write_once(payload, args.output)
        horizon = str(payload["efficacy"]["comparison_horizon_days"])
        current = payload["efficacy"]["by_horizon"][horizon]["current"]
        print(
            f"Wrote {args.output}: {current['queued']} queued in the current block, {current['returned']} returned within {horizon} days, "
            f"policy and model unchanged: {payload['policy_and_model_unchanged']}"
        )
        return 0

    if args.command == "bundle-checks":
        from med_api.context import ApiPaths
        from med_monitor import bundles
        from med_monitor import data as monitor_data
        from med_monitor import reference as ref

        _refuse_existing(args.output)
        _quiet_api()
        plan = ref.load(args.plan)
        first = plan["probe_draft_id"]
        request = monitor_data.load_requests(args.data, [first])[first]
        paths = ApiPaths.from_env()
        payload = bundles.run_checks(paths, request, Path(paths.policy).resolve().parents[2], progress=lambda item: print(f"{item['case']}: {item['outcome']}"))
        ref.write_once(payload, args.output)
        print(f"Wrote {args.output}: all altered bundles refused: {payload['all_altered_bundles_refused']}")
        return 0

    if args.command == "report":
        from med_monitor.report import write_documents

        for path in write_documents(args.docs):
            print(f"Wrote {path}")
        return 0
    return 1


def _replay(args) -> int:
    import pandas as pd

    from med_monitor import data as monitor_data
    from med_monitor import reference as ref
    from med_monitor import replay as rp
    from med_monitor import stream

    _refuse_existing(args.plan_output, args.output)
    _quiet_api()
    reference = ref.load(args.reference)
    subset_of, keep = monitor_data.validation_ids(args.data)
    structure = monitor_data.load_structure(args.data, keep)
    plan = stream.build_plan(structure)
    stream.check_plan(plan, subset_of)
    traffic_ids = {draft for draft, subset in subset_of.items() if subset == TRAFFIC_SUBSET}
    plan["traffic_population"] = monitor_data.sender_population(args.data, traffic_ids)
    ids = sorted(stream.plan_ids(plan))
    requests = monitor_data.load_requests(args.data, ids)
    features = pd.concat([monitor_data.read_features(args.features / f"features_{name}.csv") for name in VALIDATION_SUBSETS], ignore_index=True)
    expected = rp.expected_bundle(args.policy_dir)

    def progress(number, summary):
        latency = summary["client_latency_ms"]
        print(f"window {number}: {summary['requests']} requests, {summary['warnings']} warned, p95 {latency['p95']} ms", flush=True)

    if args.api:
        import httpx

        with httpx.Client(base_url=args.api, timeout=15.0) as client:
            result = rp.run_replay(plan, requests, features, client, expected, reference, subset_of=subset_of, progress=progress)
        result["environment"]["transport"] = f"HTTP {args.api}"
    else:
        from fastapi.testclient import TestClient

        from med_api.app import create_app
        from med_api.context import ApiPaths

        with TestClient(create_app(ApiPaths.from_env())) as client:
            result = rp.run_replay(plan, requests, features, client, expected, reference, subset_of=subset_of, progress=progress)
        result["environment"]["transport"] = "in-process test client, no network"
    ref.write_once(plan, args.plan_output)
    ref.write_once(result, args.output)
    print(f"Wrote {args.plan_output} and {args.output} in {result['elapsed_seconds']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
