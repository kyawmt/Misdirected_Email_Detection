"""Rollback rehearsal: a failing candidate, then the known-good bundle restored.

The rehearsal keeps two things apart: a **known-good** deployable (an image, or a
set of bundle paths) whose identity is content-addressed and never edited, and a
**candidate** that carries one injected fault. The candidate is deployed, the
checks show what the service does with it (it must fail closed), and the
known-good deployable is restored and verified again.

Two backends run the same steps:

- `container`: the API image through `docker compose`. A candidate is a thin
  image layered on the known-good image with one changed or removed file. The
  known-good image is referenced by its image id; a frozen bundle is never
  edited in place.
- `process`: `python -m med_api serve` under explicit `MED_API_*` paths. A
  candidate process is pointed at a disposable copy carrying the fault.

What each step checks
- known-good: `/health`, `/ready` (the versions and cutoff of the policy file),
  the whole scenario suite, one reviewed-label click that writes exactly one line
  to the rehearsal's own feedback file and changes no decision or bundle file.
- candidate: the process is up, `/ready` is 503 with a reason, `/assess` is
  `unable_to_assess` with no decision and no score (never an allow), the scenario
  suite flags every assessed fixture, the health command a container runs fails,
  and the review screen disables assessment and says so.
- restored: everything the known-good check verified, on an image or process
  whose identity equals the known-good identity.

This is a local rehearsal. It is not a live hot swap, a canary, or a shadow
router, and none of those exists.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

from med_deploy import container as dk
from med_deploy.bundle import sha256_file
from med_deploy.records import machine, now_utc
from med_deploy.scenarios import load_record, replay, requests_for
from med_deploy.serving import BundlePaths, StartError, api_process, free_port, wait_until_serving
from med_deploy.smoke import bundle_hashes
from med_deploy.version import (
    API_IMAGE_NAME,
    COMPOSE_FILE,
    DEFAULT_PATHS,
    DEPLOY_VERSION,
    LOCAL_HOST,
    REHEARSAL_PROJECT,
    SCENARIO_RECORD,
    UI_IMAGE_NAME,
    START_TIMEOUT_SECONDS,
)

CANDIDATES = {
    "tampered_model": {
        "fault": "one byte of model.joblib is flipped; policy.json records the model's SHA-256",
        "reason_contains": "Checksum mismatch for model.joblib",
    },
    "missing_policy": {
        "fault": "policy.json is absent",
        "reason_contains": "does not exist",
    },
}


class RehearsalError(RuntimeError):
    """The rehearsal could not be carried out (as opposed to a check that failed)."""


def require_ui_ok(health: str, where: str) -> None:
    """The review screen container must report `ok`. Anything else (unreachable, not ok) fails the step."""
    if health != "ok":
        raise RehearsalError(f"the review screen container is not healthy {where}: {health}")


def run_step(steps: list[dict], name: str, function) -> None:
    """Run one step. An exception is a failed step in the record, never a pass."""
    begin = time.perf_counter()
    try:
        detail = function()
        steps.append({"step": name, "passed": True, "seconds": round(time.perf_counter() - begin, 1), **(detail or {})})
    except Exception as error:  # a failed step is a result
        steps.append({"step": name, "passed": False, "seconds": round(time.perf_counter() - begin, 1), "error": f"{type(error).__name__}: {error}"})


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _lines(path: Path) -> list[str]:
    path = Path(path)
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _scrub(text: str) -> str:
    """Keep the stored reason stable: a scratch directory and the home directory are machine-specific."""
    text = re.sub(r"/[^\s'\"]*med-rehearsal-\w+", "<scratch>", text)
    return text.replace(str(Path.home()), "<home>")


def _policy(root: Path) -> dict:
    return json.loads((root / DEFAULT_PATHS["policy"]).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ observations


def observe_healthy(url: str, root: Path, record: dict, requests: dict, feedback_path: Path) -> dict:
    """Everything a working deployment must show. Raises AssertionError on the first thing that does not hold."""
    import httpx

    policy = _policy(root)
    hashes_before = bundle_hashes(root)
    with httpx.Client(base_url=url, timeout=60.0) as client:
        health = client.get("/health")
        _expect(health.status_code == 200, f"/health returned HTTP {health.status_code}")
        ready = client.get("/ready")
        _expect(ready.status_code == 200, f"/ready returned HTTP {ready.status_code}: {ready.text[:200]}")
        body = ready.json()
        for key, expected in (
            ("model_version", policy["model_version"]),
            ("feature_spec_version", policy["feature_spec_version"]),
            ("policy_version", policy["policy_version"]),
            ("T_warn", policy["T_warn"]),
            ("blocking_enabled", False),
        ):
            _expect(body.get(key) == expected, f"/ready {key} is {body.get(key)!r}, expected {expected!r}")
        outcome = replay(record, client, requests)
        _expect(outcome["failed"] == 0, f"{outcome['failed']} scenario fixtures failed: {[item['key'] for item in outcome['fixtures'] if not item['passed']]}")
        by_key = {item["key"]: item for item in outcome["fixtures"]}
        # Feedback isolation: one click, one line, nothing else changes.
        lines = _lines(feedback_path)
        first = client.post("/assess", json=requests["added_recipient_warn"]).json()
        _expect(first["decision"] == "warn" and bool(first["flagged_recipients"]), "the warning fixture did not warn")
        posted = client.post("/feedback", json={"request_id": first["request_id"], "recipient": first["flagged_recipients"][0], "label": "unintended"})
        _expect(posted.status_code == 200 and posted.json().get("status") == "recorded", f"/feedback returned HTTP {posted.status_code}")
        added = _lines(feedback_path)[len(lines) :]
        _expect(len(added) == 1 and "@" not in added[0], f"the click added {len(added)} lines to the rehearsal's feedback file")
        second = client.post("/assess", json=requests["added_recipient_warn"]).json()
        _expect((second["decision"], second["email_risk_score"]) == (first["decision"], first["email_risk_score"]), "the next assessment changed after feedback")
        _expect(bundle_hashes(root) == hashes_before, "a bundle file changed on disk")
    return {
        "health_http": 200,
        "ready_http": 200,
        "served": {key: body[key] for key in ("contract_version", "snapshot_id", "model_version", "feature_spec_version", "policy_version", "T_warn", "blocking_enabled")},
        "matches_policy_file": True,
        "scenario_fixtures": {"passed": outcome["passed"], "failed": outcome["failed"]},
        "allow": {"fixture": "routine_allow", "decision": by_key["routine_allow"]["decision"]},
        "warning": {"fixture": "added_recipient_warn", "decision": by_key["added_recipient_warn"]["decision"]},
        "feedback": {"lines_added_by_one_click": 1, "next_assessment_identical": True, "bundle_files_unchanged": True},
    }


def observe_failing(url: str, record: dict, requests: dict, feedback_path: Path, reason_contains: str) -> dict:
    """What a service with a broken bundle must show: up, not ready, and never an allow."""
    import httpx

    lines = _lines(feedback_path)
    with httpx.Client(base_url=url, timeout=60.0) as client:
        health = client.get("/health")
        _expect(health.status_code == 200, "/health should still answer: the process is up")
        ready = client.get("/ready")
        _expect(ready.status_code == 503 and ready.json().get("ready") is False, f"/ready returned HTTP {ready.status_code}, expected 503")
        reason = str(ready.json().get("reason", ""))
        _expect(reason_contains in reason, f"/ready reason {reason!r} does not mention {reason_contains!r}")
        probes = {}
        for key in ("routine_allow", "added_recipient_warn"):
            response = client.post("/assess", json=requests[key])
            body = response.json()
            _expect(response.status_code == 503 and body.get("status") == "unable_to_assess" and body.get("category") == "unavailable", f"{key}: expected 503 unavailable, got HTTP {response.status_code} {body.get('status')}")
            _expect(body.get("decision") is None and body.get("email_risk_score") is None and body.get("recipients") is None, f"{key}: the failure carries a decision or a score")
            _expect("allow" not in json.dumps(body) and "warn" not in json.dumps(body), f"{key}: the failure names a decision")
            _expect("provenance" not in body, f"{key}: the failure reports versions although no bundle is loaded")
            probes[key] = {"http": response.status_code, "status": body["status"], "category": body["category"], "message": body["message"], "decision": None, "email_risk_score": None}
        outcome = replay(record, client, requests)
        assessed = [item for item in record["fixtures"] if item["expected"]["status"] == "assessed"]
        flagged = [item for item in outcome["fixtures"] if not item["passed"] and item["key"] in {entry["key"] for entry in assessed}]
        _expect(len(flagged) == len(assessed), f"the scenario suite flagged {len(flagged)} of {len(assessed)} assessed fixtures")
        stray = client.post("/feedback", json={"request_id": "req_unknown", "recipient": "nobody@demo.example", "label": "unintended"})
        _expect(stray.status_code == 422, f"/feedback returned HTTP {stray.status_code}")
        _expect(_lines(feedback_path) == lines, "the failing candidate wrote to the feedback file")
    return {
        "health_http": 200,
        "ready_http": 503,
        "ready_reason": _scrub(reason),
        "assess": probes,
        "scenario_suite": {"assessed_fixtures": len(assessed), "flagged_by_the_suite": len(flagged)},
        "feedback_file_unchanged": True,
    }


def observe_screen(url: str, root: Path) -> dict:
    """The review screen against this service: it must say the service is not ready and must not offer assessment."""
    from med_deploy.smoke import _Screen

    screen = _Screen(url, root)
    texts = screen.texts()
    disabled = bool(screen.at.button(key="assess").disabled)
    banner = [str(item.value) for item in screen.at.error if "Scoring service" in str(item.value)]
    return {
        "checked_by": "the screen script, run headlessly (AppTest) on the host against this API",
        "assessment_disabled": disabled,
        "banner": banner[:1],
        "no_decision_shown": not any("Simulated decision" in text for text in texts),
    }


# ---------------------------------------------------------------------- backends


class _ContainerBackend:
    name = "container"

    def __init__(self, root: Path, good_ref: str, scratch: Path):
        self.root, self.good_ref, self.scratch = root, good_ref, scratch
        self.api_port, self.ui_port = free_port(), free_port()
        self.feedback_dir = scratch / "feedback"
        self.feedback_dir.mkdir()
        self.feedback_dir.chmod(0o777)  # the container's unprivileged user writes here
        self.images: dict[str, str] = {}
        self.known_good = dk.image_identity(good_ref)

    @property
    def feedback_path(self) -> Path:
        return self.feedback_dir / "feedback.jsonl"

    @property
    def url(self) -> str:
        return f"http://{LOCAL_HOST}:{self.api_port}"

    def _compose(self, *arguments: str, image: str) -> None:
        environment = {**os.environ, "MED_API_IMAGE": image, "MED_API_PORT": str(self.api_port), "MED_UI_PORT": str(self.ui_port), "MED_FEEDBACK_DIR": str(self.feedback_dir), "MED_UI_IMAGE": f"{UI_IMAGE_NAME}:phase9"}
        completed = subprocess.run(["docker", "compose", "-p", REHEARSAL_PROJECT, "-f", str(self.root / COMPOSE_FILE), *arguments], cwd=self.root, env=environment, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RehearsalError(f"docker compose {' '.join(arguments)} failed: {(completed.stderr or completed.stdout).strip()[-400:]}")

    def build_candidates(self) -> dict:
        """Thin images on top of the known-good image: one changed or removed file each."""
        built = {}
        tag_base = f"{API_IMAGE_NAME}:rehearsal-candidate"
        # BuildKit resolves FROM as a reference, not an image id, so layer on a tag of the same id.
        parent_tag = f"{API_IMAGE_NAME}:rehearsal-known-good"
        dk.docker("tag", self.known_good["id"], parent_tag)
        _expect(dk.image_identity(parent_tag)["id"] == self.known_good["id"], "the layering tag does not name the known-good image")
        for name in CANDIDATES:
            context = self.scratch / f"candidate-{name}"
            context.mkdir()
            lines = [f"FROM {parent_tag}", "USER root"]
            if name == "tampered_model":
                data = bytearray((self.root / DEFAULT_PATHS["model"]).read_bytes())
                data[-1] ^= 0x01
                (context / "model.joblib").write_bytes(bytes(data))
                lines.append("COPY model.joblib /app/artifacts/med-model-v2/model.joblib")
            elif name == "missing_policy":
                lines.append("RUN rm /app/artifacts/med-policy-v2/policy.json")
            lines.append("USER 10001")
            (context / "Dockerfile").write_text("\n".join(lines) + "\n", encoding="utf-8")
            tag = f"{tag_base}-{name.replace('_', '-')}"
            dk.docker("build", "-t", tag, str(context))
            identity = dk.image_identity(tag)
            self.images[name] = identity["id"]
            built[name] = {"tag": tag, "id": identity["id"], "construction": "layered on the known-good image (same id), then " + CANDIDATES[name]["fault"]}
        return built

    def start(self, variant: str) -> dict:
        image = self.known_good["id"] if variant == "known_good" else self.images[variant]
        started = time.perf_counter()
        self._compose("up", "-d", "--no-build", "--force-recreate", "--no-deps", "api", image=image)
        wait_until_serving(self.url, None, START_TIMEOUT_SECONDS)
        seconds = time.perf_counter() - started
        facts = dk.container_facts(f"{REHEARSAL_PROJECT}-api-1")
        return {"image_id": facts["image_id"], "seconds_until_the_port_answered": round(seconds, 1)}

    def wait_ready(self, timeout: float = START_TIMEOUT_SECONDS) -> None:
        import httpx

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.url}/ready", timeout=5.0).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RehearsalError("the known-good deployable did not become ready")

    def healthcheck_exit_code(self) -> int:
        completed = dk.docker("exec", f"{REHEARSAL_PROJECT}-api-1", "python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/ready', timeout=4)", check=False)
        return completed.returncode

    has_ui_container = True

    def start_ui(self, timeout: float = 90) -> str:
        """Start the review screen container and require it to be healthy. It runs beside whatever API state the rehearsal is in."""
        self._compose("up", "-d", "--no-build", "--no-deps", "ui", image=self.known_good["id"])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ui_health() == "ok":
                break
            time.sleep(0.5)
        health = self.ui_health()
        require_ui_ok(health, "after it was started")
        return health

    def ui_sees_api_ready(self) -> int:
        """The HTTP status of GET http://api:8000/ready as the review screen container sees it, from inside its own network.

        A healthy API gives 200 and a service with no loaded bundle gives 503. A container that cannot reach the API at
        all makes the command fail, which fails the step.
        """
        code = (
            "import urllib.request as u, urllib.error as e\n"
            "try:\n"
            "    print(u.urlopen('http://api:8000/ready', timeout=5).status)\n"
            "except e.HTTPError as error:\n"
            "    print(error.code)\n"
        )
        return int(dk.docker("exec", f"{REHEARSAL_PROJECT}-ui-1", "python", "-c", code).stdout.strip())

    def ui_health(self) -> str:
        import httpx

        try:
            return httpx.get(f"http://{LOCAL_HOST}:{self.ui_port}/_stcore/health", timeout=5.0).text.strip()
        except httpx.HTTPError as error:
            return f"unreachable: {type(error).__name__}"

    def stop(self) -> None:
        self._compose("down", "--remove-orphans", image=self.known_good["id"])
        for tag in [f"{API_IMAGE_NAME}:rehearsal-candidate-{name.replace('_', '-')}" for name in CANDIDATES] + [f"{API_IMAGE_NAME}:rehearsal-known-good"]:
            dk.docker("rmi", tag, check=False)

    def identity(self) -> dict:
        """Read the image again each time: the tag must still name the same content-addressed id."""
        now = dk.image_identity(self.good_ref)
        return {"kind": "image", "reference": self.good_ref, "id": now["id"], "size_bytes": now["size_bytes"], "architecture": now["architecture"]}


class _ProcessBackend:
    name = "process"

    def __init__(self, root: Path, scratch: Path):
        self.root, self.scratch = root, scratch
        self.feedback_path = scratch / "feedback.jsonl"
        self.stack = ExitStack()
        self.url = ""
        self.candidate_paths: dict[str, BundlePaths] = {}
        self.good_paths = BundlePaths.default(root, self.feedback_path)

    def identity(self) -> dict:
        paths = self.good_paths
        return {
            "kind": "bundle paths",
            "files": {"policy.json": sha256_file(paths.policy), "model.joblib": sha256_file(paths.model), "artifact_manifest.json": sha256_file(paths.features / "artifact_manifest.json")},
        }

    def build_candidates(self) -> dict:
        """Disposable copies carrying one fault each. The published files are never edited."""
        built = {}
        model_copy = self.scratch / "candidate-tampered-model" / "model.joblib"
        model_copy.parent.mkdir()
        data = bytearray(self.good_paths.model.read_bytes())
        data[-1] ^= 0x01
        model_copy.write_bytes(bytes(data))
        self.candidate_paths["tampered_model"] = self.good_paths.replace(model=model_copy)
        self.candidate_paths["missing_policy"] = self.good_paths.replace(policy=self.scratch / "candidate-missing-policy" / "policy.json")
        for name in CANDIDATES:
            built[name] = {"construction": CANDIDATES[name]["fault"] + " (a disposable copy; the published file is untouched)"}
        return built

    def start(self, variant: str) -> dict:
        self.stop()
        paths = self.good_paths if variant == "known_good" else self.candidate_paths[variant]
        started = time.perf_counter()
        served = self.stack.enter_context(api_process(paths, self.root))
        self.url = served.url
        return {"seconds_until_the_port_answered": round(time.perf_counter() - started, 1), "pid": served.process.pid}

    def wait_ready(self, timeout: float = START_TIMEOUT_SECONDS) -> None:
        return None  # the port opens only after the bundle loaded or failed

    def healthcheck_exit_code(self) -> int:
        import httpx

        try:
            return 0 if httpx.get(f"{self.url}/ready", timeout=5.0).status_code == 200 else 1
        except httpx.HTTPError:
            return 1

    has_ui_container = False

    def start_ui(self, timeout: float = 90) -> str:
        return "not applicable: there is no review screen container in the process-level rehearsal"

    def ui_sees_api_ready(self) -> None:
        return None

    def ui_health(self) -> str:
        return "not applicable"

    def stop(self) -> None:
        self.stack.close()
        self.stack = ExitStack()


# ----------------------------------------------------------------------- driver


def rehearse(mode: str, root: Path, *, good_ref: str = f"{API_IMAGE_NAME}:phase9", record_path: Path = SCENARIO_RECORD) -> dict:
    root = Path(root).resolve()
    record = load_record(root / record_path)
    requests = requests_for(record, root / DEFAULT_PATHS["data"])
    steps: list[dict] = []
    started_at = now_utc()

    def step(name: str, function):
        run_step(steps, name, function)

    with tempfile.TemporaryDirectory(prefix="med-rehearsal-") as raw:
        scratch = Path(raw)
        if mode == "container":
            ok, reason = dk.available()
            if not ok:
                raise RehearsalError(f"The container runtime is not available: {reason}")
            backend = _ContainerBackend(root, good_ref, scratch)
        elif mode == "process":
            backend = _ProcessBackend(root, scratch)
        else:
            raise RehearsalError(f"Unknown mode {mode!r}")
        bundle_before = bundle_hashes(root)
        identities: dict = {"known_good": backend.identity()}
        try:
            identities["candidates"] = backend.build_candidates()

            ui_started = {"yes": False}

            def known_good(label: str):
                def run():
                    info = backend.start("known_good")
                    backend.wait_ready()
                    result = observe_healthy(backend.url, root, record, requests, backend.feedback_path)
                    if mode == "container":
                        _expect(info["image_id"] == backend.known_good["id"], "the running container is not the known-good image")
                    extra = {}
                    if ui_started["yes"]:
                        require_ui_ok(backend.ui_health(), f"after {label}")
                        seen = backend.ui_sees_api_ready()
                        _expect(seen == 200, f"the review screen container sees /ready {seen}, expected 200")
                        extra = {"ui_health": "ok", "ui_container_sees_ready_http": seen}
                    return {"deployable": "known_good", **info, **result, **extra}

                step(label, run)

            def start_screen():
                health = backend.start_ui()
                seen = backend.ui_sees_api_ready()
                if backend.has_ui_container:
                    ui_started["yes"] = True
                    _expect(seen == 200, f"the review screen container sees /ready {seen}, expected 200")
                return {"ui_health": health, "ui_container_sees_ready_http": seen}

            known_good("baseline: known-good deployed and verified")
            step("start the review screen container and check its view of the API" if mode == "container" else "review screen container: not part of the process-level rehearsal", start_screen)
            for name, spec in CANDIDATES.items():

                def fail(name=name, spec=spec):
                    info = backend.start(name)
                    result = observe_failing(backend.url, record, requests, backend.feedback_path, spec["reason_contains"])
                    health_exit = backend.healthcheck_exit_code()
                    _expect(health_exit != 0, "the health command still passes on the failing candidate")
                    screen = observe_screen(backend.url, root)
                    _expect(screen["assessment_disabled"] and screen["no_decision_shown"], f"the review screen does not stop assessment: {screen}")
                    extra = {}
                    if backend.has_ui_container:
                        require_ui_ok(backend.ui_health(), f"while {name} is deployed")
                        seen = backend.ui_sees_api_ready()
                        _expect(seen == 503, f"the review screen container sees /ready {seen}, expected 503")
                        extra = {"ui_process_health": "ok", "ui_container_sees_ready_http": seen}
                    return {"deployable": name, "fault": spec["fault"], **info, **result, "health_command_exit_code": health_exit, "review_screen": screen, **extra}

                step(f"candidate fails closed: {name}", fail)
                known_good(f"restore: known-good redeployed after {name}")

            def screen_stayed_up():
                if not backend.has_ui_container:
                    return {"ui_health": "not applicable"}
                require_ui_ok(backend.ui_health(), "at the end of the rehearsal")
                return {"ui_health": "ok"}

            step("review screen container stayed up" if mode == "container" else "review screen container: not applicable", screen_stayed_up)
            identities["known_good_after"] = backend.identity()
            identities["known_good_unchanged"] = identities["known_good"] == identities["known_good_after"]
        finally:
            backend.stop()
        bundle_after = bundle_hashes(root)
        feedback_lines = len(_lines(backend.feedback_path)) if backend.feedback_path.exists() else 0
    passed = all(item["passed"] for item in steps) and bundle_before == bundle_after and identities.get("known_good_unchanged", False)
    return {
        "kind": "rollback_rehearsal",
        "deploy_version": DEPLOY_VERSION,
        "mode": mode,
        "date_utc": started_at,
        "passed": passed,
        "trigger": "GET /ready returned 503 and the scenario suite flagged every assessed fixture (docs/phase_8/RUNBOOK.md: roll back when /ready no longer reports the expected versions)",
        "identities": identities,
        "steps": steps,
        "published_bundle_files_unchanged": bundle_before == bundle_after,
        "feedback_lines_in_the_rehearsal_file": feedback_lines,
        "limits": [
            "A local rehearsal on one machine. It is not a live hot swap, a canary, or a shadow router; none exists.",
            "A candidate is the known-good bundle with one injected fault. It shows that a broken bundle fails closed and that the known-good deployable can be restored; it does not show that a different, healthy model can be promoted.",
            "The previous bundle (med-policy-v1) cannot be swapped in: the current code refuses it by design.",
            "In the failed-candidate state the review screen's behavior was observed with the screen script run headlessly on the host against the failing API. The review screen container was observed through its health endpoint and its own view of /ready from inside its network; its served page was not opened in a browser in that state (a browser check covers one healthy page).",
        ],
        "machine": machine(),
        "docker": dk.daemon_facts() if mode == "container" else None,
    }
