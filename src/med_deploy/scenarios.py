"""Compact scenario regression suite for the frozen policy.

Fixtures are fictional `validation_product_like` drafts chosen by rule from the
policy's stored validation decisions (`validation_scores.csv`), never by draft
id and never from a frozen test subset. Each fixture records where it came from,
the outcome the product wants (a misdirected email should warn, a legitimate one
should allow), and the outcome the frozen bundle produces. Where the two differ
the fixture is a **known miss** and stays in the suite: the suite asserts what
the bundle does today, so an improvement or a regression both fail it and force
a reviewed update.

The record holds draft ids, scores, and codes. It holds no address, subject, or
body: requests are rebuilt from the published validation tables by draft id.

`compare` is the detector. It flags a changed decision, score, provenance,
recipient list, code, or evidence limitation, and any failure that carries a
decision or a score (an `unable_to_assess` that became an allow).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from med_deploy.records import now_utc, write_record
from med_deploy.version import DEPLOY_VERSION, MODE, SELECTION_SUBSET, SNAPSHOT_ID, WORKLOAD_SUBSET

# A different machine may sum in a different order. Decisions never get a tolerance.
SCORE_TOLERANCE = 1e-9
# The stored validation scores and the API agree to this bound (docs/phase_5/THRESHOLD_POLICY.md).
STORED_PARITY_BOUND = 1e-12
PICKS = ("median", "highest", "lowest", "most_recipients_highest", "fewest_recipients_highest")


class ScenarioError(RuntimeError):
    """A fixture cannot be selected or recorded."""


@dataclass(frozen=True)
class Rule:
    """How one fixture is chosen from the stored validation decisions."""

    key: str
    title: str
    scenario_ids: tuple[str, ...]  # () matches every scenario
    variants: tuple[str, ...]  # () matches every variant
    misdirected: bool
    stored_decision: str
    pick: str
    guards: str
    rule: str


RULES = (
    Rule("routine_allow", "Routine project mail", ("S05",), ("internal_project",), False, "allow", "median",
         "The no-intervention path: an allow with no flagged recipient.",
         "The S05 internal project draft at the median email risk score among those allowed."),
    Rule("added_recipient_warn", "Added external recipient", ("S02",), ("added_external",), True, "warn", "fewest_recipients_highest",
         "A warning on an added recipient, with the API's codes on the flagged recipient.",
         "Among S02 added-recipient mistakes that were warned: the fewest recipients, then the highest email risk score."),
    Rule("legitimate_first_contact_allow", "New legitimate collaborator", ("S03",), ("legitimate_first_contact",), False, "allow", "highest",
         "Legitimate novelty stays allowed, with a limited-history limitation and not a warning.",
         "The S03 legitimate first contact allowed with the highest email risk score, the one closest to the cutoff."),
    Rule("new_domain_allow", "Uncommon external domain", ("S06",), ("legitimate_new_domain",), False, "allow", "highest",
         "A legitimate first contact at a new external domain stays allowed.",
         "The S06 legitimate new-domain draft allowed with the highest email risk score."),
    Rule("topic_change_allow", "Legitimate topic change", ("S07",), ("legitimate_topic_change",), False, "allow", "highest",
         "A topic change alone is not a mistake.",
         "The S07 legitimate topic change allowed with the highest email risk score."),
    Rule("known_miss_lookalike", "Lookalike replacement (S01)", ("S01",), ("lookalike_replacement",), True, "allow", "highest",
         "A known miss: the policy allows a lookalike replacement. It must not change silently.",
         "The S01 lookalike mistake that was allowed, with the highest email risk score."),
    Rule("known_miss_topic", "Familiar recipient, unusual topic (S04)", ("S04",), ("familiar_topic_mismatch",), True, "allow", "highest",
         "A known miss: the policy allows a familiar-recipient topic mistake.",
         "The S04 familiar-recipient topic mistake that was allowed, with the highest email risk score."),
    Rule("known_miss_first_contact", "Mistaken first contact (S11)", ("S11",), ("mistaken_first_contact",), True, "allow", "highest",
         "A known miss: the policy allows a mistaken first contact.",
         "The S11 mistaken first contact that was allowed, with the highest email risk score."),
    Rule("cold_start_allow", "Cold-start sender", ("S09",), ("cold_start_legitimate",), False, "allow", "median",
         "A sender with no earlier mail is assessed with a visible limitation, not forced to allow or warn.",
         "The S09 cold-start draft at the median email risk score among those allowed."),
    Rule("little_text_allow", "Little text, legitimate", ("S09",), ("little_text_legitimate",), False, "allow", "highest",
         "Empty or tiny text is assessed with a LIMITED_TEXT limitation.",
         "The S09 little-text legitimate draft allowed with the highest email risk score."),
    Rule("little_text_mistake_warn", "Little text, unintended recipient", ("S09",), ("little_text_unintended",), True, "warn", "lowest",
         "Little text does not stop a warning on a swapped recipient.",
         "The S09 little-text unintended draft that was warned (one on validation)."),
    Rule("multi_recipient_warn", "Several recipients, one or more flagged", ("S08",), (), True, "warn", "most_recipients_highest",
         "Maximum aggregation: the email risk is the highest recipient risk and every recipient at or above the cutoff is flagged.",
         "Among S08 multi-recipient mistakes that were warned: the most recipients, then the highest email risk score."),
    Rule("multi_recipient_allow", "Several recipients, none flagged", ("S05", "routine"), ("internal_project", "established_contact"), False, "allow", "most_recipients_highest",
         "Maximum aggregation on an allowed draft: the email risk is the highest recipient risk.",
         "Among routine drafts that were allowed: the most recipients, then the highest email risk score."),
    Rule("threshold_equality_warn", "Score exactly at the cutoff", (), (), True, "warn", "lowest",
         "Equality warns: the lowest-scoring warned mistake scores exactly T_warn, and a score equal to the cutoff must warn.",
         "The warned mistake with the lowest email risk score on validation_product_like."),
)

# Derived fixtures: one transformation of a base fixture's request. The base
# fixture's scores are the expectation, apart from what the derivation changes.
DERIVED = (
    ("duplicate_roles", "routine_allow", "Repeated address across roles",
     "The routine request with its first To address repeated in Cc (upper case, padded with spaces). "
     "The API merges it into one recipient with both roles and scores it as before.",
     "Repeated addresses merge across roles into one recipient, keeping every role; scores do not change."),
    ("invalid_malformed_address", "routine_allow", "Malformed address",
     "The routine request with '@' in its first To address replaced by '.'.",
     "A malformed address is invalid_input: no decision, no score."),
    ("invalid_no_recipients", "routine_allow", "No recipients",
     "The routine request with To, Cc, and Bcc emptied.",
     "A draft with no recipient is invalid_input."),
    ("invalid_label_field", "routine_allow", "Answer field in the request",
     "The routine request plus a top-level scenario_id field.",
     "A label, scenario, split, or score field is rejected by name and never read."),
    ("unavailable_unknown_address", "routine_allow", "Address outside the directory",
     "The routine request with the last letter of its first To address removed.",
     "A well-formed address outside the snapshot directory is unavailable, never a warning or an allow."),
    ("unavailable_unknown_snapshot", "routine_allow", "Unknown snapshot",
     "The routine request with context_snapshot_id set to an unknown id.",
     "An unknown snapshot is unavailable."),
)


# ------------------------------------------------------------------ selection


def load_frame(data_dir: Path, policy_dir: Path) -> pd.DataFrame:
    """Validation drafts with their stored decision. Frozen records are never kept."""
    from med_monitor.data import stream_rows, validation_ids

    _, keep = validation_ids(data_dir)
    drafts = stream_rows(Path(data_dir) / "drafts.csv", keep, columns=("draft_id", "subset", "scenario_id", "scenario_variant"))
    recipients = stream_rows(Path(data_dir) / "draft_recipients.csv", keep, columns=("draft_id",))
    scores = pd.read_csv(Path(policy_dir) / "validation_scores.csv", float_precision="round_trip")
    scores["draft_id"] = scores["draft_id"].astype(str)
    frame = drafts.merge(scores[["draft_id", "email_risk", "misdirected", "warned"]], on="draft_id", how="inner")
    frame = frame.loc[frame["subset"] == SELECTION_SUBSET].copy()
    frame["recipients"] = frame["draft_id"].map(recipients.groupby("draft_id").size()).astype(int)
    frame["misdirected"] = frame["misdirected"].astype(bool)
    frame["warned"] = frame["warned"].astype(bool)
    return frame


def select_fixture(frame: pd.DataFrame, rule: Rule) -> str:
    """Apply one rule to the stored decisions and return the chosen draft id."""
    if rule.pick not in PICKS:
        raise ScenarioError(f"Unknown pick {rule.pick}")
    chosen = frame.loc[(frame["misdirected"] == rule.misdirected) & (frame["warned"] == (rule.stored_decision == "warn"))]
    if rule.scenario_ids:
        chosen = chosen.loc[chosen["scenario_id"].isin(rule.scenario_ids)]
    if rule.variants:
        chosen = chosen.loc[chosen["scenario_variant"].isin(rule.variants)]
    if chosen.empty:
        raise ScenarioError(f"No {SELECTION_SUBSET} draft matches rule {rule.key}")
    if rule.pick == "median":
        ordered = chosen.sort_values(["email_risk", "draft_id"], kind="mergesort")
        return str(ordered.iloc[len(ordered) // 2]["draft_id"])
    if rule.pick == "highest":
        return str(chosen.sort_values(["email_risk", "draft_id"], ascending=[False, True], kind="mergesort").iloc[0]["draft_id"])
    if rule.pick == "lowest":
        return str(chosen.sort_values(["email_risk", "draft_id"], kind="mergesort").iloc[0]["draft_id"])
    if rule.pick == "most_recipients_highest":
        return str(chosen.sort_values(["recipients", "email_risk", "draft_id"], ascending=[False, False, True], kind="mergesort").iloc[0]["draft_id"])
    return str(chosen.sort_values(["recipients", "email_risk", "draft_id"], ascending=[True, False, True], kind="mergesort").iloc[0]["draft_id"])


def select_fixtures(frame: pd.DataFrame, rules=RULES) -> dict[str, str]:
    return {rule.key: select_fixture(frame, rule) for rule in rules}


# -------------------------------------------------------------------- requests


def base_requests(data_dir: Path, draft_ids: list[str]) -> dict[str, dict]:
    """Phase 1 requests for validation drafts, rebuilt from the published tables. A frozen id raises."""
    from med_monitor.data import load_requests

    return load_requests(Path(data_dir), sorted(set(draft_ids)))


def _with_reference(payload: dict, draft_id: str) -> dict:
    return {**payload, "draft_reference": f"fixture-{draft_id}"}


def derive_request(key: str, base: dict) -> dict:
    """The request of a derived fixture, from its base fixture's request."""
    first = base["to"][0]["address"]
    local, _, domain = first.partition("@")
    if key == "duplicate_roles":
        return {**base, "cc": [{"address": f"  {first.upper()}  ", "display_name": "Duplicate Role"}, *base["cc"]]}
    if key == "invalid_malformed_address":
        return {**base, "to": [{**base["to"][0], "address": first.replace("@", ".")}, *base["to"][1:]]}
    if key == "invalid_no_recipients":
        return {**base, "to": [], "cc": [], "bcc": []}
    if key == "invalid_label_field":
        return {**base, "scenario_id": "S05"}
    if key == "unavailable_unknown_address":
        return {**base, "to": [{**base["to"][0], "address": f"{local[:-1]}@{domain}"}, *base["to"][1:]]}
    if key == "unavailable_unknown_snapshot":
        return {**base, "context_snapshot_id": "unknown-snapshot"}
    raise ScenarioError(f"Unknown derivation {key}")


