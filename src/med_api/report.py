"""Generate docs/phase_6.

Latency numbers come from the latency record of the served policy bundle
(`artifacts/med-api-latency/<policy version>/latency.json`). Example response
bodies come from live calls to the app on fictional `.example` requests; the
request id is replaced with a placeholder so the docs are stable. Example
drafts are chosen by rule from the policy's validation table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from med_data.io import read_dataset
from med_api.app import create_app
from med_api.context import ApiPaths
from med_api.fixtures import example_draft_ids, request_from_draft
from med_api.normalize import ALLOWED_FIELDS, DENIED_NAME_PARTS
from med_api.service import CODE_TEXT, LOG_FIELDS
from med_api.version import (
    API_CONTRACT_VERSION,
    DEFAULT_SCORING_TIMEOUT_SECONDS,
    MAX_BODY_CHARS,
    MAX_RECIPIENTS,
    MAX_SUBJECT_CHARS,
    ORGANIZATION_DOMAIN,
    SNAPSHOT_ID,
)



def write_documents(paths: ApiPaths, docs_dir: Path, latency_path: Path) -> list[Path]:
    latency = json.loads(Path(latency_path).read_text(encoding="utf-8")) if Path(latency_path).exists() else None
    examples = _examples(paths)
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in (
        ("API_CONTRACT.md", _contract(examples)),
        ("SCORING_FLOW.md", _flow(latency, _policy_results(paths))),
        ("ERROR_BEHAVIOR.md", _errors(examples)),
    ):
        path = docs_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def _examples(paths: ApiPaths) -> dict:
    dataset = read_dataset(paths.data)
    scores = pd.read_csv(paths.policy.parent / "validation_scores.csv", float_precision="round_trip")
    picks = example_draft_ids(dataset, scores)
    warn_request = request_from_draft(dataset, picks["warn"])
    allow_request = request_from_draft(dataset, picks["allow"])
    invalid_request = dict(allow_request, to=[{"address": "not-an-email"}], cc=[], bcc=[])
    unknown_request = dict(allow_request, to=[{"address": "nobody@example"}], cc=[], bcc=[])
    snapshot_request = dict(allow_request, context_snapshot_id="other")
    out = {"requests": {"warn": warn_request, "allow": allow_request}, "picks": picks}
    with TestClient(create_app(paths)) as client:
        for key, payload in (
            ("warn", warn_request),
            ("allow", allow_request),
            ("invalid_input", invalid_request),
            ("unknown_address", unknown_request),
            ("unknown_snapshot", snapshot_request),
        ):
            response = client.post("/assess", json=payload)
            body = response.json()
            body["request_id"] = "req_example"
            body["duration_ms"] = "<measured>"
            out[key] = {"status_code": response.status_code, "body": body}
    return out


def _policy_results(paths: ApiPaths) -> dict:
    """Stored policy results of the served bundle, read through the policy package. Nothing is rescored."""
    from med_policy.report import stored_results

    return stored_results(Path(paths.policy).parent)


def _block(value) -> str:
    return "```json\n" + json.dumps(value, indent=2) + "\n```"


def _contract(examples: dict) -> str:
    return "\n".join(
        [
            "# Phase 6 — API contract",
            "",
            f"Contract version `{API_CONTRACT_VERSION}`. The service is a simulation over fictional `.example` mail. Every number it returns is a **risk score**, not a probability.",
            "",
            "## Endpoints",
            "",
            "| Method and path | Role | Success |",
            "| --- | --- | --- |",
            "| `GET /health` | The process is up. It does not prove the bundle loaded. | 200 |",
            "| `GET /ready` | The bundle loaded and the snapshot is resolvable. Returns versions and `T_warn`. | 200, else 503 |",
            "| `POST /assess` | One simulated assessment. | 200 assessed, 422 `invalid_input`, 503 `unavailable` |",
            "| `POST /feedback` | Store a reviewed label for an earlier assessment. Does not score or train. | 200, else 422 |",
            "",
            "## Assessment request",
            "",
            "| Field | Required | Rule |",
            "| --- | --- | --- |",
            "| `draft_timestamp` | yes | ISO 8601 with a timezone. A naive timestamp is `invalid_input`. It is the historical cutoff. |",
            f"| `sender` | yes | Address string or `{{address, display_name}}`. Must resolve to an internal `{ORGANIZATION_DOMAIN}` contact. |",
            f"| `to`, `cc`, `bcc` | yes | Lists, each may be empty. Entries are address strings or `{{address, display_name}}`. 1 to {MAX_RECIPIENTS} unique addresses in total. |",
            f"| `subject` | yes | String, may be empty, at most {MAX_SUBJECT_CHARS} characters. |",
            f"| `body` | yes | Plain text, may be empty, at most {MAX_BODY_CHARS:,} characters. No HTML parsing. |",
            f"| `context_snapshot_id` | yes | Only `{SNAPSHOT_ID}` is accepted. The server resolves it; the caller does not upload history. |",
            "| `draft_reference` | no | Caller correlation label, returned unchanged. Not a feature. |",
            "",
            f"Accepted top-level fields: {', '.join(f'`{name}`' for name in sorted(ALLOWED_FIELDS))}. Any other field is `invalid_input`. A field whose name contains any of {', '.join(f'`{part}`' for part in DENIED_NAME_PARTS)} is rejected by name, at any depth, and its value is never read.",
            "",
            "Addresses follow assumption A7: surrounding whitespace is trimmed, matching is case-insensitive on the whole address, only ASCII `local@domain` with a domain of `example` or ending in `.example` is accepted, and the same address across To, Cc, and Bcc becomes one recipient that keeps every role. The first non-empty display name is kept. Recipient order is first appearance. Limits count characters and nothing is truncated.",
            "",
            "## Assessed response",
            "",
            "| Field | Meaning |",
            "| --- | --- |",
            "| `request_id` | Server-generated for every request. |",
            "| `draft_reference` | The caller's label, when one was sent. |",
            "| `contract_version` | `med-api-v1`. |",
            "| `status` | `assessed`. |",
            "| `mode` | `simulation`. |",
            "| `decision` | `allow` or `warn`. Blocking is disabled, so `block` is never returned. |",
            "| `email_risk_score` | Maximum recipient risk score. |",
            "| `flagged_recipients` | Every address whose risk score is at or above `T_warn`. |",
            "| `recipients` | One entry per unique address: `address`, `display_name`, `roles`, `risk_score`, `flagged`, `reason_codes`, `evidence_limitations`. |",
            "| `explanation` | Short sentences, including whether draft-text similarity was an input of the served model. |",
            "| `provenance` | Model, feature-spec, and policy versions, `T_warn`, `blocking_enabled: false`, snapshot id, effective cutoff, and the history rule. |",
            "| `duration_ms` | Handler time for this assessment. |",
            "",
            "## Codes",
            "",
            "Context codes and limitations are read from the feature row. They do not change the decision and are not read from model coefficients. `CONTENT_RELATIONSHIP_MISMATCH` is a reason tied to the model: it is emitted on a flagged recipient only when its content cosine was observed, is below the typical train value (the mean observed cosine on train, from the feature quality report), and raising only that value to the typical one would drop the recipient's risk score below `T_warn`. The check rescores the frozen model on that one changed row; it never changes the decision.",
            "",
            "| Code | Kind | Emitted when | Text |",
            "| --- | --- | --- | --- |",
            f"| `LIMITED_RELATIONSHIP_HISTORY` | evidence limitation, any recipient | `recipient_novel_to_sender` is 1 or `pair_recency_observed` is 0 | {CODE_TEXT['LIMITED_RELATIONSHIP_HISTORY']} |",
            f"| `LIMITED_TEXT` | evidence limitation, any recipient | draft text empty, short, or out of vocabulary | {CODE_TEXT['LIMITED_TEXT']} |",
            f"| `EXTERNAL_RECIPIENT` | context, flagged recipient only | `recipient_is_internal` is 0 | {CODE_TEXT['EXTERNAL_RECIPIENT']} |",
            f"| `LOOKALIKE_CONTACT_CONTEXT` | context, flagged recipient only | `near_name_count` is at least 1 | {CODE_TEXT['LOOKALIKE_CONTACT_CONTEXT']} |",
            f"| `CONTENT_RELATIONSHIP_MISMATCH` | reason, flagged recipient only | observed content cosine below the typical train value, and a rescore with only that value raised to typical falls below `T_warn` | {CODE_TEXT['CONTENT_RELATIONSHIP_MISMATCH']} |",
            f"| `UNUSUAL_RECIPIENT_COMBINATION` | context, flagged recipient only | co-recipient support applies and the partner fraction is 0 | {CODE_TEXT['UNUSUAL_RECIPIENT_COMBINATION']} |",
            "",
            "## Feedback request",
            "",
            "`{request_id, recipient, label}` with `label` of `intended` or `unintended`. The request id must be an assessment this process returned, and the recipient must have been on it. Otherwise the response is `invalid_input` and nothing is written. Accepted feedback appends one JSON line (request id, contact id, label, versions, time) to a local, gitignored file. `/assess` never reads it, and it never changes the model, the policy, or the cutoff.",
            "",
            "## Examples",
            "",
            f"These bodies come from live calls on fictional validation drafts, chosen by rule from the policy's validation table. `{examples['picks']['warn']}` is the warned validation mistake with the lowest email risk score; `{examples['picks']['allow']}` is the allowed routine draft at the median score.",
            "",
            f"### Warn request (`{examples['picks']['warn']}`)",
            "",
            _block(examples["requests"]["warn"]),
            "",
            f"### Warn response (HTTP {examples['warn']['status_code']})",
            "",
            _block(examples["warn"]["body"]),
            "",
            f"### Allow response for `{examples['picks']['allow']}` (HTTP {examples['allow']['status_code']})",
            "",
            _block(examples["allow"]["body"]),
            "",
            f"### `invalid_input` response (HTTP {examples['invalid_input']['status_code']})",
            "",
            _block(examples["invalid_input"]["body"]),
            "",
            f"### `unavailable` response (HTTP {examples['unknown_address']['status_code']})",
            "",
            _block(examples["unknown_address"]["body"]),
            "",
        ]
    )


def _flow(latency: dict | None, results: dict) -> str:
    policy = results["policy"]
    parts = [
        "# Phase 6 — Scoring flow",
        "",
        f"Served bundle: dataset snapshot `{SNAPSHOT_ID}`, features `{policy['feature_spec_version']}`, model `{policy['model_version']}` (`{policy['model_run_name']}`), policy `{policy['policy_version']}`, contract `{API_CONTRACT_VERSION}`.",
        "",
        "## Startup",
        "",
        "At startup the app loads, once and without fitting anything:",
        "",
        "1. the feature artifact manifest, with every file checksum verified",
        f"2. the `{SNAPSHOT_ID}` tables, with dataset checksums verified",
        "3. the model and the policy through `med_policy.decision.load_bundle`, which refuses a version, run-name, or checksum mismatch",
        "4. the saved text transformer",
        "5. the contact directory and the sent-mail history index; the transformer is bound to the index once",
        "",
        "`/ready` returns 503 until that succeeds. `/health` answers either way. If the load fails, every `/assess` returns `unavailable`.",
        "",
        "## Request",
        "",
        "1. Parse the JSON body. Reject label, scenario, split, family, and score fields by name, and any field outside the contract.",
        "2. Normalize (A7): timestamp with timezone, `.example` addresses, merge repeated addresses across roles, limits.",
        f"3. Resolve the snapshot id (`{SNAPSHOT_ID}` only), the sender (internal contact), and every recipient in the directory.",
        "4. Build one `DraftQuery`. The family exclusion is empty, because a client draft has no family. A non-empty body's hash is excluded from history so the draft is not its own earlier mail. History is sent mail strictly earlier than the cutoff.",
        "5. Call `med_policy.decision.assess_draft` under the scoring timeout. It runs `transform_draft`, the frozen model, and the policy. The API does not reimplement the cutoff, the maximum, or the model.",
        "6. Map the result to the response. Reason codes and limitations are read from the same feature rows. They do not change the decision.",
        "",
        "`T_warn` is loaded from `policy.json`. It is not reselected, and it is not recomputed from `validation_scores.csv`.",
        "",
        "## What the service does not change",
        "",
        *_limits(results),
        "- A well-formed address that is not in the snapshot directory, such as a typo, is `unavailable`, not a warning. Changing that is a contract decision.",
        "- No rule warns because a recipient is new, external, a lookalike, or off-topic.",
        "",
        "## Latency (AC05)",
        "",
    ]
    if latency is None:
        parts.append("Not measured for this bundle.")
        parts.append("")
        return "\n".join(parts)
    parity = latency["parity"]
    env = latency["environment"]
    workload = latency.get("workload", {})
    history = workload.get("sender_history_messages", {})
    parts += [
        f"Measured once with `python -m med_api latency` for policy bundle `{policy['policy_version']}`: {latency['measured_calls']} `POST /assess` calls on `{latency['subset']}` requests after {latency['warmup_calls']} unmeasured warm-up calls, concurrency {latency['concurrency']}. Boundary: {latency['boundary']}. This contains assumption A10's boundary (backend receipt to response preparation) and adds only the in-process client and ASGI hop. The record is keyed by the policy bundle and is never overwritten.",
        "",
        f"Workload: {workload.get('drawn', '')}. Warm-up: {workload.get('warmup', '')}.",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| Client p50 | {latency['client_p50_ms']:.2f} ms |",
        f"| Client p95 | {latency['client_p95_ms']:.2f} ms |",
        f"| Client p99 | {latency['client_p99_ms']:.2f} ms |",
        f"| Client max | {latency['client_max_ms']:.2f} ms |",
        f"| Server-side p50 / p95 / max | {latency['server_p50_ms']:.2f} / {latency['server_p95_ms']:.2f} / {latency['server_max_ms']:.2f} ms |",
        f"| Target | p95 below {latency['target_p95_ms']:.0f} ms |",
        f"| AC05 | **{latency['ac05']}** |",
        f"| Cold start | {latency['cold_start_seconds']:.2f} s ({latency['cold_start_includes']}) |",
        f"| Statuses | {', '.join(f'{k}: {v}' for k, v in latency['statuses'].items())} |",
        f"| Recipients per request | {', '.join(f'{k}: {v}' for k, v in latency['recipient_mix'].items())} |",
        f"| Month of draft | {', '.join(f'{k}: {v}' for k, v in workload.get('months', {}).items())} |",
        f"| Sender history (earlier sent messages) | {', '.join(f'{k}: {v}' for k, v in history.get('bands', {}).items())}; quartiles {history.get('p25', 0):.0f} / {history.get('p50', 0):.0f} / {history.get('p75', 0):.0f}, max {history.get('max', 0)} |",
        f"| Hardware and OS | {env['platform']}, {env['machine']}, {env['cpu_count']} CPUs |",
        f"| Versions | {', '.join(f'{k} {v}' for k, v in latency['versions'].items())} |",
        "",
        f"AC05 is recorded as **{latency['ac05']}** on the client-side p95 of {latency['client_p95_ms']:.2f} ms, on this machine only. The model and policy were not changed to improve it. The `CONTENT_RELATIONSHIP_MISMATCH` check was added after this measurement; it rescores one row per flagged recipient, so it adds work only to warned drafts (8 of 4,000 in this workload), and the record was not remeasured because the latency command never overwrites a record. The content-cosine centroid is built from one sparse slice of the history matrix per recipient, not one row read at a time; that change leaves every feature value identical.",
        "",
        "## Parity with the frozen validation scores",
        "",
        f"During the same run, {parity['decisions_matching_validation_table']} of {parity['assessed']} API decisions matched the `warned` column of `validation_scores.csv`. The largest email risk score difference was {parity['max_abs_email_risk_difference']:.2e}. Feature CSVs are lossless, so the remaining difference is summation order in the model, and the policy selection already required identical decisions on every validation draft.",
    ]
    for item in parity.get("drafts_at_T_warn", []):
        parts += [
            "",
            f"`{item['draft_id']}` is the validation draft whose score set `T_warn` ({item['T_warn']!r}). Through the API it scores {item['api_email_risk_score']!r} ({item['api_email_risk_score'] - item['T_warn']:+.1e} from the cutoff) and returns `{item['decision']}`.",
        ]
    parts.append("")
    return "\n".join(parts)


def _limits(results: dict) -> list[str]:
    test = results.get("test")
    if not test:
        return ["- The frozen test pass has not run for this policy."]
    product = test["subsets"]["test_product_like"]
    fi = product["policy"]["interventions"]
    email = product["policy"]["email"]
    missed = {}
    for subset in test["subsets"].values():
        for row in subset["outcomes"]["missed_mistakes"]:
            missed[row["scenario_id"]] = missed.get(row["scenario_id"], 0) + 1
    warned = {row["scenario_id"] for subset in test["subsets"].values() for row in subset["outcomes"]["warned_mistakes"]}
    never = sorted(set(missed) - warned)
    budget = "within" if fi["interval_per_1000_exact"]["high"] <= fi["budget_per_1000"] else "above"
    return [
        f"- The service serves the frozen cutoff. On the one `test_product_like` pass it warned on {email['true_positives']} of {email['positives']} misdirected emails with {fi['false_interventions']} false interventions on {fi['legitimate_emails']:,} legitimate emails. The exact upper 95% bound, {fi['interval_per_1000_exact']['high']:.2f} per 1,000, is {budget} the budget of {fi['budget_per_1000']:g} only if emails were independent; most test drafts share one sender, so AC01 is recorded as insufficient evidence. That is a simulation result.",
        f"- Scenarios never warned in the frozen test subsets: {', '.join(never) or 'none'}. The API does not change that.",
    ]


def _errors(examples: dict) -> str:
    return "\n".join(
        [
            "# Phase 6 — Error behavior",
            "",
            "Both failure categories are **unable to assess** (assumption A9). `decision`, `email_risk_score`, `recipients`, and `flagged_recipients` are null. The service never returns `allow` for a failure, and never returns an empty flagged list as if the assessment succeeded. A whole request fails if any recipient cannot be assessed.",
            "",
            "| Category | HTTP | When |",
            "| --- | --- | --- |",
            f"| `invalid_input` | 422 | Malformed JSON or address, non-`.example` domain, non-ASCII address, timestamp without a timezone, 0 or more than {MAX_RECIPIENTS} unique recipients, subject over {MAX_SUBJECT_CHARS} or body over {MAX_BODY_CHARS:,} characters, sender not an internal `{ORGANIZATION_DOMAIN}` address, unsupported fields, or a label, scenario, split, family, or score field. |",
            "| `unavailable` | 503 | Unknown snapshot id, sender or recipient address well formed but not in the directory, bundle failed to load, version or checksum mismatch, `FeatureError` or `ModelError` while scoring, a non-finite risk score, or the scoring timeout. |",
            "",
            "A failure body carries the request id, the category, a short message, and versions only when they are known. If the bundle did not load, no model or policy version is reported.",
            "",
            "No history is not a failure. A sender or recipient with no earlier mail is assessed with the existing feature fallback and may carry `LIMITED_RELATIONSHIP_HISTORY`. It is not forced to allow or warn.",
            "",
            "## Timeout",
            "",
            f"The scoring timeout is {DEFAULT_SCORING_TIMEOUT_SECONDS:g} seconds, overridable with `MED_API_SCORING_TIMEOUT_SECONDS`. It starts when the handler has a normalized request and ends when `assess_draft` returns. On timeout the response is `unavailable` with no partial decision. The scoring thread is not interrupted; its late result is discarded.",
            "",
            "## Logging",
            "",
            f"One JSON log line per assessment on logger `med_api`, with only these fields: {', '.join(f'`{name}`' for name in LOG_FIELDS)}. Subject, body, display names, email addresses, and recipient lists are never logged. Feedback lines store the contact id, not the address.",
            "",
            "## Examples",
            "",
            f"Unknown snapshot (HTTP {examples['unknown_snapshot']['status_code']}):",
            "",
            _block(examples["unknown_snapshot"]["body"]),
            "",
            f"Malformed recipient address (HTTP {examples['invalid_input']['status_code']}):",
            "",
            _block(examples["invalid_input"]["body"]),
            "",
        ]
    )
