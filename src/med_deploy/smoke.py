"""End-to-end smoke check: the review screen and the scoring API, together, over HTTP.

The real Streamlit script (`med_ui/app.py`) runs under Streamlit's headless
`AppTest` with its API URL pointed at a live service, so every call is a real
HTTP request to that service: a local process or a container. For each step the
check compares what the screen shows with what the API returns for the same
request, sent directly.

Steps: readiness and served versions, one allow and one warning, an edit that
hides the earlier decision until the edited draft is assessed again, a
malformed address (`invalid_input`), an unknown address (`unavailable`), and one
reviewer click posted to `/feedback`. The click must add exactly one line to a
disposable feedback file, change no bundle file, and leave the next assessment
unchanged. All drafts are fictional validation examples; the record holds
decisions and counts, no address, subject, or body.

Run it in a fresh interpreter (`python -m med_deploy smoke`): the last step
requires that the screen process never loaded scoring code.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from med_deploy.bundle import sha256_file
from med_deploy.records import machine, now_utc
from med_deploy.version import DEFAULT_PATHS, DEPLOY_VERSION

# Modules that score. The screen must never import them; only the API does.
SCORING_MODULES = (
    "med_policy.decision",
    "med_models.package",
    "med_models.estimators",
    "med_features.transform",
    "med_api.service",
    "med_api.app",
    "med_api.context",
)
APP_TIMEOUT_SECONDS = 120


class SmokeError(RuntimeError):
    """A step could not be carried out (as opposed to a check that failed)."""


class _Steps:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def run(self, name: str, function) -> None:
        try:
            detail = function()
        except Exception as error:  # a failed step is a result, not a crash
            self.items.append({"name": name, "passed": False, "detail": f"{type(error).__name__}: {error}"})
        else:
            self.items.append({"name": name, "passed": True, "detail": detail or "ok"})

    def skip(self, name: str, reason: str) -> None:
        self.items.append({"name": name, "passed": None, "detail": f"not verified: {reason}"})

    @property
    def ok(self) -> bool:
        return all(item["passed"] is not False for item in self.items) and any(item["passed"] for item in self.items)


def bundle_hashes(root: Path) -> dict[str, str]:
    """SHA-256 of the files that define the served bundle, as they sit on disk."""
    root = Path(root)
    files = {
        "policy.json": root / DEFAULT_PATHS["policy"],
        "model.joblib": root / DEFAULT_PATHS["model"],
        "artifact_manifest.json": root / DEFAULT_PATHS["features"] / "artifact_manifest.json",
        "dataset_manifest.json": root / DEFAULT_PATHS["data"] / "dataset_manifest.json",
    }
    return {name: sha256_file(path) for name, path in files.items() if path.is_file()}


def _feedback_lines(path: Path) -> list[str]:
    path = Path(path)
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


class _Screen:
    """The real review screen under AppTest, plus the direct API client used to check it."""

    def __init__(self, api_url: str, root: Path) -> None:
        import httpx
        from streamlit.testing.v1 import AppTest

        from med_ui import examples as ex
        from med_ui import presentation as pres
        from med_ui.cli import APP_PATH
        from med_ui.config import UiSettings

        os.environ["MED_UI_API_URL"] = api_url
        os.environ["MED_UI_ROOT"] = str(root)
        self.pres = pres
        self.settings = UiSettings.from_env()
        self.catalog = ex.load_catalog(self.settings.data_dir, self.settings.policy_dir)
        self.names = ex.display_names(self.catalog.contacts)
        self.http = httpx.Client(base_url=api_url, timeout=60.0)
        self.at = AppTest.from_file(str(APP_PATH), default_timeout=APP_TIMEOUT_SECONDS)
        self.at.run()
        if self.at.exception:
            raise SmokeError(f"the screen raised {[item.value for item in self.at.exception]}")

    # ------------------------------------------------------------- driving

    def load_and_assess(self, key: str) -> None:
        self.at.selectbox(key="example_choice").set_value(key).run()
        self.at.button(key="load_example").click().run()
        self.at.button(key="assess").click().run()
        if self.at.exception:
            raise SmokeError(f"the screen raised {[item.value for item in self.at.exception]}")

    def set_recipients(self, role: str, addresses: list[str]) -> None:
        self.at.multiselect(key=f"f_{role}").set_value(list(addresses)).run()

    def assess(self) -> None:
        self.at.button(key="assess").click().run()
        if self.at.exception:
            raise SmokeError(f"the screen raised {[item.value for item in self.at.exception]}")

    def form(self):
        at = self.at
        return self.pres.DraftForm(
            draft_timestamp=at.text_input(key="f_timestamp").value,
            sender=at.selectbox(key="f_sender").value,
            to=tuple(at.multiselect(key="f_to").value),
            cc=tuple(at.multiselect(key="f_cc").value),
            bcc=tuple(at.multiselect(key="f_bcc").value),
            subject=at.text_input(key="f_subject").value,
            body=at.text_area(key="f_body").value,
        )

    def direct(self) -> dict:
        """The API's own answer for the draft now in the form."""
        response = self.http.post("/assess", json=self.pres.build_request(self.form(), self.names))
        return {"status_code": response.status_code, "body": response.json()}

    # ------------------------------------------------------------ reading

    def texts(self) -> list[str]:
        at = self.at
        groups = (at.title, at.header, at.subheader, at.markdown, at.caption, at.success, at.info, at.warning, at.error)
        return [str(element.value) for group in groups for element in group]

    def displayed(self) -> dict:
        at = self.at
        texts = self.texts()
        decision = next(
            (match.group(1) for text in texts if (match := re.search(r"Simulated decision: (\w+)", text))),
            None,
        )
        flagged_line = next((text for text in texts if text.startswith("**Flagged recipients:**")), "")
        tables = []
        for table in at.table:
            frame = table.value
            tables.append(dict(zip(map(str, frame["Item"]), map(str, frame["Value"]), strict=True)))
        category = next((match.group(1) for text in texts if (match := re.search(r"Category: (\w+)\.", text))), None)
        return {
            "decision": decision,
            "metrics": {str(metric.label): str(metric.value) for metric in at.metric},
            "flagged": re.findall(r"`([^`]+)`", flagged_line),
            "provenance": next((table for table in tables if "History cutoff" in table), {}),
            "service": next((table for table in tables if "Contract" in table), {}),
            "category": category,
            "texts": texts,
        }


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _matches_api(screen: _Screen, view: dict, direct: dict) -> str:
    """What the screen shows must be what the API returned for the same request."""
    pres = screen.pres
    body = direct["body"]
    _expect(direct["status_code"] == 200 and body.get("status") == "assessed", f"the API did not assess the draft: HTTP {direct['status_code']}")
    provenance = body["provenance"]
    _expect(view["decision"] == body["decision"], f"the screen shows {view['decision']!r}, the API returned {body['decision']!r}")
    _expect(view["metrics"].get("Email risk score") == pres.format_score(body["email_risk_score"]), "the displayed email risk score differs from the API's")
    _expect(view["metrics"].get("T_warn (risk score cutoff)") == pres.format_score(provenance["T_warn"]), "the displayed cutoff differs from the API's")
    _expect(view["flagged"] == body["flagged_recipients"], "the displayed flagged recipients differ from the API's")
    shown = view["provenance"]
    for label, key in (("Model", "model_version"), ("Features", "feature_spec_version"), ("Policy", "policy_version"), ("Snapshot", "snapshot_id")):
        _expect(shown.get(label) == provenance[key], f"provenance {label}: the screen shows {shown.get(label)!r}, the API returned {provenance[key]!r}")
    _expect(shown.get("T_warn (risk score cutoff)") == repr(provenance["T_warn"]), "the displayed provenance cutoff differs from the API's")
    return f"decision {body['decision']}; email risk score, cutoff, flagged recipients, and versions equal the API's"


