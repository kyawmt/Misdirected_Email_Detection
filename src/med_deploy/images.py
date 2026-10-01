"""Identity and contents of the two built images.

An image id is a SHA-256 of the image configuration, so it names one exact
content: it is the immutable identity used for the known-good image in the
rollback rehearsal. For each image this records the id, the base image it was
built from, every file in `/app` (compared elsewhere with the files the process
was measured to read), the interpreter and packages inside it compared with
`constraints.txt`, whether pyarrow is importable, and probes that the frozen
bundle cannot be written from inside a container.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from med_deploy import container as dk
from med_deploy.records import now_utc
from med_deploy.version import API_DOCKERFILE, CONSTRAINTS_FILE, DEPLOY_VERSION, UI_DOCKERFILE

LIST_APP = (
    "import json, os\n"
    "files = {}\n"
    "for base, _, names in os.walk('/app'):\n"
    "    for name in names:\n"
    "        path = os.path.join(base, name)\n"
    "        files[path[len('/app/'):]] = os.path.getsize(path)\n"
    "print(json.dumps(files, sort_keys=True))\n"
)
WRITE_PROBE = (
    "import json, os, sys\n"
    "target = sys.argv[1]\n"
    "try:\n"
    "    open(target, 'ab').close()\n"
    "    outcome = 'writable'\n"
    "except OSError as error:\n"
    "    outcome = type(error).__name__ + ': ' + (error.strerror or '')\n"
    "print(json.dumps({'uid': os.getuid(), 'target': target, 'outcome': outcome}))\n"
)


def base_image(dockerfile: Path) -> str:
    match = re.search(r"^FROM\s+(\S+)", Path(dockerfile).read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError(f"{dockerfile} has no FROM line")
    return match.group(1)


def _run_python(reference: str, code: str, *arguments: str, flags: tuple[str, ...] = ()) -> dict:
    text = dk.docker("run", "--rm", *flags, "--entrypoint", "python", reference, "-c", code, *arguments).stdout
    return json.loads(text[text.index("{") :])


def describe(reference: str, dockerfile: Path, root: Path, *, writable_probe_target: str) -> dict:
    identity = dk.image_identity(reference)
    environment = dk.image_environment(reference, root / CONSTRAINTS_FILE)
    return {
        "identity": identity,
        "dockerfile": Path(dockerfile).as_posix(),
        "base_image": base_image(root / dockerfile),
        "environment": {
            "python": environment["python"],
            "python_matches_tested": environment["python_matches_tested"],
            "platform": environment["platform"],
            "packages": environment["packages"],
            "key_packages": environment["key_packages"],
            "pyarrow_importable": environment["pyarrow_importable"],
            "pandas_string_storage": environment["pandas_string_storage"],
            "installed_but_not_pinned": environment["constraints"]["installed_but_not_pinned"],
            "version_differs": environment["constraints"]["version_differs"],
            "matches_constraints": environment["matches_constraints"],
            "pinned_but_not_installed_count": len(environment["constraints"]["pinned_but_not_installed"]),
        },
        "files_in_app": _run_python(reference, LIST_APP),
        "write_probes": {
            "as_the_container_user": _run_python(reference, WRITE_PROBE, writable_probe_target),
            "root_on_a_read_only_filesystem": _run_python(reference, WRITE_PROBE, writable_probe_target, flags=("--read-only", "--user", "0")),
        },
    }


def record_images(root: Path, api_ref: str, ui_ref: str) -> dict:
    root = Path(root)
    api = describe(api_ref, API_DOCKERFILE, root, writable_probe_target="/app/artifacts/med-model-v2/model.joblib")
    ui = describe(ui_ref, UI_DOCKERFILE, root, writable_probe_target="/app/data/med-synth-v4/drafts.csv")
    return {
        "kind": "images",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "docker": dk.daemon_facts(),
        "images": {"api": api, "ui": ui},
    }
