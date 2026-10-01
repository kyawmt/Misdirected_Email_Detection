"""Phase 7 commands.

serve        start the Streamlit screen (the default when no command is given)
walkthrough  regenerate docs/phase_7/WALKTHROUGH.md from the running API
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from med_ui.config import DEFAULT_UI_HOST, DEFAULT_UI_PORT, DOCS_DIR, WALKTHROUGH_FILE, UiSettings

APP_PATH = Path(__file__).with_name("app.py")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="med-ui", description="Simulated draft-review UI, a client of the scoring API.")
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="start the Streamlit screen")
    serve.add_argument("--port", default=DEFAULT_UI_PORT, type=int)
    serve.add_argument("--host", default=DEFAULT_UI_HOST, help="address to listen on (default: loopback only)")
    serve.add_argument("--api", default=None, help="scoring API base URL (default: MED_UI_API_URL or http://127.0.0.1:8000)")
    walk = sub.add_parser("walkthrough", help="regenerate the walkthrough document from the running API")
    walk.add_argument("--api", default=None)
    walk.add_argument("--output", default=Path(DOCS_DIR) / WALKTHROUGH_FILE, type=Path)
    args = parser.parse_args(argv)

    if args.command in (None, "serve"):
        env = dict(os.environ)
        if getattr(args, "api", None):
            env["MED_UI_API_URL"] = args.api
        port = getattr(args, "port", DEFAULT_UI_PORT)
        host = getattr(args, "host", DEFAULT_UI_HOST)
        command = [
            sys.executable, "-m", "streamlit", "run", str(APP_PATH),
            "--server.port", str(port),
            "--server.address", host,
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--client.toolbarMode", "minimal",
        ]
        return subprocess.call(command, env=env)
    if args.command == "walkthrough":
        from med_ui.client import ApiClient
        from med_ui.walkthrough import generate

        settings = UiSettings.from_env()
        text = generate(ApiClient(args.api or settings.api_url), settings.data_dir, settings.policy_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