def run_smoke(
    api_url: str,
    *,
    root: Path = Path("."),
    feedback_file: Path | None = None,
    ui_url: str | None = None,
    target: str = "process",
    hash_files: bool = True,
) -> dict:
    """Run every step against a service at `api_url`. `feedback_file` is the disposable file that service writes.

    With `hash_files` False the check never opens a bundle file to hash it. The
    file audit uses that, so the files this process opens are only the ones the
    review screen itself opens.
    """
    import httpx

    root = Path(root).resolve()
    policy = json.loads((root / DEFAULT_PATHS["policy"]).read_text(encoding="utf-8"))
    steps = _Steps()
    ready_body: dict = {}
    hashes_before = bundle_hashes(root) if hash_files else None

    def api_health():
        response = httpx.get(f"{api_url}/health", timeout=10.0)
        _expect(response.status_code == 200 and response.json().get("status") == "ok", f"/health returned HTTP {response.status_code}")
        return "process is up (liveness only)"

    def api_ready():
        response = httpx.get(f"{api_url}/ready", timeout=10.0)
        _expect(response.status_code == 200, f"/ready returned HTTP {response.status_code}: {response.text[:200]}")
        body = response.json()
        ready_body.update(body)
        for key, expected in (
            ("model_version", policy["model_version"]),
            ("feature_spec_version", policy["feature_spec_version"]),
            ("policy_version", policy["policy_version"]),
            ("T_warn", policy["T_warn"]),
            ("blocking_enabled", False),
        ):
            _expect(body.get(key) == expected, f"/ready {key} is {body.get(key)!r}, the policy file says {expected!r}")
        return f"contract {body['contract_version']}, snapshot {body['snapshot_id']}, versions and cutoff equal the policy file, blocking disabled"

    steps.run("api_health", api_health)
    steps.run("api_ready", api_ready)
    if not ready_body:
        steps.skip("screen", "the API is not ready, so the screen cannot be exercised")
        return _result(steps, api_url, target, ready_body, policy, hashes_before, bundle_hashes(root) if hash_files else None, ui_url, feedback_file)

    screen: _Screen | None = None
    try:
        screen = _Screen(api_url, root)
    except Exception as error:
        steps.items.append({"name": "screen_starts", "passed": False, "detail": f"{type(error).__name__}: {error}"})
    if screen is not None:
        _screen_steps(steps, screen, ready_body, feedback_file, root, hash_files)
    if ui_url:
        _ui_endpoint(steps, ui_url)
    return _result(steps, api_url, target, ready_body, policy, hashes_before, bundle_hashes(root) if hash_files else None, ui_url, feedback_file)


