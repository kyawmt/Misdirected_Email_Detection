"""Check what a real browser showed against the API.

Streamlit talks to the browser over a websocket, so the UI container cannot be
driven by a plain HTTP client. The smoke check runs the real script headlessly
(AppTest) against the API; for the container, a person (or an agent with a
browser) opens the page and saves its visible text. This module parses that text
and compares it with the API's own response for the same example draft. The text
itself is not stored, only what was parsed and what the API returned.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from med_deploy.records import now_utc
from med_deploy.version import DEPLOY_VERSION

CODE = re.compile(r"(?:Context|Reason|Evidence limitation) ([A-Z]+(?:_[A-Z]+)+):")


def _value_after(lines: list[str], label: str) -> str | None:
    for index, line in enumerate(lines):
        if line.strip() == label:
            for item in lines[index + 1 :]:
                if item.strip():
                    return item.strip()
    return None


def parse_page_text(text: str) -> dict:
    lines = text.splitlines()
    decision = re.search(r"Simulated decision: (\w+)", text)
    flagged = re.search(r"Flagged recipients: (.+)", text)
    return {
        "decision": decision.group(1) if decision else None,
        "email_risk_score": _value_after(lines, "Email risk score"),
        "t_warn": _value_after(lines, "T_warn (risk score cutoff)"),
        "flagged": [item.strip() for item in flagged.group(1).split(",")] if flagged else [],
        "codes": sorted(set(CODE.findall(text))),
        "action_message": next((line.strip() for line in lines if line.strip() in ("Pause and review before sending.", "No warning from this policy.")), None),
    }


def verify_page_text(text: str, api_url: str, root: Path, *, example: str = "added_recipient", page_url: str = "") -> dict:
    """Compare the parsed page with the API's response for the example's own request."""
    import httpx

    from med_ui import examples as ex
    from med_ui import presentation as pres
    from med_ui.config import UiSettings

    shown = parse_page_text(text)
    os.environ["MED_UI_ROOT"] = str(Path(root).resolve())
    settings = UiSettings.from_env()
    catalog = ex.load_catalog(settings.data_dir, settings.policy_dir)
    names = ex.display_names(catalog.contacts)
    request = pres.build_request(catalog.examples[example].form, names)
    body = httpx.post(f"{api_url}/assess", json=request, timeout=60.0).json()
    if body.get("status") != "assessed":
        raise ValueError(f"the API did not assess the example: {body.get('category')}")
    # The cards show every recipient's codes and limitations.
    flagged_codes = sorted({item["code"] for recipient in body["recipients"] for item in recipient["reason_codes"] + recipient["evidence_limitations"]})
    api = {
        "decision": body["decision"],
        "email_risk_score": pres.format_score(body["email_risk_score"]),
        "t_warn": pres.format_score(body["provenance"]["T_warn"]),
        "flagged": body["flagged_recipients"],
        "codes": flagged_codes,
    }
    checks = {name: shown[name] == api[name] for name in api}
    return {
        "kind": "browser_check",
        "deploy_version": DEPLOY_VERSION,
        "date_utc": now_utc(),
        "how": "manual: the page was opened in a browser and its visible text saved; this command parsed it and compared it with the API's response for the same example",
        "example": example,
        "page": page_url,
        "shown_in_browser": {key: shown[key] for key in ("decision", "email_risk_score", "t_warn", "codes", "action_message")} | {"flagged_count": len(shown["flagged"])},
        "from_the_api": {key: api[key] for key in ("decision", "email_risk_score", "t_warn", "codes")} | {"flagged_count": len(api["flagged"])},
        "matches": checks,
        "passed": all(checks.values()) and shown["action_message"] is not None,
    }
