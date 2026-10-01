"""Run a module and record which files it opens under the repository root.

    python -m med_deploy.audited OUTPUT.json ROOT -- MODULE [ARGS...]

A Python audit hook logs every `open` event. On exit the paths under
`ROOT/data` and `ROOT/artifacts`, and every file opened for writing, are
written to OUTPUT.json. This is how the file lists of the two images are
measured instead of guessed: the process is started exactly as it is served,
driven with real requests, and stopped.

The wrapped module is not changed and does not know it is being audited.
"""

from __future__ import annotations

import atexit
import json
import os
import runpy
import signal
import sys
from pathlib import Path

WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
IGNORED_PARTS = ("__pycache__", ".venv", "site-packages")


def main(argv: list[str]) -> int:
    if len(argv) < 4 or "--" not in argv:
        print(__doc__)
        return 2
    output, root = Path(argv[0]), Path(argv[1]).resolve()
    split = argv.index("--")
    module, arguments = argv[split + 1], argv[split + 2 :]
    read: set[str] = set()
    written: set[str] = set()

    def hook(event: str, args: tuple) -> None:
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        mode, flags = args[1], args[2]
        try:
            path = Path(os.fsdecode(args[0]))
            path = path if path.is_absolute() else Path.cwd() / path
            path = Path(os.path.normpath(path))
        except (TypeError, ValueError):
            return
        if any(part in IGNORED_PARTS for part in path.parts):
            return
        writing = (isinstance(mode, str) and any(letter in mode for letter in "wax+")) or (isinstance(flags, int) and flags & WRITE_FLAGS)
        if writing:
            written.add(str(path))
        else:
            read.add(str(path))

    def relative(path: str) -> str:
        try:
            return Path(path).relative_to(root).as_posix()
        except ValueError:
            return path

    def save() -> None:
        kept = sorted(relative(item) for item in read if Path(item).is_file() and relative(item).startswith(("data/", "artifacts/")))
        inside = sorted(relative(item) for item in written if relative(item) != item)
        outside = sum(1 for item in written if relative(item) == item)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"read": kept, "written_under_root": inside, "files_written_outside_root": outside}
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def on_terminate(signum, frame) -> None:
        # uvicorn restores this handler and re-raises SIGTERM after a graceful
        # shutdown, which would end the process before atexit runs.
        save()
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    sys.addaudithook(hook)
    atexit.register(save)
    signal.signal(signal.SIGTERM, on_terminate)
    sys.argv = [module, *arguments]
    sys.path.insert(0, str(Path.cwd()))
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except SystemExit as error:
        return int(error.code or 0) if not isinstance(error.code, str) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
