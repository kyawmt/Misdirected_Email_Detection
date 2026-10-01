"""Start the scoring API as a local process, for smoke checks and process-level rehearsals.

The child process is the real `python -m med_api serve`, pointed at explicit
bundle paths through the same `MED_API_*` variables a deployment uses. Bundle
files are never edited: a fault is injected by pointing a process at a
disposable copy.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from med_deploy.version import DEFAULT_PATHS, LOCAL_HOST, START_TIMEOUT_SECONDS


class StartError(RuntimeError):
    """The process did not start answering in time, or exited first."""


@dataclass(frozen=True)
class BundlePaths:
    """The five bundle paths a process is pointed at. It has no scoring imports, so a checker can build one without loading scoring code."""

    policy: Path
    model: Path
    features: Path
    data: Path
    feedback: Path

    @classmethod
    def default(cls, root: Path, feedback: Path) -> "BundlePaths":
        root = Path(root)
        return cls(
            policy=root / DEFAULT_PATHS["policy"],
            model=root / DEFAULT_PATHS["model"],
            features=root / DEFAULT_PATHS["features"],
            data=root / DEFAULT_PATHS["data"],
            feedback=Path(feedback),
        )

    def replace(self, **changes) -> "BundlePaths":
        return BundlePaths(**{**self.__dict__, **changes})


@dataclass
class Served:
    url: str
    process: subprocess.Popen
    log_path: Path
    python: str

    def log_tail(self, lines: int = 20) -> list[str]:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        except OSError:
            return []


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOCAL_HOST, 0))
        return sock.getsockname()[1]


def api_environment(paths, root: Path) -> dict[str, str]:
    """The `MED_API_*` variables that point a process at these bundle paths."""
    return {
        "MED_API_ROOT": str(Path(root).resolve()),
        "MED_API_POLICY": str(Path(paths.policy).resolve()),
        "MED_API_MODEL": str(Path(paths.model).resolve()),
        "MED_API_FEATURES": str(Path(paths.features).resolve()),
        "MED_API_DATA": str(Path(paths.data).resolve()),
        "MED_API_FEEDBACK": str(Path(paths.feedback).resolve()),
    }


def wait_until_serving(url: str, process: subprocess.Popen | None = None, timeout: float = START_TIMEOUT_SECONDS) -> None:
    """Return once `GET /health` answers. The port opens only after the bundle load has finished or failed."""
    import httpx

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise StartError(f"the process exited with code {process.returncode} before it answered")
        try:
            if httpx.get(f"{url}/health", timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise StartError(f"{url} did not answer /health within {timeout:.0f} s")


@contextmanager
def api_process(paths, root: Path, *, python: str | None = None, port: int | None = None, timeout: float = START_TIMEOUT_SECONDS, extra_env: dict | None = None):
    """Run the API on a free local port and stop it on exit. Yields a `Served`."""
    port = port or free_port()
    python = python or sys.executable
    env = {**os.environ, **api_environment(paths, root), **(extra_env or {})}
    with tempfile.TemporaryDirectory(prefix="med-deploy-api-") as scratch:
        log_path = Path(scratch) / "api.log"
        with open(log_path, "w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [python, "-m", "med_api", "serve", "--host", LOCAL_HOST, "--port", str(port)],
                cwd=root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            served = Served(url=f"http://{LOCAL_HOST}:{port}", process=process, log_path=log_path, python=python)
            try:
                try:
                    wait_until_serving(served.url, process, timeout)
                except StartError as error:
                    raise StartError(f"{error}. Last log lines: {served.log_tail()}") from error
                yield served
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
