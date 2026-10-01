"""Phase 9 commands.

check-bundle       verify the published bundle a process would serve (no scoring, no fit)
record-scenarios   record the scenario regression fixtures and their expected outcomes
smoke              exercise the API and the review screen together over HTTP
environment        report the interpreter and installed packages against constraints.txt
reads              record which files the API and the UI read
latency            warm latency check against a running API
rehearse           rollback rehearsal (containers or processes)
record-run         run a command and store its exit code, time, and summary counts
images             record the identity of the built images
report             regenerate docs/phase_9 from the stored records

Nothing here retrains, refits, recalibrates, or changes a model, a policy, or the
cutoff. No command opens a file that holds frozen test outcomes or scores a frozen
draft. Every measurement record refuses to overwrite an earlier one.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from med_deploy import version as V


def _add_bundle_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", choices=("api", "ui"), default="api")
    parser.add_argument("--root", default=Path("."), type=Path, help="application directory the default paths are relative to")
    parser.add_argument("--dataset-manifest", default=None, type=Path, help="dataset_manifest.json for the ui scope when it is not beside the tables")
    parser.add_argument("--digests", default=None, type=Path, help="bundle_digests.json with the anchored SHA-256 of policy.json and the stored validation files (default: the one under --root)")
    parser.add_argument("--image", action="store_true", help="the root is an image's application directory: it must hold exactly the files this scope reads")
    parser.add_argument("--record", default=None, type=Path, help="write the result as a new record file (refuses to overwrite)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="med-deploy", description="Deployment checks for the served bundle (local simulation).")
    sub = parser.add_subparsers(dest="command", required=True)

    _add_bundle_arguments(sub.add_parser("check-bundle", help="verify the published bundle a process would serve"))

    digests = sub.add_parser("record-digests", help="anchor the SHA-256 of policy.json and the stored validation files, verified against the published blobs in git")
    digests.add_argument("--root", default=Path("."), type=Path)
    digests.add_argument("--git-ref", default="main", help="the commit whose blobs the digests must equal (default: main, before Phase 9)")
    digests.add_argument("--record", default=V.DIGESTS_RECORD, type=Path)

    scenarios = sub.add_parser("record-scenarios", help="record the scenario regression fixtures once")
    scenarios.add_argument("--output", default=V.SCENARIO_RECORD, type=Path)
    scenarios.add_argument("--root", default=Path("."), type=Path)

    regress = sub.add_parser("regress", help="replay the recorded scenario fixtures against a running API")
    regress.add_argument("--api", required=True, help="API base URL")
    regress.add_argument("--record", default=V.SCENARIO_RECORD, type=Path)
    regress.add_argument("--root", default=Path("."), type=Path)

    smoke = sub.add_parser("smoke", help="exercise the API and the review screen together over HTTP")
    where = smoke.add_mutually_exclusive_group(required=True)
    where.add_argument("--api", help="URL of a running API (a local process or a container)")
    where.add_argument("--spawn", action="store_true", help="start the API as a local process with a disposable feedback file")
    smoke.add_argument("--ui", default=None, help="URL of a running review screen; its health endpoint is checked as well")
    smoke.add_argument("--feedback-file", default=None, type=Path, help="the disposable feedback file the API writes (needed to verify the feedback step)")
    smoke.add_argument("--target", default="process", choices=("process", "container"))
    smoke.add_argument("--no-file-hashes", action="store_true", help="do not open bundle files to hash them (used by the file audit)")
    smoke.add_argument("--root", default=Path("."), type=Path)
    smoke.add_argument("--record", default=None, type=Path, help="write the result as a new record file (refuses to overwrite)")

    env = sub.add_parser("environment", help="report the interpreter and installed packages against constraints.txt")
    env.add_argument("--constraints", default=None, type=Path, help="compare every installed package with this file's pins")
    env.add_argument("--check", action="store_true", help="exit 1 unless the Python is the tested one and every package matches its pin (needs --constraints)")
    env.add_argument("--freeze", action="store_true", help="print the installed third-party packages as constraints lines and exit")
    env.add_argument("--record", default=None, type=Path, help="write the result as a new record file (refuses to overwrite)")

    reads = sub.add_parser("reads", help="measure which published files the API and the review screen read")
    reads.add_argument("--root", default=Path("."), type=Path)
    reads.add_argument("--record", default=V.READS_RECORD, type=Path)

    latency = sub.add_parser("latency", help="warm latency check against a running API (a new record; the Phase 6 record is never touched)")
    latency.add_argument("--api", required=True, help="API base URL")
    what = latency.add_mutually_exclusive_group(required=True)
    what.add_argument("--container", help="name of the running API container being measured")
    what.add_argument("--python", help="the interpreter the measured API process runs under")
    latency.add_argument("--root", default=Path("."), type=Path)
    latency.add_argument("--record", required=True, type=Path)

    rehearse = sub.add_parser("rehearse", help="rollback rehearsal: a failing candidate, then the known-good bundle restored")
    rehearse.add_argument("--mode", choices=("container", "process"), required=True)
    rehearse.add_argument("--good", default=f"{V.API_IMAGE_NAME}:phase9", help="container mode: the known-good API image (tag or id)")
    rehearse.add_argument("--root", default=Path("."), type=Path)
    rehearse.add_argument("--record", required=True, type=Path)

    images = sub.add_parser("images", help="record the identity and contents of the built images")
    images.add_argument("--api", default=f"{V.API_IMAGE_NAME}:phase9")
    images.add_argument("--ui", default=f"{V.UI_IMAGE_NAME}:phase9")
    images.add_argument("--root", default=Path("."), type=Path)
    images.add_argument("--record", default=V.IMAGES_RECORD, type=Path)

    run = sub.add_parser(
        "record-run",
        help="run a command and store its exit code, time, and summary counts",
        usage="med-deploy record-run [--runs FILE] [--note TEXT] NAME -- COMMAND [ARGS ...]",
    )
    run.add_argument("--note", default=None)
    run.add_argument("--runs", default=V.RUNS_RECORD, type=Path)
    run.add_argument("name", help="the name the run is stored under, for example full_pytest")
    # Everything after NAME belongs to the command, so this option must not reuse the subcommand's `command` destination.
    run.add_argument("argv", nargs=argparse.REMAINDER, help="the command, after --")

    browser = sub.add_parser("browser-check", help="compare the saved text of a browser page with the API's response for the same example")
    browser.add_argument("--page-text", required=True, type=Path, help="a file holding the page's visible text")
    browser.add_argument("--api", required=True)
    browser.add_argument("--page-url", default="")
    browser.add_argument("--example", default="added_recipient")
    browser.add_argument("--root", default=Path("."), type=Path)
    browser.add_argument("--record", required=True, type=Path)

    clean = sub.add_parser("clean-checkout", help="run every CI step in a scratch copy of the working tree and a fresh virtual environment")
    clean.add_argument("--root", default=Path("."), type=Path)
    clean.add_argument("--record", required=True, type=Path)

    other = sub.add_parser("platform-check", help="build and serve the API image for another CPU architecture and replay the scenario fixtures")
    other.add_argument("--platform", default="linux/amd64")
    other.add_argument("--root", default=Path("."), type=Path)
    other.add_argument("--record", default=V.PLATFORM_RECORD, type=Path)

    mutation = sub.add_parser("mutation-check", help="apply one-line code mutations to a scratch copy of src/ and require the scenario suite to catch each")
    mutation.add_argument("--root", default=Path("."), type=Path)
    mutation.add_argument("--record", default=V.MUTATION_RECORD, type=Path)

    rebuild = sub.add_parser("rebuild-demo", help="rebuild features and model into a scratch directory and compare with the published files (about nine minutes)")
    rebuild.add_argument("--root", default=Path("."), type=Path)
    rebuild.add_argument("--record", default=V.REBUILD_RECORD, type=Path)

    report = sub.add_parser("report", help="regenerate docs/phase_9 from the stored records")
    report.add_argument("--root", default=Path("."), type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    handler = globals().get("_" + args.command.replace("-", "_"))
    if handler is None:
        raise SystemExit(f"No handler for {args.command}")
    return handler(args)


def _record_digests(args) -> int:
    from med_deploy.digests import record_digests
    from med_deploy.records import write_record

    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = record_digests(args.root, args.git_ref)
    for path, item in result["files"].items():
        print(f"{item['sha256']}  {path} ({item['bytes']:,} bytes)")
    print(f"each digest equals the blob at {result['verified_against']['commit'][:12]}")
    print(f"Wrote {write_record(args.record, result)}")
    return 0


def _platform_check(args) -> int:
    from med_deploy.otherarch import check_platform
    from med_deploy.records import write_record

    _quiet()
    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = check_platform(args.root, args.platform)
    regression = result["regression"]
    print(f"{args.platform} ({result['architecture']}): {regression['passed']} fixtures passed, {regression['failed']} failed {regression['failed_fixtures'] or ''}; largest score difference from the record {result['max_abs_email_risk_difference_from_the_record']:.2e}; cutoff fixture {result['cutoff_fixture']}")
    print(f"Wrote {write_record(args.record, result)}")
    return 0 if regression["failed"] == 0 else 1


def _mutation_check(args) -> int:
    from med_deploy.mutations import run_mutation_checks
    from med_deploy.records import write_record

    _quiet()
    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = run_mutation_checks(args.root)
    print(f"control (unmutated copy): {result['control']['fixtures'] - result['control']['failed']} of {result['control']['fixtures']} fixtures pass")
    for item in result["mutations"]:
        print(f"{'caught' if item['detected'] else 'MISSED'} {item['mutation']}: {item['failed']} of {item['fixtures']} fixtures failed; first: {item['first_problem']}")
    print(f"Wrote {write_record(args.record, result)}")
    return 0 if result["control_passed"] and result["all_detected"] else 1


def _rebuild_demo(args) -> int:
    from med_deploy.rebuild import rebuild_demo
    from med_deploy.records import write_record

    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = rebuild_demo(args.root)
    print(result["summary"])
    print(f"published files unchanged: {result['published_files_unchanged']}")
    print(f"Wrote {write_record(args.record, result)}")
    return 0 if result["published_files_unchanged"] else 1


def _report(args) -> int:
    from med_deploy.report import write_documents

    for path in write_documents(args.root):
        print(f"Wrote {path}")
    return 0


def _browser_check(args) -> int:
    from med_deploy.browser import verify_page_text
    from med_deploy.records import write_record

    _quiet()
    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = verify_page_text(args.page_text.read_text(encoding="utf-8"), args.api, args.root, example=args.example, page_url=args.page_url)
    print(json.dumps({"shown_in_browser": result["shown_in_browser"], "from_the_api": result["from_the_api"], "matches": result["matches"]}, indent=2))
    print(f"Wrote {write_record(args.record, result)}")
    return 0 if result["passed"] else 1


def _clean_checkout(args) -> int:
    from med_deploy.ci import clean_checkout
    from med_deploy.records import write_record

    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = clean_checkout(args.root)
    for step in result["steps"]:
        print(f"{'ok  ' if step['exit_code'] == 0 else 'FAIL'} {step['step']} ({step['seconds']} s)")
        if step["exit_code"] != 0:
            print("\n".join(step["output_tail"]))
    print(f"Wrote {write_record(args.record, result)}")
    print(f"clean checkout ({result['files_copied']} files, Python {result['venv_python']}): {'passed' if result['passed'] else 'FAILED'}")
    return 0 if result["passed"] else 1


def _rehearse(args) -> int:
    from med_deploy.records import write_record
    from med_deploy.rehearsal import rehearse

    _quiet()
    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = rehearse(args.mode, args.root, good_ref=args.good)
    for step in result["steps"]:
        print(f"{'ok  ' if step['passed'] else 'FAIL'} {step['step']} ({step['seconds']} s){'' if step['passed'] else ': ' + step['error']}")
    print(f"Wrote {write_record(args.record, result)}")
    print(f"rollback rehearsal ({args.mode}): {'passed' if result['passed'] else 'FAILED'}")
    return 0 if result["passed"] else 1


def _images(args) -> int:
    from med_deploy.images import record_images
    from med_deploy.records import write_record

    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = record_images(args.root, args.api, args.ui)
    for name, item in result["images"].items():
        print(f"{name}: {item['identity']['id']} ({item['identity']['size_bytes'] / 1e6:.0f} MB); pyarrow importable: {item['environment']['pyarrow_importable']}; matches constraints: {item['environment']['matches_constraints']}; {len(item['files_in_app'])} files in /app")
    print(f"Wrote {write_record(args.record, result)}")
    return 0


def _record_run(args) -> int:
    from med_deploy.records import record_run

    command = [item for item in args.argv if item != "--"]
    if not command:
        raise SystemExit("record-run needs a command after --")
    command = [sys.executable if item == "python" and index == 0 else item for index, item in enumerate(command)]
    run = record_run(args.name, command, args.runs, cwd=Path("."), note=args.note)
    counts = ", ".join(f"{key} {run[key]}" for key in ("passed", "failed", "errors", "skipped", "deselected", "checks_passed") if key in run)
    print(f"{args.name}: exit {run['exit_code']} in {run['seconds']} s ({counts or run['summary_line'] or 'no summary line'})")
    return run["exit_code"]


def _latency(args) -> int:
    import subprocess

    from med_api.version import DEFAULT_PATHS
    from med_deploy import container
    from med_deploy.latency import measure
    from med_deploy.records import machine, write_record

    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    root = args.root.resolve()
    if args.container:
        facts = container.container_facts(args.container)
        target = {
            "kind": "container",
            "container": facts,
            "image": container.image_identity(facts["image_id"]),
            "docker": container.daemon_facts(),
            "note": "The container runs inside the runtime's Linux VM. Its cpus and memory_limit_bytes are the limits the measurement ran under.",
        }
        environment = container.exec_json(args.container, "python", "-m", "med_deploy", "environment")
    else:
        completed = subprocess.run([args.python, "-m", "med_deploy", "environment"], capture_output=True, text=True, check=True)
        environment = json.loads(completed.stdout[completed.stdout.index("{") :])
        target = {"kind": "process", "python": args.python, "machine": machine()}
    result = measure(args.api, data_dir=root / DEFAULT_PATHS["data"], policy_dir=(root / DEFAULT_PATHS["policy"]).parent, target=target, environment=environment)
    if args.container:
        result["target"]["peak_memory_bytes_after_run"] = container.peak_memory_bytes(args.container)
    ac05 = result["ac05"]
    print(f"{ac05['requests']} measured requests after {result['workload']['warmup_calls']} warm-up: client p50 {ac05['client']['p50_ms']:.2f} ms, p95 {ac05['client']['p95_ms']:.2f} ms, p99 {ac05['client']['p99_ms']:.2f} ms; failures {ac05['failures']}; AC05 {ac05['result']}")
    print(f"pyarrow importable in the measured process: {environment['pyarrow_importable']}")
    print(f"Wrote {write_record(args.record, result)}")
    return 0 if ac05["failures"] == 0 else 1


def _environment(args) -> int:
    from med_deploy.environment import freeze_lines, snapshot

    if args.freeze:
        print("\n".join(freeze_lines()))
        return 0
    result = snapshot(args.constraints)
    print(json.dumps(result, indent=2))
    if args.record:
        from med_deploy.records import write_record  # not shipped in the images

        print(f"Wrote {write_record(args.record, result)}", file=sys.stderr)
    if args.check:
        if args.constraints is None:
            raise SystemExit("--check needs --constraints")
        good = result["python_matches_tested"] and result["matches_constraints"]
        print(f"environment check: {'passed' if good else 'FAILED'}", file=sys.stderr)
        return 0 if good else 1
    return 0


def _reads(args) -> int:
    from med_deploy.reads import measure_reads
    from med_deploy.records import write_record

    if Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    result = measure_reads(args.root)
    for name, item in result["processes"].items():
        print(f"{name}: read {len(item['read'])} files; matches bundle check: {item['matches_expected']}; written under the repository root: {item['written_under_root'] or 'nothing'}")
        for label in ("read_but_not_expected", "expected_but_not_read"):
            if item[label]:
                print(f"   {label}: {item[label]}")
    print(f"Wrote {write_record(args.record, result)}")
    return 0 if all(item["matches_expected"] and not item["written_under_root"] for item in result["processes"].values()) and result["workload"]["smoke_passed"] else 1


def _quiet() -> None:
    """The API logs a line per assessment and httpx one per request."""
    for name in ("med_api", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def _record_scenarios(args) -> int:
    from dataclasses import replace
    import tempfile

    from fastapi.testclient import TestClient

    from med_api.app import create_app
    from med_api.context import ApiPaths
    from med_deploy.scenarios import record_scenarios
    from med_policy.version import POLICY_DIR

    _quiet()
    root = args.root
    if Path(args.output).exists():
        raise SystemExit(f"{args.output} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    with tempfile.TemporaryDirectory(prefix="med-deploy-") as scratch:
        paths = replace(ApiPaths.from_env(root), feedback=Path(scratch) / "feedback.jsonl")
        with TestClient(create_app(paths)) as client:
            record = record_scenarios(client, paths.data, root / POLICY_DIR, args.output)
    known = [item["key"] for item in record["fixtures"] if item.get("known_miss")]
    print(f"Wrote {args.output}: {len(record['fixtures'])} fixtures; known misses kept in the suite: {', '.join(known)}")
    return 0


def _regress(args) -> int:
    import httpx

    from med_deploy.scenarios import load_record, replay, requests_for
    from med_api.version import DEFAULT_PATHS

    _quiet()
    record = load_record(args.record)
    requests = requests_for(record, args.root / DEFAULT_PATHS["data"])
    with httpx.Client(base_url=args.api, timeout=60.0) as client:
        outcome = replay(record, client, requests)
    for item in outcome["fixtures"]:
        print(f"{'ok  ' if item['passed'] else 'FAIL'} {item['key']}: HTTP {item['status_code']}, decision {item['decision']}")
        for problem in item["problems"]:
            print(f"       - {problem}")
    print(f"scenario regression: {outcome['passed']} passed, {outcome['failed']} failed")
    return 0 if outcome["failed"] == 0 else 1


def _smoke(args) -> int:
    import tempfile

    from med_deploy.records import write_record
    from med_deploy.serving import BundlePaths, api_process
    from med_deploy.smoke import run_smoke

    _quiet()
    root = args.root.resolve()
    if args.record and Path(args.record).exists():
        raise SystemExit(f"{args.record} exists. A deployment record is not overwritten; use a new DEPLOY_VERSION.")
    if args.spawn:
        with tempfile.TemporaryDirectory(prefix="med-deploy-smoke-") as scratch:
            feedback = Path(scratch) / V.FEEDBACK_FILE_NAME
            with api_process(BundlePaths.default(root, feedback), root) as served:
                result = run_smoke(served.url, root=root, feedback_file=feedback, ui_url=args.ui, target="process", hash_files=not args.no_file_hashes)
    else:
        result = run_smoke(args.api, root=root, feedback_file=args.feedback_file, ui_url=args.ui, target=args.target, hash_files=not args.no_file_hashes)
    for item in result["checks"]:
        mark = {True: "ok  ", False: "FAIL", None: "skip"}[item["passed"]]
        print(f"{mark} {item['name']}: {item['detail']}")
    if args.record:
        print(f"Wrote {write_record(args.record, result)}")
    print(f"smoke ({result['target']}): {'passed' if result['passed'] else 'FAILED'}")
    return 0 if result["passed"] else 1


def _check_bundle(args) -> int:
    from med_deploy.bundle import check_bundle

    result = check_bundle(args.scope, root=args.root, dataset_manifest=args.dataset_manifest, digests=args.digests, image=args.image)
    for item in result["checks"]:
        print(f"{'ok  ' if item['passed'] else 'FAIL'} {item['name']}: {item['detail']}")
    if result["bundle"]:
        shown = {key: result["bundle"][key] for key in ("dataset_version", "feature_spec_version", "model_version", "policy_version", "T_warn", "blocking_enabled") if key in result["bundle"]}
        print(json.dumps(shown))
    if args.record:
        from med_deploy.records import write_record  # not shipped in the images, which never pass --record

        print(f"Wrote {write_record(args.record, result)}")
    print(f"bundle check ({args.scope}): {'passed' if result['ok'] else 'FAILED'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