def _screen_steps(steps: _Steps, screen: _Screen, ready_body: dict, feedback_file: Path | None, root: Path, hash_files: bool) -> None:
    pres = screen.pres
    seen: dict = {}

    def screen_ready():
        at = screen.at
        _expect(not [item for item in at.error if "Scoring service" in str(item.value)], "the screen shows a readiness error")
        _expect(not at.button(key="assess").disabled, "the Assess button is disabled")
        service = screen.displayed()["service"]
        for label, key in (("Contract", "contract_version"), ("Snapshot", "snapshot_id"), ("Model", "model_version"), ("Features", "feature_spec_version"), ("Policy", "policy_version")):
            _expect(service.get(label) == ready_body[key], f"service status {label}: {service.get(label)!r}, /ready says {ready_body[key]!r}")
        _expect(service.get("T_warn (risk score cutoff)") == repr(ready_body["T_warn"]), "the displayed cutoff differs from /ready")
        _expect(service.get("Blocking") == "disabled", "the screen does not report blocking as disabled")
        return "no readiness banner; Assess enabled; served versions and cutoff equal /ready"

    def allow():
        screen.load_and_assess("routine")
        view = screen.displayed()
        _expect(view["decision"] == "allow", f"expected allow, the screen shows {view['decision']!r}")
        _expect(any(pres.ALLOW_ACTION in text for text in view["texts"]), "the allow message is not shown")
        return _matches_api(screen, view, screen.direct())

    def warn():
        screen.load_and_assess("added_recipient")
        view = screen.displayed()
        direct = screen.direct()
        _expect(view["decision"] == "warn", f"expected warn, the screen shows {view['decision']!r}")
        _expect(any(pres.WARN_ACTION in text for text in view["texts"]), "the warn message is not shown")
        seen["flagged"] = direct["body"]["flagged_recipients"]
        seen["request_id"] = direct["body"]["request_id"]
        seen["recipients"] = [item["address"] for item in direct["body"]["recipients"]]
        return _matches_api(screen, view, direct)

    def edit_then_reassess():
        _expect(bool(seen.get("flagged")), "no warned draft to edit")
        screen.at.text_input(key="f_subject").input("Edited subject").run()
        stale = screen.displayed()
        _expect(any(pres.STALE_ACTION in text for text in stale["texts"]), "the edited draft did not hide the earlier result")
        _expect(stale["decision"] is None and not stale["metrics"], "a decision or score is still shown for the edited draft")
        screen.assess()
        again = screen.displayed()
        first = _matches_api(screen, again, screen.direct())
        # Remove every flagged address and assess a second edit.
        for role in ("to", "cc", "bcc"):
            kept = [item for item in screen.at.multiselect(key=f"f_{role}").value if item.strip().casefold() not in {a.casefold() for a in seen["flagged"]}]
            screen.set_recipients(role, kept)
        stale = screen.displayed()
        _expect(stale["decision"] is None and not stale["metrics"], "a decision is still shown after removing a recipient")
        screen.assess()
        second = _matches_api(screen, screen.displayed(), screen.direct())
        return f"edit hid the decision until reassessed ({first}); after removing the flagged recipient: {second}"

    def failure(label: str, category: str, form):
        screen.at.selectbox(key="example_choice").set_value("routine").run()
        screen.at.button(key="load_example").click().run()
        screen.set_recipients("to", list(form.to))
        screen.assess()
        view = screen.displayed()
        direct = screen.direct()
        _expect(direct["body"].get("status") == "unable_to_assess" and direct["body"].get("category") == category, f"the API did not return {category}")
        _expect(any(pres.UNABLE_ACTION in text for text in view["texts"]), "the unable-to-assess message is not shown")
        _expect(view["category"] == category, f"the screen shows category {view['category']!r}, expected {category}")
        _expect(view["decision"] is None and not view["metrics"], "a decision or score is shown for a failure")
        _expect(direct["body"]["decision"] is None and direct["body"]["email_risk_score"] is None, "the API returned a decision or score for a failure")
        return f"{label}: the API returned {direct['status_code']} {category} with no decision or score; the screen shows the failure and no decision"

    def invalid_input():
        from med_ui.examples import invalid_address_form

        return failure("malformed address", "invalid_input", invalid_address_form(screen.catalog))

    def unavailable():
        from med_ui.examples import unknown_address_form

        return failure("address outside the directory", "unavailable", unknown_address_form(screen.catalog))

    def feedback():
        path = Path(feedback_file)
        screen.load_and_assess("added_recipient")
        before = screen.direct()["body"]
        flagged = before["flagged_recipients"]
        _expect(bool(flagged), "no flagged recipient to give feedback on")
        index = next(i for i, item in enumerate(before["recipients"]) if item["address"] == flagged[0])
        hashes = bundle_hashes(root) if hash_files else None
        lines = _feedback_lines(path)
        screen.at.button(key=f"fb_{index}_unintended").click().run()
        added = _feedback_lines(path)[len(lines):]
        _expect(len(added) == 1, f"the click added {len(added)} lines to the feedback file, expected 1")
        record = json.loads(added[0])
        _expect(record.get("label") == "unintended" and "@" not in added[0], "the feedback line names an address or a wrong label")
        _expect(not hash_files or bundle_hashes(root) == hashes, "a bundle file changed after feedback")
        after = screen.direct()["body"]
        _expect((after["decision"], after["email_risk_score"], after["flagged_recipients"]) == (before["decision"], before["email_risk_score"], before["flagged_recipients"]), "the next assessment changed after feedback")
        _expect(any("not a label until reviewed" in text for text in screen.texts()), "the screen does not say feedback is not a label until reviewed")
        return "one click added one line (no address) to the disposable feedback file" + ("; no bundle file changed" if hash_files else "") + "; the next assessment is identical"

    def no_local_scoring():
        loaded = sorted(name for name in SCORING_MODULES if name in sys.modules)
        _expect(not loaded, f"the screen process imported scoring modules: {loaded}")
        return "the screen process never imported the scoring modules"

    steps.run("screen_ready", screen_ready)
    steps.run("screen_allow", allow)
    steps.run("screen_warn", warn)
    steps.run("screen_edit_then_reassess", edit_then_reassess)
    steps.run("screen_invalid_input", invalid_input)
    steps.run("screen_unavailable", unavailable)
    if feedback_file is None:
        steps.skip("screen_feedback", "no feedback file was given, so the write cannot be checked")
    else:
        steps.run("screen_feedback", feedback)
    steps.run("screen_no_local_scoring", no_local_scoring)