def requests_for(record: dict, data_dir: Path) -> dict[str, dict]:
    """The exact request of every fixture in the record, keyed by fixture key."""
    ids = [item["source"]["draft_id"] for item in record["fixtures"] if item["kind"] == "draft"]
    base = base_requests(data_dir, ids)
    by_key = {item["key"]: item for item in record["fixtures"]}
    out = {}
    for item in record["fixtures"]:
        if item["kind"] == "draft":
            out[item["key"]] = _with_reference(base[item["source"]["draft_id"]], item["source"]["draft_id"])
        else:
            parent = by_key[item["derived_from"]]
            out[item["key"]] = derive_request(item["key"], _with_reference(base[parent["source"]["draft_id"]], parent["source"]["draft_id"]))
    return out


# ------------------------------------------------------------------- expected


def expected_from(status_code: int, body: dict) -> dict:
    """What a response must keep: the fields of the contract, without addresses or text from the request."""
    if body.get("status") == "assessed":
        return {
            "status_code": status_code,
            "status": "assessed",
            "decision": body["decision"],
            "email_risk_score": body["email_risk_score"],
            "recipients": [
                {
                    "roles": item["roles"],
                    "risk_score": item["risk_score"],
                    "flagged": item["flagged"],
                    "reason_codes": item["reason_codes"],
                    "evidence_limitations": item["evidence_limitations"],
                }
                for item in body["recipients"]
            ],
            "explanation": body["explanation"],
            "provenance": body["provenance"],
        }
    return {
        "status_code": status_code,
        "status": "unable_to_assess",
        "category": body.get("category"),
        "message": body.get("message"),
        "provenance_reported": "provenance" in body,
    }


