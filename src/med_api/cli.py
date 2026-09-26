"""Phase 6 commands.

serve    start the API with uvicorn
latency  measure AC05 on the API boundary, once per served policy bundle,
         and write artifacts/med-api-latency/<policy version>/latency.json
report   regenerate docs/phase_6
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from med_api.context import ApiPaths
from med_api.version import DOCS_DIR, LATENCY_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-api", description="Simulated misdirected-recipient scoring API.")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8000, type=int)
    latency = sub.add_parser("latency")
    latency.add_argument("--output", default=LATENCY_PATH, type=Path)
    report = sub.add_parser("report")
    report.add_argument("--docs", default=Path(DOCS_DIR), type=Path)
    report.add_argument("--latency", default=LATENCY_PATH, type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "serve":
        import uvicorn

        from med_api.app import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
        return 0
    if args.command == "latency":
        from med_api.latency import measure, write_once

        logging.getLogger("med_api").setLevel(logging.WARNING)
        result = measure(ApiPaths.from_env(), args.output)
        write_once(result, args.output)
        print(
            f"{result['measured_calls']} calls: client p50 {result['client_p50_ms']:.2f} ms, "
            f"p95 {result['client_p95_ms']:.2f} ms; AC05 {result['ac05']}; wrote {args.output}"
        )
        return 0
    if args.command == "report":
        from med_api.report import write_documents

        logging.getLogger("med_api").setLevel(logging.WARNING)
        for path in write_documents(ApiPaths.from_env(), args.docs, args.latency):
            print(f"Wrote {path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