def _ui_endpoint(steps: _Steps, ui_url: str) -> None:
    import httpx

    def endpoint():
        health = httpx.get(f"{ui_url}/_stcore/health", timeout=10.0)
        _expect(health.status_code == 200 and health.text.strip() == "ok", f"the UI health endpoint returned HTTP {health.status_code}: {health.text[:80]!r}")
        page = httpx.get(ui_url, timeout=10.0)
        _expect(page.status_code == 200 and "<html" in page.text.lower(), f"the UI page returned HTTP {page.status_code}")
        return "the UI process answers its health endpoint and serves its page (the running screen is exercised by the steps above and, for the container, in a browser)"

    steps.run("ui_endpoint", endpoint)


def _result(steps, api_url, target, ready_body, policy, before, after, ui_url, feedback_file) -> dict:
    import httpx

    if before is None:
        steps.skip("bundle_files_unchanged", "file hashing was switched off for a file audit")
    else:
        steps.items.append(
            {
                "name": "bundle_files_unchanged",
                "passed": before == after,
                "detail": "policy, model, and manifest files on disk have the same SHA-256 before and after" if before == after else "a bundle file changed during the check",
            }
        )
    return {
        "kind": "smoke",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "target": target,
        "api_url": re.sub(r":\d+$", ":<port>", api_url),
        "ui_url": re.sub(r":\d+$", ":<port>", ui_url) if ui_url else None,
        "served": {key: ready_body.get(key) for key in ("contract_version", "snapshot_id", "model_version", "feature_spec_version", "policy_version", "T_warn", "blocking_enabled")},
        "feedback_checked": feedback_file is not None,
        "checks": steps.items,
        "passed": steps.ok,
        "machine": machine(),
        "httpx": httpx.__version__,
    }