def _codes(items) -> list[tuple[str, str]]:
    return [(item["code"], item["text"]) for item in items or []]


def _values(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _values(item)
    else:
        yield value


def compare(expected: dict, status_code: int, body: dict | None, *, reference: str | None = None) -> list[str]:
    """Every way `body` differs from what the record expects. An empty list means the fixture holds."""
    if not isinstance(body, dict):
        return ["the response is not a JSON object"]
    problems: list[str] = []
    if status_code != expected["status_code"]:
        problems.append(f"HTTP {status_code}, expected {expected['status_code']}")
    if body.get("status") != expected["status"]:
        problems.append(f"status {body.get('status')!r}, expected {expected['status']!r}")
    if body.get("mode") != MODE:
        problems.append(f"mode {body.get('mode')!r}, expected {MODE!r}")
    if reference is not None and body.get("draft_reference") != reference:
        problems.append("the draft reference was not returned unchanged")

    if expected["status"] == "unable_to_assess":
        if body.get("decision") is not None or body.get("email_risk_score") is not None:
            problems.append("a failure carries a decision or a risk score")
        if body.get("recipients") is not None or body.get("flagged_recipients") is not None:
            problems.append("a failure carries recipients")
        if "allow" in list(_values(body)):
            problems.append("a failure response contains 'allow'")
        if body.get("category") != expected["category"]:
            problems.append(f"category {body.get('category')!r}, expected {expected['category']!r}")
        if body.get("message") != expected["message"]:
            problems.append(f"message {body.get('message')!r}, expected {expected['message']!r}")
        if ("provenance" in body) != expected["provenance_reported"]:
            problems.append("version provenance is present or absent unlike the record")
        return problems

    if body.get("status") != "assessed":
        return problems
    try:
        problems.extend(_compare_assessed(expected, body))
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        problems.append(f"the assessed response is malformed ({type(error).__name__}: {error})")
    return problems


def _compare_assessed(expected: dict, body: dict) -> list[str]:
    problems: list[str] = []
    provenance = body.get("provenance") or {}
    for key, value in expected["provenance"].items():
        if provenance.get(key) != value:
            problems.append(f"provenance {key} is {provenance.get(key)!r}, expected {value!r}")
    if provenance.get("blocking_enabled") is not False:
        problems.append("provenance does not report blocking as disabled")
    if body.get("decision") not in ("allow", "warn"):
        problems.append(f"decision {body.get('decision')!r} is neither allow nor warn")
    if body.get("decision") != expected["decision"]:
        problems.append(f"decision {body.get('decision')!r}, expected {expected['decision']!r}")
    email = body.get("email_risk_score")
    if not isinstance(email, (int, float)) or abs(email - expected["email_risk_score"]) > SCORE_TOLERANCE:
        problems.append(f"email risk score {email!r}, expected {expected['email_risk_score']!r}")
    t_warn = provenance.get("T_warn")
    recipients = body.get("recipients") or []
    scores = [item["risk_score"] for item in recipients]
    if isinstance(t_warn, (int, float)) and isinstance(email, (int, float)) and scores:
        if email != max(scores):
            problems.append("the email risk score is not the maximum recipient risk score")
        if body.get("decision") != ("warn" if email >= t_warn else "allow"):
            problems.append("the decision does not follow the cutoff (equality must warn)")
        if [item["address"] for item in recipients if item["risk_score"] >= t_warn] != body.get("flagged_recipients"):
            problems.append("flagged recipients are not exactly the recipients at or above the cutoff")
    if len(recipients) != len(expected["recipients"]):
        problems.append(f"{len(recipients)} recipients, expected {len(expected['recipients'])}")
    for position, (got, want) in enumerate(zip(recipients, expected["recipients"], strict=False)):
        label = f"recipient {position}"
        if got["roles"] != want["roles"]:
            problems.append(f"{label} roles {got['roles']}, expected {want['roles']}")
        if abs(got["risk_score"] - want["risk_score"]) > SCORE_TOLERANCE:
            problems.append(f"{label} risk score {got['risk_score']!r}, expected {want['risk_score']!r}")
        if got["flagged"] != want["flagged"]:
            problems.append(f"{label} flagged {got['flagged']}, expected {want['flagged']}")
        if _codes(got["reason_codes"]) != _codes(want["reason_codes"]):
            problems.append(f"{label} reason codes {[code for code, _ in _codes(got['reason_codes'])]}, expected {[code for code, _ in _codes(want['reason_codes'])]}")
        if _codes(got["evidence_limitations"]) != _codes(want["evidence_limitations"]):
            problems.append(
                f"{label} evidence limitations {[code for code, _ in _codes(got['evidence_limitations'])]}, "
                f"expected {[code for code, _ in _codes(want['evidence_limitations'])]}"
            )
    if body.get("explanation") != expected["explanation"]:
        problems.append("the explanation sentences changed")
    return problems


# --------------------------------------------------------------------- record


def record_scenarios(client, data_dir: Path, policy_dir: Path, output: Path) -> dict:
    """Select fixtures by rule, run them through the frozen bundle, and store the outcomes once.

    `client` is a FastAPI test client or an httpx client on a running service.
    The record is refused if any fixture's decision or score disagrees with the
    stored validation table, or if a derived fixture changes a score it must not.
    """
    ready = client.get("/ready")
    if ready.status_code != 200:
        raise ScenarioError(f"The service is not ready: {ready.text}")
    served = ready.json()
    frame = load_frame(data_dir, policy_dir)
    picked = select_fixtures(frame)
    stored = frame.set_index("draft_id")
    base = base_requests(data_dir, list(picked.values()))
    fixtures: list[dict] = []
    by_key: dict[str, dict] = {}
    for rule in RULES:
        draft_id = picked[rule.key]
        payload = _with_reference(base[draft_id], draft_id)
        response = client.post("/assess", json=payload)
        body = response.json()
        if response.status_code != 200 or body.get("status") != "assessed":
            raise ScenarioError(f"Fixture {rule.key} ({draft_id}) was not assessed: HTTP {response.status_code}")
        row = stored.loc[draft_id]
        if (body["decision"] == "warn") != bool(row["warned"]) or abs(body["email_risk_score"] - float(row["email_risk"])) > STORED_PARITY_BOUND:
            raise ScenarioError(f"Fixture {rule.key} ({draft_id}) disagrees with the stored validation decision")
        desired = "warn" if rule.misdirected else "allow"
        item = {
            "key": rule.key,
            "title": rule.title,
            "kind": "draft",
            "guards": rule.guards,
            "source": {
                "draft_id": draft_id,
                "subset": SELECTION_SUBSET,
                "selection": rule.rule,
                "stored_decision": "warn" if row["warned"] else "allow",
                "stored_email_risk": float(row["email_risk"]),
            },
            "scenario": {"id": str(row["scenario_id"]), "variant": str(row["scenario_variant"]), "note": "audit metadata: never part of a request"},
            "misdirected": rule.misdirected,
            "desired": desired,
            "known_miss": desired != body["decision"],
            "expected": expected_from(response.status_code, body),
        }
        fixtures.append(item)
        by_key[rule.key] = item
    for key, parent, title, derivation, guards in DERIVED:
        parent_item = by_key[parent]
        parent_id = parent_item["source"]["draft_id"]
        payload = derive_request(key, _with_reference(base[parent_id], parent_id))
        response = client.post("/assess", json=payload)
        body = response.json()
        expected = expected_from(response.status_code, body)
        if key == "duplicate_roles":
            want = parent_item["expected"]
            same = (
                body.get("status") == "assessed"
                and body["decision"] == want["decision"]
                and abs(body["email_risk_score"] - want["email_risk_score"]) <= STORED_PARITY_BOUND
                and [item["risk_score"] for item in body["recipients"]] == [item["risk_score"] for item in want["recipients"]]
                and body["recipients"][0]["roles"] == ["to", "cc"]
            )
            if not same:
                raise ScenarioError("The repeated-address fixture changed a score or lost a role")
        elif expected["status"] != "unable_to_assess":
            raise ScenarioError(f"Fixture {key} was assessed; it must be unable to assess")
        fixtures.append(
            {
                "key": key,
                "title": title,
                "kind": "derived",
                "derived_from": parent,
                "derivation": derivation,
                "guards": guards,
                "source": {"draft_id": parent_id, "subset": SELECTION_SUBSET},
                "expected": expected,
            }
        )
    record = {
        "deploy_version": DEPLOY_VERSION,
        "kind": "scenario_regression",
        "recorded_at": now_utc(),
        "subset": WORKLOAD_SUBSET,
        "bundle": {key: served[key] for key in ("contract_version", "snapshot_id", "model_version", "feature_spec_version", "policy_version", "T_warn", "blocking_enabled")},
        "sources": {
            "selection": "artifacts/med-policy-v2/validation_scores.csv: the policy's stored decisions on validation_product_like, chosen by rule",
            "requests": "rebuilt from data/med-synth-v4 validation drafts by draft id, streamed so that no frozen record is kept; no address, subject, or body is stored here",
            "expected": "recorded once from the frozen bundle through the API; each decision and email risk agrees with the stored validation table to 1e-12",
            "desired": "the product intent in docs/phase_1/SCENARIOS.md: a misdirected email should warn and a legitimate one should allow",
        },
        "score_tolerance": SCORE_TOLERANCE,
        "fixtures": fixtures,
    }
    write_record(output, record)
    return record


def load_record(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def replay(record: dict, client, requests: dict[str, dict]) -> dict:
    """Send every fixture to a service and compare each response with the record."""
    results = []
    for item in record["fixtures"]:
        payload = requests[item["key"]]
        response = client.post("/assess", json=payload)
        try:
            body = response.json()
        except ValueError:
            body = None
        problems = compare(item["expected"], response.status_code, body, reference=payload.get("draft_reference"))
        results.append(
            {
                "key": item["key"],
                "passed": not problems,
                "problems": problems,
                "status_code": response.status_code,
                "decision": body.get("decision") if isinstance(body, dict) else None,
            }
        )
    failed = [item for item in results if not item["passed"]]
    return {"fixtures": results, "passed": len(results) - len(failed), "failed": len(failed)}
