"""Generate docs/phase_8 from the stored monitor records.

Every number in the documents comes from `reference.json`, `replay_plan.json`,
`replay.json`, `feedback_review.json`, `bundle_checks.json`, the frozen policy
file, or the constants in `med_monitor.version`. Sentences that state a result
are built from the computed statuses, so a different record gives a different
sentence instead of a stale claim. The tables show counts with denominators.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from med_monitor import alerts as alert_module
from med_monitor import experiment, version
from med_monitor.drift import ALERT, INSUFFICIENT, NO_CHANGE, NO_DRIFT, OK, STRUCTURAL, WATCH
from med_monitor.observations import score_bins
from med_monitor.version import (
    ALLOWED_STRATA,
    ARTIFACT_DIR,
    CUMULATIVE_FEATURES,
    CURRENT_WINDOWS,
    DRAFT_LEVEL_FEATURES,
    EXPERIMENT_PREVALENCE,
    MIN_EMAILS_DECISION_RATE,
    MIN_EMAILS_INPUT_DRIFT,
    MIN_EMAILS_SCORE_BAND,
    MIN_EXCESS_ROWS,
    MIN_REQUESTS_OPERATIONAL,
    MIN_REVIEWED_POSITIVES,
    MIN_ROWS_INPUT_DRIFT,
    NEAR_BAND,
    PSI_ALERT,
    PSI_WATCH,
    RATE_ALPHA,
    REFERENCE_WINDOWS,
    SHARE_SHIFT_ALERT,
    SHARE_SHIFT_WATCH,
)

STATUS_LABEL = {
    ALERT: "ALERT",
    WATCH: "watch",
    OK: "ok",
    NO_DRIFT: "no drift detected",
    NO_CHANGE: "no change detected",
    INSUFFICIENT: "insufficient sample",
    STRUCTURAL: "structural",
}
DOC_FILES = ("MONITORING.md", "DRIFT_REPLAY.md", "FEEDBACK_REVIEW.md", "EXPERIMENT_PROPOSAL.md", "RUNBOOK.md")


class MissingRecord(FileNotFoundError):
    pass


@dataclass
class Records:
    reference: dict
    plan: dict
    replay: dict
    feedback: dict
    bundles: dict
    alerts: dict
    policy: dict


def load_records(artifact_dir: Path = ARTIFACT_DIR, policy_path: Path = version.POLICY_PATH) -> Records:
    def read(name: str) -> dict:
        path = Path(artifact_dir) / name
        if not path.exists():
            raise MissingRecord(f"{path} is missing. Run the command that writes it before `report`.")
        return json.loads(path.read_text(encoding="utf-8"))

    reference, plan, replay = read("reference.json"), read("replay_plan.json"), read("replay.json")
    feedback, bundles = read("feedback_review.json"), read("bundle_checks.json")
    policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
    evaluated = alert_module.evaluate(replay, reference, alert_module.expected_version_key(policy), feedback)
    return Records(reference, plan, replay, feedback, bundles, evaluated, policy)


# ------------------------------------------------------------------ helpers


def count(value) -> str:
    return f"{int(value):,}"


def ratio(k, n, digits: int = 2) -> str:
    if not n:
        return f"{count(k)} of {count(n)}"
    return f"{count(k)} of {count(n)} ({100 * k / n:.{digits}f}%)"


def number(value, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def sci(value) -> str:
    return "n/a" if value is None else f"{value:.3g}"


def plural(amount: int, noun: str, many: str | None = None) -> str:
    return f"{count(amount)} {noun if amount == 1 else (many or noun + 's')}"


def days(value: int) -> str:
    return f"{value} day" if value == 1 else f"{value} days"


def spell(value: int) -> str:
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
    return words.get(value, str(value))


def show_version(key: str) -> str:
    """Version keys use a pipe internally; a pipe would break a Markdown table cell."""
    return key.replace("|", ", ")


def ms(value) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def label(status: str) -> str:
    return STATUS_LABEL.get(status, status)


def find(checks: list[dict], check_id: str) -> dict:
    return next(item for item in checks if item["id"] == check_id)


def window_of(records: Records, number_: int) -> dict:
    return next(item for item in records.replay["windows"] if item["window"] == number_)


def bundle_line(records: Records) -> str:
    b = records.replay["bundle"]
    return (
        f"contract `{b['contract_version']}`, snapshot `{b['snapshot_id']}`, features `{b['feature_spec_version']}`, "
        f"model `{b['model_version']}`, policy `{b['policy_version']}`, `T_warn = {b['T_warn']}`, blocking disabled"
    )


def frozen_note() -> str:
    return (
        "All data is fictional. Monitored requests are `validation_product_like` drafts, plus copies of legitimate first-contact "
        "validation drafts in the shifted windows. No frozen test row is read, replayed, scored, or summarized; the one recorded "
        "test result is quoted as recorded where it serves as a reference."
    )


# ---------------------------------------------------------------- MONITORING


def monitoring(records: Records) -> str:
    replay, ref, alerts = records.replay, records.reference, records.alerts
    ref_block = replay["blocks"]["reference"]
    cur_block = replay["blocks"]["current"]
    rs, cs = ref_block["summary"], cur_block["summary"]
    from med_api.service import LOG_FIELDS

    lines = [
        "# Phase 8 — Monitoring",
        "",
        f"Served bundle: {bundle_line(records)}. Monitor record `{replay['monitor_version']}`.",
        "",
        f"This is a monitoring **simulation**. The replay drives the real scoring API in process ({replay['environment']['transport']}), "
        "reduces every window to counts, histograms, and percentiles, and drops the individual responses. There is no production "
        "traffic. The thresholds are conventions fixed in `med_monitor.version`, and none has been validated against a real deployment. "
        "The indicator share-shift rule was added after a first look at validation windows showed that PSI alone barely moves when a rare state "
        "(about 2% of train rows) grows to about 13%; the rest were set beforehand. " + frozen_note(),
        "",
        "Every table is generated by `python -m med_monitor report` from the stored records in "
        f"`{ARTIFACT_DIR}/`. Nothing is typed by hand.",
        "",
        "## Metrics, references, rules, and minimum samples",
        "",
        table(
            ["Metric", "Where the number comes from", "Reference", "Rule", "Minimum sample"],
            [
                ["Requests, statuses, failure categories and messages", "Response body (the log carries the category, not the message)", "Reference windows", f"Unable-to-assess rate above the reference: one-sided exact test, alpha {RATE_ALPHA}", f"{MIN_REQUESTS_OPERATIONAL} requests"],
                ["Scoring latency p50, p95, p99", "Client-side timing of each call (server `duration_ms` is also in the log)", "Reference windows and the recorded AC05 measurement", f"p95 above {version.LATENCY_TARGET_MS:.0f} ms or above {version.LATENCY_RELATIVE_FACTOR:g} times the reference p95; timing-dependent", f"{MIN_REQUESTS_OPERATIONAL} requests"],
                ["Recipients per email, flagged recipients", "Response body (the log carries both counts)", "Reference windows", "Reported; no rule", "n/a"],
                ["Warning rate", "Decision (the log carries it)", "Reference windows", f"Two-sided exact test, alpha {RATE_ALPHA}", f"{count(MIN_EMAILS_DECISION_RATE)} emails on each side"],
                ["Block count", "Decision", "Must be 0", "Any block is critical", "none"],
                ["Served versions", "Log fields and `GET /ready`", "The frozen policy file", "Any other version is critical", "none"],
                ["Limited relationship history (first contact or cold start), limited text", "Evidence limitations in the response", "Reference windows", f"Rate above the reference: one-sided exact test, alpha {RATE_ALPHA}", f"{MIN_EMAILS_SCORE_BAND} assessed emails"],
                ["Emails from a sender with no earlier mail", "Feature rows (`sender_history_available` = 0)", "Reference windows", "Same test", f"{MIN_EMAILS_SCORE_BAND} assessed emails"],
                ["Email risk score distribution; scores near `T_warn`", "Email risk score in the response", "Reference windows", f"Emails in [T_warn - {NEAR_BAND}, T_warn): one-sided exact test; margin to the highest allowed score reported", f"{MIN_EMAILS_SCORE_BAND} assessed emails"],
                ["Input drift", "Model-input feature rows against the train reference", "Train only", f"PSI alert {PSI_ALERT}, watch {PSI_WATCH}; indicators also alert at a share shift of {SHARE_SHIFT_ALERT:g}; an alert needs {MIN_EXCESS_ROWS} excess rows", f"{MIN_ROWS_INPUT_DRIFT} recipient rows and {MIN_EMAILS_INPUT_DRIFT} emails"],
                ["Confirmed performance change", "Reviewed labels only", f"The recorded frozen test pass and the reference windows", "Recall intervals do not overlap", f"{MIN_REVIEWED_POSITIVES} confirmed misdirected emails on each side"],
            ],
        ),
        "",
        "Input drift, decision-rate change, and confirmed performance change are three separate findings. A window can show any one without the others; see [the drift replay](DRIFT_REPLAY.md).",
        "",
        "## What the structured log carries, and what it does not",
        "",
        "The API writes one JSON line per assessment with only these fields: "
        + ", ".join(f"`{name}`" for name in LOG_FIELDS)
        + ". Failure messages, evidence limitations, scores, and feature values are not in it. The replay driver reads them from the "
        "response body instead. A deployed monitor would need the log allow-list widened to carry, for example, a bucketed "
        "email-risk band, a near-cutoff flag, counts of recipients with limited history and limited text, and a failure-message code. "
        "Each of those is an integer or an enum, not an address, name, subject, or body. **That is a privacy decision. It is proposed "
        "here and not implemented:** no log field was added, and no score, address, or text is stored anywhere new. The stored "
        "records hold aggregates, plus the simulated review queue (draft id, decision, coarse stratum).",
        "",
        "## Reference periods",
        "",
        f"- **Input reference: `{ref['subset']}` only.** {count(ref['rows'])} recipient rows from {count(ref['drafts'])} emails in "
        f"`{ref['source']['file']}` (SHA-256 `{ref['source']['sha256'][:16]}…`, checked against the artifact manifest before it is read). "
        "Bin edges and counts come from these rows alone. Train is enriched to 10% misdirected mail, so its recipient mix is not the "
        "product-like mix; some features sit in the watch band on ordinary traffic (see the reference block below).",
        f"- **Operating reference: windows {', '.join(str(w) for w in REFERENCE_WINDOWS)}** of the replay, {count(ref_block['summary']['requests'])} consecutive "
        f"`validation_product_like` emails sent {window_of(records, REFERENCE_WINDOWS[0])['first_sent_at'][:10]} to "
        f"{window_of(records, REFERENCE_WINDOWS[-1])['last_sent_at'][:10]}. This subset chose the cutoff, so the reference warning rate is "
        "not independent evidence about the policy.",
        f"- **Latency, second reference:** the recorded AC05 measurement ({count(ref['latency_reference']['measured_calls'])} calls, client p50 "
        f"{ms(ref['latency_reference']['client_p50_ms'])} ms, p95 {ms(ref['latency_reference']['client_p95_ms'])} ms, p99 "
        f"{ms(ref['latency_reference']['client_p99_ms'])} ms; target {ref['latency_reference']['target_p95_ms']:.0f} ms), read as recorded and never rewritten.",
        "",
        "## Reference-period counts",
        "",
        _summary_table(rs, ref_block),
        "",
        "## Statuses and failure categories",
        "",
        _status_section(records),
        "",
        "## Windows",
        "",
        f"Windows are consecutive blocks of {records.plan['window_emails']} emails. Windows {', '.join(str(w) for w in REFERENCE_WINDOWS)} are the reference. "
        "Window 5 is an unshifted control. Windows 6 to 8 replace a growing share of routine drafts with copies of legitimate first-contact "
        "drafts; see the plan in [the drift replay](DRIFT_REPLAY.md#what-was-replayed).",
        "",
        _window_matrix(records),
        "",
        "## Status of the current windows against the reference",
        "",
        "Each cell is the check's status. A check below its minimum sample says so and reports no test. Latency depends on the machine "
        "and the moment, so it is timing-dependent and is not part of the deterministic alert set.",
        "",
        _check_matrix(alerts),
        "",
        "### Checks in detail, last window",
        "",
        _check_detail(alerts["windows"][CURRENT_WINDOWS[-1]]["checks"]),
        "",
        "## Email risk score distribution",
        "",
        _score_table(records),
        "",
        f"The near band is [T_warn - {NEAR_BAND}, T_warn). The highest legitimate validation email scored "
        f"{ref['policy_reference']['highest_legitimate_validation_email_risk']:.5f} against `T_warn` {records.policy['T_warn']:.6f}, a margin of "
        f"{ref['policy_reference']['T_warn'] - ref['policy_reference']['highest_legitimate_validation_email_risk']:.2e}; the band is about twice that margin. "
        "Scores are risk scores, not probabilities.",
        "",
        "## Input drift",
        "",
        _drift_summary(records),
        "",
        _reference_block_drift(records),
        "",
        _structural_table(records),
        "",
        "## Decision-rate change",
        "",
        _decision_table(records),
        "",
        "## Failure probes",
        "",
        f"{spell(len(records.replay['probes']['before'])).capitalize()} deliberately bad requests are sent before and after the replay and are not counted as traffic. A probe passes when the "
        "service returns unable to assess with no decision and no score. The messages are the ones the service sent.",
        "",
        _probe_table(records),
        "",
        "## Limits of this monitor",
        "",
        "- The reference operating period and the current windows are all validation mail from a synthetic generator. The rules were "
        "not tested against a real incident.",
        f"- Warnings are rare ({ratio(rs['warnings'], rs['assessed'])} in the reference), so a warning-rate statement needs "
        f"{count(MIN_EMAILS_DECISION_RATE)} emails on each side. Per-window statements are not made; blocks of four windows are compared.",
        "- Most validation mail comes from one sender "
        + _sender_sentence(records)
        + ", so windows are not independent draws of senders.",
        f"- {spell(len(CUMULATIVE_FEATURES)).capitalize()} lifetime-count features leave the train range because time passes, not because behavior changed. The monitor reports "
        "them as structural and cannot tell when that extrapolation starts to matter.",
        "- Confirmed performance needs reviewed labels. None exist for this traffic today; see [the feedback review](FEEDBACK_REVIEW.md).",
        "- Nothing here shows that detection improved. The monitor watches the served policy; it does not change it.",
        "",
    ]
    return "\n".join(lines)


def _sender_sentence(records: Records) -> str:
    pop = records.plan.get("traffic_population")
    if not pop:
        return "(sender concentration not recorded)"
    return f"({count(pop['largest_sender_emails'])} of {count(pop['emails'])} emails, {100 * pop['largest_sender_share']:.1f}%, from one of {pop['senders']} senders)"


def _summary_table(summary: dict, block: dict) -> str:
    flags = summary["email_flags_from_feature_rows"]
    rows = [
        ["Requests", count(summary["requests"]), "all requests in the block"],
        ["Assessed", ratio(summary["assessed"], summary["requests"]), "requests"],
        ["Unable to assess", ratio(summary["unable_to_assess"], summary["requests"]), "requests"],
        ["Warned", ratio(summary["warnings"], summary["assessed"]), "assessed emails"],
        ["Allowed", ratio(summary["decisions"]["allow"], summary["assessed"]), "assessed emails"],
        ["Blocked (must be 0)", count(summary["blocks"]), "assessed emails"],
        ["Flagged recipients", count(summary["flagged_recipients"]), f"of {count(summary['recipients'])} recipients"],
        ["Emails with limited relationship history", ratio(summary["emails_with_limited_relationship_history"], summary["assessed"]), "assessed emails"],
        ["Emails with limited text", ratio(summary["emails_with_limited_text"], summary["assessed"]), "assessed emails"],
        ["Emails from a sender with no earlier mail", ratio(flags.get("cold_start_sender", 0), summary["assessed"]), "assessed emails (feature rows)"],
        [f"Emails scoring in the near band", ratio(summary["near_band_emails"], summary["assessed"]), "assessed emails"],
        ["Highest allowed email risk score", number(summary["highest_allowed_email_risk"], 6), f"margin to T_warn {sci(summary['margin_to_cutoff'])}"],
        ["Client latency p50 / p95 / p99 (ms)", f"{ms(summary['client_latency_ms']['p50'])} / {ms(summary['client_latency_ms']['p95'])} / {ms(summary['client_latency_ms']['p99'])}", f"{count(summary['client_latency_ms']['n'])} calls"],
        ["Recipients per email", ", ".join(f"{k}: {count(v)}" for k, v in summary["recipients_per_email"].items()), "emails"],
        ["Served versions", "; ".join(f"`{show_version(k)}` ({count(v)})" for k, v in summary["versions"].items()), "responses"],
    ]
    return table(["Metric", "Count", "Denominator"], rows)


def _status_section(records: Records) -> str:
    rows, failures = [], []
    for item in records.replay["windows"]:
        summary = item["summary"]
        rows.append([f"W{item['window']}", count(summary["requests"]), count(summary["assessed"]), count(summary["unable_to_assess"]), count(summary["unexpected_responses"])])
        for failure in summary["failures"]:
            failures.append([f"W{item['window']}", failure["category"], failure["message"], count(failure["count"])])
    text = table(["Window", "Requests", "Assessed", "Unable to assess", "Unexpected responses"], rows)
    if failures:
        text += "\n\n" + table(["Window", "Category", "Message", "Count"], failures)
    else:
        text += (
            "\n\nNo request in the replayed traffic failed, so the categories `invalid_input` and `unavailable` and their messages are exercised only by the "
            "probes below. In real traffic a mistyped address is `unavailable` (\"A recipient is not in the context snapshot directory\"), "
            "and that message is what the monitor counts."
        )
    return text


def _window_matrix(records: Records) -> str:
    windows = records.replay["windows"]
    headers = ["Metric"] + [f"W{item['window']}" for item in windows]
    role = ["Role"] + [item["role"] for item in windows]
    share = ["Injected first-contact emails"] + [count(item["injected_emails"]) for item in windows]

    def row(name, fn):
        return [name] + [fn(item) for item in windows]

    rows = [
        role,
        share,
        row("Requests", lambda i: count(i["summary"]["requests"])),
        row("Unable to assess", lambda i: count(i["summary"]["unable_to_assess"])),
        row("Recipients", lambda i: count(i["summary"]["recipients"])),
        row("Warned", lambda i: count(i["summary"]["warnings"])),
        row("Blocked", lambda i: count(i["summary"]["blocks"])),
        row("Flagged recipients", lambda i: count(i["summary"]["flagged_recipients"])),
        row("Limited relationship history (emails)", lambda i: count(i["summary"]["emails_with_limited_relationship_history"])),
        row("Limited text (emails)", lambda i: count(i["summary"]["emails_with_limited_text"])),
        row("No-earlier-mail sender (emails)", lambda i: count(i["summary"]["email_flags_from_feature_rows"].get("cold_start_sender", 0))),
        row("Emails with a first-contact recipient", lambda i: count(i["slices"]["novel_recipient"]["yes"]["emails"])),
        row("Near-band emails", lambda i: count(i["summary"]["near_band_emails"])),
        row("Highest allowed score", lambda i: number(i["summary"]["highest_allowed_email_risk"], 5)),
        row("Client p95 latency (ms)", lambda i: ms(i["summary"]["client_latency_ms"]["p95"])),
        row("Recipient rows", lambda i: count(i["rows"])),
    ]
    return table(headers, rows)


def _check_matrix(alerts: dict) -> str:
    windows = list(CURRENT_WINDOWS)
    headers = ["Check"] + [f"W{w}" for w in windows] + ["Current block"]
    ids = [item["id"] for item in alerts["windows"][windows[0]]["checks"]]
    block_ids = {item["id"] for item in alerts["block"]["checks"]}
    rows = []
    for check_id in ids:
        cells = [f"`{check_id}`"]
        for w in windows:
            cells.append(label(find(alerts["windows"][w]["checks"], check_id)["status"]))
        cells.append(label(find(alerts["block"]["checks"], check_id)["status"]) if check_id in block_ids else "")
        rows.append(cells)
    rows.append(["`confirmed_performance_change`"] + ["" for _ in windows] + [label(find(alerts["block"]["checks"], "confirmed_performance_change")["status"])])
    return table(headers, rows)


def _check_detail(checks: list[dict]) -> str:
    return table(["Check", "Family", "Status", "Statement"], [[f"`{c['id']}`", c["family"], label(c["status"]), c["statement"]] for c in checks])


def _score_table(records: Records) -> str:
    windows = records.replay["windows"]
    bins = [name for name, _, _ in score_bins(records.replay["bundle"]["T_warn"])]
    rows = [[name] + [count(item["summary"]["score_histogram"][name]) for item in windows] for name in bins]
    rows.append(["Assessed emails"] + [count(item["summary"]["assessed"]) for item in windows])
    return table(["Email risk score"] + [f"W{item['window']}" for item in windows], rows)


def _drift_summary(records: Records) -> str:
    rows = []
    for item in records.replay["windows"]:
        drift = item["input_drift"]
        rows.append([f"W{item['window']}", count(drift["rows"]), count(drift["emails"]), label(drift["status"]), ", ".join(f"`{n}`" for n in drift["alert"]) or "none", str(len(drift["watch"])), str(len(drift["structural"]))])
    return "\n".join(
        [
            f"Each window is compared with the train reference. Recipient-level features count recipient rows; the {spell(len(DRAFT_LEVEL_FEATURES))} draft-level features count emails. "
            f"An alert needs PSI of at least {PSI_ALERT}, or (for a 0/1 indicator) a share shift of at least {SHARE_SHIFT_ALERT:g} from the train share, and at least "
            f"{MIN_EXCESS_ROWS} rows in excess of the reference expectation. A watch starts at PSI {PSI_WATCH} or a share shift of {SHARE_SHIFT_WATCH:g}. Below "
            f"{MIN_ROWS_INPUT_DRIFT} rows or {MIN_EMAILS_INPUT_DRIFT} emails no statement is made.",
            "",
            table(["Window", "Rows", "Emails", "Input-drift finding", "Features in the alert band", "Features in watch", "Structural"], rows),
        ]
    )


def _reference_block_drift(records: Records) -> str:
    drift = records.replay["blocks"]["reference"]["input_drift"]
    watch = [item for item in drift["features"] if item["status"] in (WATCH, ALERT)]
    lines = [
        "### The reference windows against train",
        "",
        f"The four reference windows pooled ({count(drift['rows'])} rows, {count(drift['emails'])} emails) put {len(drift['alert'])} features in the alert band and "
        f"{len(drift['watch'])} in the watch band against train. That offset exists on ordinary mail because train is enriched: read a current window's "
        "watch list against this one, and read an alert as new only for features not already here.",
        "",
    ]
    if watch:
        lines.append(
            table(
                ["Feature", "Unit", "PSI", "Train mean", "Reference-window mean", "Status"],
                [[f"`{i['feature']}`", i["unit"], number(i["psi"], 3), number(i["mean_train"], 4), number(i["mean_window"], 4), label(i["status"])] for i in watch],
            )
        )
    return "\n".join(lines)


def _structural_table(records: Records) -> str:
    rows = []
    ref = records.replay["blocks"]["reference"]["input_drift"]
    cur = records.replay["blocks"]["current"]["input_drift"]
    by_ref = {i["feature"]: i for i in ref["features"]}
    by_cur = {i["feature"]: i for i in cur["features"]}
    for name in records.reference["cumulative_features"]:
        rows.append([f"`{name}`", number(by_ref[name]["train_max"], 1), ratio(by_ref[name]["rows_above_train_max"], by_ref[name]["n"], 1), ratio(by_cur[name]["rows_above_train_max"], by_cur[name]["n"], 1)])
    return "\n".join(
        [
            "### Structural features",
            "",
            "These lifetime counts and spans grow with calendar time, so mail after the training period is above the train maximum by construction. "
            "They are counted, not scored, and never alert. The share is the honest finding: the model scores inputs it was not fit on, from the first "
            "validation day, and this monitor cannot say when that starts to matter. Fixing it means monitoring rates or windowed counts, or a rolling refit, "
            "which are model changes outside this phase.",
            "",
            table(["Feature", "Train maximum", "Rows above it, reference windows", "Rows above it, current windows"], rows),
        ]
    )


def _decision_table(records: Records) -> str:
    alerts = records.alerts
    rows = []
    for w in CURRENT_WINDOWS:
        f = find(alerts["windows"][w]["checks"], "decision_rate_change")["finding"]
        rows.append([f"W{w}", ratio(f["current"]["k"], f["current"]["n"]), label(f["status"]), sci(f["p_value"])])
    block = find(alerts["block"]["checks"], "decision_rate_change")["finding"]
    rows.append(["Current windows, pooled", ratio(block["current"]["k"], block["current"]["n"]), label(block["status"]), sci(block["p_value"])])
    ref = block["reference"]
    doubling = experiment.warning_rate_table(ref["k"] / ref["n"])[0]["emails_per_arm_if_independent"]
    return "\n".join(
        [
            f"Reference: {ratio(ref['k'], ref['n'])} emails warned. A statement needs {count(MIN_EMAILS_DECISION_RATE)} emails on each side, "
            f"so single windows of {records.plan['window_emails']} emails make none; the pooled block does. Two-sided exact test, alpha {RATE_ALPHA}.",
            "",
            table(["Compared", "Warned", "Finding", "p-value"], rows),
            "",
            f"With {count(ref['k'])} warnings in the reference, \"no change detected\" means the sample cannot tell, not that the rate is unchanged: detecting a doubling of "
            f"this rate with 80% power needs about {count(doubling)} emails on each side if emails were independent.",
        ]
    )


def _probe_table(records: Records) -> str:
    rows = []
    for when in ("before", "after"):
        for item in records.replay["probes"][when]:
            rows.append([when, item["probe"].replace("_", " "), item["http_status"], item["category"], item["message"], "yes" if item["no_decision_and_no_score"] else "NO"])
    return table(["When", "Probe", "HTTP", "Category", "Message", "No decision, no score"], rows)


# ---------------------------------------------------------------- DRIFT REPLAY


def drift_replay(records: Records) -> str:
    replay, plan, alerts = records.replay, records.plan, records.alerts
    last = CURRENT_WINDOWS[-1]
    first_alert = alerts["timeline"]
    drift_last = window_of(records, last)["input_drift"]
    drift_ref = replay["blocks"]["reference"]["input_drift"]
    new_features = [n for n in drift_last["alert"] if n not in drift_ref["alert"]]
    lines = [
        "# Phase 8 — Drift replay",
        "",
        f"Served bundle: {bundle_line(records)}. This document replays one shift, follows the alert to an investigation, and ends with a proposed experiment. "
        "The experiment is a written proposal. Nothing in the served model, the policy, or `T_warn` changes. " + frozen_note(),
        "",
        "## What was replayed",
        "",
        f"The scenario is a **new partner or collaborator wave**: legitimate first contacts (planned introductions to a new colleague or a new external partner) "
        f"replace a growing share of ordinary routine mail. It is built from the validation data, so no data was generated and no `med_data` rule changed. "
        f"The traffic is `{plan['traffic_subset']}` in send-time order, cut into {len(plan['windows'])} windows of {plan['window_emails']} emails. "
        f"The shifted emails are copies of the {plan['shift']['pool_drafts']} legitimate first-contact validation drafts (variants "
        + ", ".join(f"`{v}`" for v in plan["shift"]["pool_variants"])
        + f") drawn with seed {plan['seed']}; each replaces a `{plan['shift']['replaced_scenario']}` draft at a seeded position. "
        "Scenario and variant fields build the simulated traffic. They are never sent to the API and never used as monitored inputs.",
        "",
        table(
            ["Window", "Role", "Sent (base traffic)", "Injected first-contact emails", "Share of window"],
            [[w["window"], w["role"], f"{w['first_sent_at'][:10]} to {w['last_sent_at'][:10]}", count(w["injected_emails"]), f"{100 * w['injected_share']:.0f}%"] for w in plan["windows"]],
        ),
        "",
        f"The plan checksum is `{plan['checksum_sha256'][:16]}…`. The schedule (`SHIFT_SCHEDULE` in `med_monitor.version`) was set so that the last window crosses "
        "the alert rules. That makes this a demonstration of the path from alert to investigation, **not a measurement of how sensitive the monitor is**. "
        "How it behaves when nothing is shifted is the other half of the evidence: see the first row of the timeline below.",
        "",
        "## Timeline",
        "",
        _timeline(records, first_alert),
        "",
        "## Three findings, kept apart",
        "",
        "These are separate questions with separate evidence. One alert does not imply the others.",
        "",
        _three_findings(records),
        "",
        "## Investigation",
        "",
        _investigation(records, drift_last, drift_ref, new_features),
        "",
        "## Proposed targeted experiment (not run)",
        "",
        _targeted_experiment(records),
        "",
        "## Reproduce",
        "",
        "```bash",
        "python -m med_monitor build-reference",
        "python -m med_monitor replay",
        "python -m med_monitor feedback",
        "python -m med_monitor bundle-checks",
        "python -m med_monitor report",
        "```",
        "",
        "`replay` runs the plan through the API in process (`--api URL` uses a running service). It refuses to start unless the service reports the frozen bundle. "
        "Scores and decisions are deterministic; only latency changes between runs.",
        "",
    ]
    return "\n".join(lines)


def _timeline(records: Records, timeline: list[dict]) -> str:
    alerts = records.alerts
    unshifted = [w for w in CURRENT_WINDOWS if not records.plan["windows"][w - 1]["injected_emails"]]
    quiet = [w for w in unshifted if not [c for c in alerts["windows"][w]["alerts"]]]
    ref_alerts = [w for w in REFERENCE_WINDOWS if records.replay["windows"][w - 1]["input_drift"]["alert"]]
    lines = [
        f"- **No shift.** The unshifted control (window {', '.join(str(w) for w in unshifted)}) raised "
        f"{'no alert' if len(quiet) == len(unshifted) else 'alerts: ' + ', '.join(str(w) for w in unshifted if w not in quiet)}. "
        f"{len(ref_alerts)} of the {len(REFERENCE_WINDOWS)} reference windows put a feature in the input-drift alert band. The first-window alerts below are what the shift adds.",
    ]
    if not timeline:
        lines.append("- No alert fired in any shifted window.")
    for item in timeline:
        w = item["first_alert_window"]
        check = find(alerts["windows"][w]["checks"], item["check"])
        lines.append(f"- **Window {w}: `{item['check']}`** first alerts. {check['statement']}")
    return "\n".join(lines)


def _three_findings(records: Records) -> str:
    alerts = records.alerts
    last = CURRENT_WINDOWS[-1]
    drift = find(alerts["windows"][last]["checks"], "input_drift")
    block_drift = find(alerts["block"]["checks"], "input_drift")
    decision = find(alerts["block"]["checks"], "decision_rate_change")
    window_decision = find(alerts["windows"][last]["checks"], "decision_rate_change")
    performance = find(alerts["block"]["checks"], "confirmed_performance_change")
    rows = [
        ["**Input drift** (model inputs against train)", f"window {last}", label(drift["status"]), drift["statement"]],
        ["**Input drift**", "current windows pooled", label(block_drift["status"]), block_drift["statement"]],
        ["**Decision-rate change** (share warned)", f"window {last}", label(window_decision["status"]), window_decision["statement"]],
        ["**Decision-rate change**", "current windows pooled", label(decision["status"]), decision["statement"]],
        ["**Confirmed performance change** (reviewed labels)", "current against reference", label(performance["status"]), performance["statement"]],
    ]
    return table(["Finding", "Scope", "Status", "Statement"], rows)


def _investigation(records: Records, drift_last: dict, drift_ref: dict, new_features: list[str]) -> str:
    replay, alerts, plan = records.replay, records.alerts, records.plan
    last = CURRENT_WINDOWS[-1]
    control = CURRENT_WINDOWS[0]
    w_last, w_control = window_of(records, last), window_of(records, control)
    ref_sum = replay["blocks"]["reference"]["summary"]
    s_last = w_last["summary"]
    by_feature = {i["feature"]: i for i in drift_last["features"]}
    moved = [by_feature[n] for n in drift_last["alert"]]
    checks = alerts["windows"][last]["checks"]
    near = find(checks, "near_cutoff_scores")
    hist = find(checks, "limited_relationship_history_rate")
    slices_last, slices_control = w_last["slices"]["novel_recipient"], w_control["slices"]["novel_recipient"]
    first_window = alerts["timeline"][0]["first_alert_window"] if alerts["timeline"] else None
    first_input = next((item["first_alert_window"] for item in alerts["timeline"] if item["check"] == "input_drift"), None)
    steps = []

    if new_features and len(new_features) == len(drift_last["alert"]):
        novelty = "None of them was in the alert band on the pooled reference windows."
    elif new_features:
        novelty = f"{len(new_features)} of them were not in the alert band on the pooled reference windows."
    else:
        novelty = "All of them were already in the alert band on the pooled reference windows."
    earlier = ""
    if first_input and first_input < last:
        earlier_window = window_of(records, first_input)["input_drift"]
        names = earlier_window["alert"]
        unshifted_watch = {
            name
            for item in replay["windows"]
            if not item["injected_emails"]
            for name in item["input_drift"]["watch"]
        }
        also_watch = len(names) == 1 and names[0] in unshifted_watch
        earlier = (
            f" The input-drift check first alerted in window {first_input}, on {plural(len(names), 'feature')} ({', '.join(f'`{n}`' for n in names)})"
            + (
                f"; that feature also sits in the watch band on windows with no injected emails, so a one-feature alert on it is low confidence, and the first-contact signature below appears only in window {last}."
                if also_watch
                else f"; the first-contact signature below appears in window {last}."
            )
        )
    steps.append(
        "### 1. What alerted\n\n"
        f"The earliest alert of any kind is in window {first_window}. In window {last}, {plural(len(drift_last['alert']), 'model input')} "
        f"{'is' if len(drift_last['alert']) == 1 else 'are'} in the alert band against train: "
        + (", ".join(f"`{n}`" for n in drift_last["alert"]) or "none")
        + f". {novelty}{earlier}\n\n"
        f"- Near-cutoff scores: {near['statement']}\n"
        f"- Limited relationship history: {hist['statement']}"
    )
    if moved:
        steps.append(
            "### 2. Which inputs moved, and what they have in common\n\n"
            + table(
                ["Feature", "Unit", "Train mean", "Window mean", "Share shift", "PSI", "Status"],
                [[f"`{i['feature']}`", i["unit"], number(i["mean_train"], 4), number(i["mean_window"], 4), number(i.get("share_shift"), 4) if i.get("share_shift") is not None else "", number(i["psi"], 3), label(i["status"])] for i in moved],
            )
            + "\n\nThese inputs describe the same fact from different sides: the sender has no earlier mail with the recipient "
            "(`recipient_novel_to_sender`, `pair_recency_observed`, `co_focus_history_available`), so there is no earlier text to compare with "
            "(`content_similarity_observed`). That is the signature of first contacts. Novelty is not a label: the shift says who is being addressed, not "
            "whether anyone is mistaken."
        )
    steps.append(
        "### 3. Where in the traffic\n\n"
        + table(
            ["Slice", f"Window {control} (control), emails", f"Window {last}, emails", f"Window {last}, warned", f"Window {last}, near band", f"Window {last}, limited history"],
            [
                ["Has a first-contact recipient", count(slices_control["yes"]["emails"]), count(slices_last["yes"]["emails"]), count(slices_last["yes"]["warnings"]), count(slices_last["yes"]["near_band"]), count(slices_last["yes"]["limited_relationship_history"])],
                ["No first-contact recipient", count(slices_control["no"]["emails"]), count(slices_last["no"]["emails"]), count(slices_last["no"]["warnings"]), count(slices_last["no"]["near_band"]), count(slices_last["no"]["limited_relationship_history"])],
            ],
        )
        + f"\n\nReplay ground truth, which a real investigation would not have: {count(plan['windows'][last - 1]['injected_emails'])} of the {count(plan['window_emails'])} emails in window {last} were injected first contacts."
    )
    yes_near, no_near = slices_last["yes"]["near_band"], slices_last["no"]["near_band"]
    warned_text = (
        f"There were no warnings in window {last}."
        if s_last["warnings"] == 0
        else f"Warnings in window {last}: {count(s_last['warnings'])} of {count(s_last['assessed'])}, {count(slices_last['yes']['warnings'])} of them in the first-contact slice."
    )
    steps.append(
        "### 4. What happened to the scores\n\n"
        f"Emails in the near band in window {last}: {count(s_last['near_band_emails'])}, of which {count(yes_near)} have a first-contact recipient and {count(no_near)} do not, "
        f"against {count(ref_sum['near_band_emails'])} of {count(ref_sum['assessed'])} in the reference windows. The highest allowed score in window {last} is "
        f"{number(s_last['highest_allowed_email_risk'], 6)} (margin to `T_warn` {sci(s_last['margin_to_cutoff'])}); the reference windows' highest is "
        f"{number(ref_sum['highest_allowed_email_risk'], 6)} (margin {sci(ref_sum['margin_to_cutoff'])}). {warned_text} "
        f"The {count(s_last['near_band_emails'])} near-band emails are {count(s_last['near_band_distinct_drafts'])} distinct drafts, because the replay repeats "
        f"pool drafts ({count(s_last['distinct_drafts'])} distinct drafts among {count(s_last['requests'])} emails in this window). Nothing about a draft or the model changed: the margin narrows because "
        "these drafts are now a larger share of traffic, and because the pool also draws legitimate first contacts from `validation_diagnostic`, which the reference windows do not contain."
    )
    steps.append(_review_step(records))
    steps.append(_verdict(records, drift_last, near))
    return "\n\n".join(steps)


def _review_step(records: Records) -> str:
    feedback, last = records.feedback, CURRENT_WINDOWS[-1]
    horizon = int(feedback["efficacy"]["comparison_horizon_days"])
    items = [i for i in feedback["queue_items"] if i["window"] == last and i["delay_days"] <= horizon]
    rows = []
    for name in sorted({i["stratum"] for i in items}):
        chosen = [i for i in items if i["stratum"] == name]
        rows.append([f"`{name}`", count(len(chosen)), count(sum(i["misdirected"] for i in chosen)), count(sum(not i["misdirected"] for i in chosen))])
    text = (
        "### 5. What reviewed labels say (simulated reviewer)\n\n"
        f"Queued emails from window {last} whose simulated label came back within {days(horizon)}. The labels are the dataset's stipulations returned by a "
        "simulated reviewer; [the feedback review](FEEDBACK_REVIEW.md) lists the assumptions. They are not real reviews.\n\n"
    )
    text += table(["Review stratum", "Returned", "Confirmed misdirected", "Confirmed all intended"], rows) if rows else "No queued email returned in this window."
    return text


def _verdict(records: Records, drift_last: dict, near: dict) -> str:
    alerts, feedback = records.alerts, records.feedback
    last = CURRENT_WINDOWS[-1]
    decision = find(alerts["block"]["checks"], "decision_rate_change")
    block_drift = find(alerts["block"]["checks"], "input_drift")
    performance = find(alerts["block"]["checks"], "confirmed_performance_change")
    horizon = int(feedback["efficacy"]["comparison_horizon_days"])
    current = feedback["efficacy"]["by_horizon"][str(horizon)]["current"]
    warned = current["warned"]
    top = [i for i in feedback["queue_items"] if i["window"] == last and i["delay_days"] <= horizon and i["stratum"] == "allowed_score_at_least_0.9"]
    return (
        "### 6. What is and is not established\n\n"
        f"- **Established:** the model inputs moved toward first contacts (window {last} input drift: {label(drift_last['status'])}); more emails now score in the band just below the cutoff "
        f"(near-band check: {label(near['status'])}). Pooling all four current windows dilutes a shift that ramps up late: the pooled input-drift finding is {label(block_drift['status'])}, "
        "which is why the per-window finding is the one to read.\n"
        f"- **Pooled decision rate:** {label(decision['status'])}. {decision['statement']} That is a statement about too few warnings to see a change, not proof that none occurred.\n"
        f"- **Not established:** any change in detection or in false warnings. Confirmed performance change: {label(performance['status'])}. {performance['statement']} "
        f"Warned emails reviewed in windows {CURRENT_WINDOWS[0]} to {last} within {days(horizon)}: {ratio(warned['reviewed'], warned['population'], 0)}, of which {count(warned['confirmed_all_intended'])} were confirmed all intended. "
        "That counts confirmed false interventions among reviewed warnings only; it is not a false-warning rate.\n"
        + (f"- **What the simulated review adds:** {count(len(top))} allowed emails from window {last} scoring at least 0.9 were reviewed, and {count(sum(not i['misdirected'] for i in top))} were confirmed all intended. "
           "The extra mass near the cutoff is legitimate first-contact mail. That is a finding about this replay's pool, not a guarantee.\n" if top else "")
        + "- **The risk this points at:** legitimate first contacts already score just below the cutoff. A wave of them pushes more legitimate mail into that margin. "
        "Nothing here shows a false warning, and nothing here shows the margin is safe.\n"
        "- **Not addressed:** mistaken first contacts (S11) are missed by the served policy on every validation and test subset. A first-contact wave does not change that, "
        "and the monitor cannot see it without reviewed labels."
    )


def _targeted_experiment(records: Records) -> str:
    design = experiment.design(records.reference)
    policy_version = records.replay["bundle"]["policy_version"]
    guardrail = design["false_interventions"]
    plan = records.plan
    return "\n".join(
        [
            "**Question.** Under a first-contact wave, how often does a *legitimate* first contact score at or above `T_warn`, and how much mass sits in the near band?",
            "",
            "**Why this and not a model change.** The replay shows the inputs and the margin moving. It cannot say whether the score tail crosses `T_warn`, because the shift "
            f"is built from only {plan['shift']['pool_drafts']} distinct legitimate first-contact drafts. Changing the cutoff, the model, or the features on this evidence would be tuning on the replay.",
            "",
            "**Design (shadow mode, log only, no user sees a warning).**",
            "",
            f"1. Score first-contact traffic for the affected senders with the frozen `{policy_version}`, in shadow, for a fixed window.",
            "2. Review every shadow warning, every near-band email, and a seeded sample of the rest, using the stratified queue in [the feedback review](FEEDBACK_REVIEW.md#review-workflow).",
            "3. Estimate two quantities among reviewed legitimate first contacts: the share at or above `T_warn` (a false-warning rate) and the share in the near band, each with an exact interval.",
            f"4. Size: a zero-count bound at the budget of {guardrail['budget_per_1000']:g} per 1,000 needs about {count(guardrail['legitimate_emails_per_arm_for_zero_count_bound'])} reviewed legitimate first contacts "
            "if emails were independent, and more when they come from few senders.",
            "",
            "**Decision rule, written before the run.**",
            "",
            f"- Zero false warnings and a near-band share no higher than the reference: keep `{policy_version}`, record the tail, and keep watching the near-band check.",
            "- Any confirmed false warning, or a near-band share above the reference: do not move `T_warn`. Open a new policy version through the offline path (new evidence on a new frozen dataset version, "
            "separate calibration and selection portions, one test pass) and gate it as in [the runbook](RUNBOOK.md#promotion-gates).",
            "",
            "**Side question the same data answers.** The recorded threshold-free separation of mistaken first contacts from legitimate ones (AUC 0.88 on `validation_diagnostic`, 10 against 20 rows) "
            "says the score can rank them. The shadow run measures whether that ranking holds at the volume and mix of a real wave. It does not, by itself, justify a lower cutoff.",
            "",
        ]
    )


# ---------------------------------------------------------------- FEEDBACK


def feedback_review(records: Records) -> str:
    fb, alerts = records.feedback, records.alerts
    real = fb["real_reviewed_labels"]
    api, dataset = real["api_feedback"], real["dataset_reviewer_feedback"]
    horizon = str(fb["efficacy"]["comparison_horizon_days"])
    lines = [
        "# Phase 8 — Reviewed feedback",
        "",
        f"Served bundle: {bundle_line(records)}. **A click is not a label.** Feedback reaches a label only through a reviewer, and it never retrains, recalibrates, "
        "or moves the cutoff. " + frozen_note(),
        "",
        "## Sources, and how much reviewed evidence exists today",
        "",
        table(
            ["Source", "Content", "Reviewed", "Usable as a label for the monitored traffic"],
            [
                ["API feedback file (`POST /feedback`)", f"{plural(api['lines'], 'line')}, {plural(api['distinct_assessments'], 'assessment')}, {plural(api['distinct_contacts'], 'contact')}; labels {_pairs(api['labels'])}; {api['first_received']} to {api['last_received']}", "0 (clicks)", "No. No line names a draft, and the log and feedback line carry no assessment time."],
                ["Dataset `reviewer_feedback.csv`", f"{plural(dataset['rows_about_non_frozen_drafts'], 'row')} about non-frozen drafts: {_pairs(dataset['by_subset_and_status'])}", f"{count(dataset['accepted'])} accepted", f"No. {plural(dataset['about_validation_drafts'], 'row')} concern a validation draft."],
            ],
        ),
        "",
        f"**Reviewed labels on the monitored traffic: {count(real['reviewed_labels_on_monitored_traffic'])}.** Label delay for the click feedback is not computable: {api['label_delay'].split(': ', 1)[1]}. "
        "Everything below that reports coverage, delay, or efficacy uses a **simulated reviewer**, not real reviews.",
        "",
        "## The rule",
        "",
        f"{fb['effective_label_rule']} In this run {count(fb['labels_changed_by_feedback'])} labels were changed by feedback. The SHA-256 of `policy.json` and `model.joblib` was recorded "
        f"before and after the feedback stage and {'did not change' if fb['policy_and_model_unchanged'] else 'CHANGED'}.",
        "",
        "## Why feedback on warned emails alone is biased",
        "",
        _bias_section(records, horizon),
        "",
        "## Review workflow",
        "",
        _workflow(records),
        "",
        "## Simulated reviewer",
        "",
        f"- Label source: {fb['simulation']['label_source']}.",
        f"- {fb['simulation']['assumptions']}",
        f"- Delay: {fb['simulation']['delay']['distribution']}; median {fb['simulation']['delay']['median_days']:.1f} days, 90th percentile {fb['simulation']['delay']['p90_days']:.1f} days, "
        f"longest {fb['simulation']['delay']['max_days']:.1f} days over {count(fb['simulation']['delay']['queued'])} queued emails.",
        "- Because every queued email is eventually answered and the reviewer is always right, this shows the arithmetic of a review workflow and its delay. It says nothing about real reviewer accuracy, return rates, or workload.",
        "",
        "## Label coverage and delay",
        "",
        _coverage_table(fb),
        "",
        "## Efficacy from returned labels",
        "",
        f"Recall and false interventions are computed from returned labels only, with the counts shown. Recall is confirmed warned mistakes over all mistakes, where the mistakes among allowed emails are estimated from the sampled strata; the interval adds the per-stratum "
        f"{int(100 * version.REVIEW_CONFIDENCE)}% Clopper-Pearson intervals, so it is conservative and not simultaneous. Emails not yet reviewed are unknown, not zero. Reference means windows {', '.join(str(w) for w in REFERENCE_WINDOWS)}; current means windows {', '.join(str(w) for w in CURRENT_WINDOWS)}.",
        "",
        _efficacy_tables(fb),
        "",
        "## Confirmed performance change",
        "",
        _performance_section(records, horizon),
        "",
        "## What this does not show",
        "",
        "- It does not show how well real reviewers would label, how many would respond, or how fast.",
        "- It does not show that detection improved. It shows how to measure detection when labels arrive, and why a click stream cannot do it.",
        f"- The reference recall for a future comparison is the one recorded frozen test pass: {ratio(records.reference['recorded_test_pass']['warned_mistakes'], records.reference['recorded_test_pass']['misdirected'])} misdirected emails warned (exact interval "
        f"{number(records.reference['recorded_test_pass']['recall_interval_exact'][0], 3)} to {number(records.reference['recorded_test_pass']['recall_interval_exact'][1], 3)}, if emails were independent). "
        "The validation figure is not independent of the cutoff.",
        "",
    ]
    return "\n".join(lines)


def _pairs(values: dict) -> str:
    return ", ".join(f"{key} {value}" for key, value in values.items()) or "none"


def _bias_section(records: Records, horizon: str) -> str:
    fb = records.feedback
    current = fb["efficacy"]["by_horizon"][horizon]["current"]
    reference = fb["efficacy"]["by_horizon"][horizon]["reference"]
    recall = reference["recall"]
    warned = reference["warned"]
    return "\n".join(
        [
            "People are shown a warning only when the policy warns. If only those emails are reviewed:",
            "",
            "- **Precision is estimable.** Every reviewed email was warned, so the share confirmed misdirected is a precision-side figure.",
            "- **Recall is not.** A mistake the policy allowed is never shown to anyone, so it never reaches a reviewer, and the denominator silently drops every miss. "
            f"On the reference windows, {count(warned['confirmed_misdirected'])} of {count(warned['reviewed'])} reviewed warned emails were misdirected, so recall computed from warned emails alone is "
            f"{number(reference['warned_only_view']['recall_if_only_warned_emails_were_reviewed'], 2)}. With a sample of allowed emails added, the estimate is "
            f"{number(recall['estimate'], 3)} (interval {number(recall['low'], 3)} to {number(recall['high'], 3)}) at {days(int(horizon))}.",
            "- **What senders do with a warning changes what can be reviewed.** A sender who removes a flagged recipient sends a corrected email, and the mistake that was caught never appears in sent mail. "
            "Warnings a sender ignores are the ones that stay in the record. Reviewing only mail sent after a warning is another biased sample.",
            "- **Clicks are not verified.** A click says what one person thought at one moment. It needs a review before it is a label.",
            "",
            "The fix is a sampled review of *allowed* emails with known inclusion probabilities, so misses can be observed and weighted back to the population.",
        ]
    )


def _workflow(records: Records) -> str:
    fb = records.feedback
    replay = records.replay
    population = replay["review_queue"]["population"]

    def total(windows: list[int], name: str) -> int:
        return sum(population[str(w)].get(name, 0) for w in windows)

    rows = []
    for item in fb["simulation"]["queue_policy"]:
        name = item["name"]
        rule = "every warned email" if name == "warned" else f"allowed, email risk score from {item['score_from']:g} to below {item['score_below']:g}"
        queued = sum(1 for q in fb["queue_items"] if q["stratum"] == name)
        rows.append([f"`{name}`", rule, f"{item['inclusion_probability']:g}", count(total(list(REFERENCE_WINDOWS), name)), count(total(list(CURRENT_WINDOWS), name)), count(queued)])
    return "\n".join(
        [
            "1. A click or a warning creates no label. It can put an email in a review queue.",
            "2. The queue is built from the decision and the score band: all warned emails, and a seeded sample of allowed emails with a higher inclusion probability where the score is higher.",
            "3. A reviewer answers whether each recipient was intended. Only an accepted review can change a recipient's effective label.",
            "4. Efficacy is computed from returned answers, with each stratum weighted by its population, and always shown with its counts.",
            "",
            f"Strata are fixed in `med_monitor.version` before any answer is read. The score bands are generic round numbers. The recorded validation misses all score above "
            f"{ALLOWED_STRATA[0][1]:g} (see the [error analysis](../phase_5/ERROR_ANALYSIS.md)), so the top band holds them here; a real system cannot assume that. "
            "The lowest band is sampled at a low rate so that mistakes the score does not see can still be observed.",
            "",
            table(["Stratum", "Rule", "Inclusion probability", "Emails, reference", "Emails, current", "Queued (all windows)"], rows),
        ]
    )


def _coverage_table(fb: dict) -> str:
    rows = []
    for horizon in fb["efficacy"]["horizons_days"]:
        for role in ("reference", "current"):
            side = fb["efficacy"]["by_horizon"][str(horizon)][role]
            rows.append(
                [
                    days(horizon),
                    role,
                    count(side["queued"]),
                    count(side["returned"]),
                    ratio(side["returned"], side["assessed_emails"], 2),
                    ratio(side["warned"]["reviewed"], side["warned"]["population"], 0),
                ]
            )
    return table(["Within", "Block", "Queued", "Returned", "Returned, of assessed emails", "Warned emails reviewed, of warned"], rows)


def _efficacy_tables(fb: dict) -> str:
    out = []
    for horizon in fb["efficacy"]["horizons_days"]:
        rows = []
        for role in ("reference", "current"):
            side = fb["efficacy"]["by_horizon"][str(horizon)][role]
            recall = side["recall"]
            confirmed = side["positives_confirmed"]
            fi = side["false_interventions"]
            rows.append(
                [
                    role,
                    ratio(side["warned"]["confirmed_misdirected"], side["warned"]["reviewed"], 0) + " misdirected",
                    f"{count(fi['confirmed'])} of {count(fi['of_reviewed_warned'])} reviewed warned",
                    count(confirmed),
                    _allowed_cell(side),
                    "not estimable" if recall["estimate"] is None else f"{number(recall['estimate'], 3)} ({number(recall['low'], 3)} to {number(recall['high'], 3)})"
                    + (" †" if confirmed < MIN_REVIEWED_POSITIVES and recall["estimate"] is not None else ""),
                ]
            )
        out.append(f"**Labels returned within {days(horizon)}**\n\n" + table(["Block", "Reviewed warned emails", "Confirmed false interventions", "Confirmed misdirected, all strata", "Reviewed allowed emails (mistakes / reviewed / population)", "Estimated recall (conservative interval)"], rows))
    out.append(
        f"† Fewer than {MIN_REVIEWED_POSITIVES} confirmed misdirected emails. That is arithmetic on a handful of cases, not a finding, and the performance check refuses to compare it."
    )
    return "\n\n".join(out)


def _allowed_cell(side: dict) -> str:
    parts = []
    for name, value in side["strata"].items():
        if name == "warned":
            continue
        parts.append(f"`{name.replace('allowed_score_', '')}`: {value['mistakes']} / {value['reviewed']} / {value['population']}")
    return "; ".join(parts)


def _performance_section(records: Records, horizon: str) -> str:
    performance = find(records.alerts["block"]["checks"], "confirmed_performance_change")["finding"]
    ref, cur = performance["reference"], performance["current"]
    fb_horizons = records.feedback["efficacy"]["horizons_days"]
    by_horizon = records.feedback["efficacy"]["by_horizon"][str(max(fb_horizons))]
    last_ref, last_cur = by_horizon["reference"]["positives_confirmed"], by_horizon["current"]["positives_confirmed"]
    return "\n".join(
        [
            f"A performance statement needs at least {MIN_REVIEWED_POSITIVES} confirmed misdirected emails in the reference and in the current block, and it is made only when the recall intervals do not overlap. "
            f"At {days(int(horizon))} the reference block has {count(ref['positives_confirmed'])} and the current block {count(cur['positives_confirmed'])}. "
        f"At {days(max(fb_horizons))} they hold {count(last_ref)} and {count(last_cur)}, so the confirmed mistakes are not spread evenly over the replayed period.",
            "",
            f"**Finding: {label(performance['status'])}.** {performance['statement']}",
            "",
            f"At a misdirection rate of {100 * EXPERIMENT_PREVALENCE:.1f}% a block of 2,000 emails holds about {round(2000 * EXPERIMENT_PREVALENCE)} mistakes, so {MIN_REVIEWED_POSITIVES} confirmed mistakes need roughly "
            f"{count(round(MIN_REVIEWED_POSITIVES / EXPERIMENT_PREVALENCE))} emails on each side with every mistake confirmed, and more when only a sample is reviewed. This is the reason input drift and decision-rate change are watched first and are reported separately: they arrive long before confirmed performance can.",
        ]
    )


# ------------------------------------------------------------ EXPERIMENT


def experiment_proposal(records: Records) -> str:
    design = experiment.design(records.reference)
    pop = records.plan.get("traffic_population") or {}
    validation = records.reference["policy_reference"]["validation"]

    def scaling(rows: list[dict]) -> str:
        return "; ".join(f"ICC {item['icc']:g}: {count(item['emails'])} emails, {count(item['senders'])} senders" for item in rows)

    lines = [
        "# Phase 8 — Sender-level A/B test proposal",
        "",
        "**This is a proposal. There is no online evidence.** No experiment has been run, no real user has seen a warning, and every number below is arithmetic on stated assumptions. "
        f"The served bundle is {bundle_line(records)}. Blocking stays disabled in every arm.",
        "",
        "## Question",
        "",
        "Does showing the frozen warning policy to senders lead to more confirmed detections of misdirected mail, at an acceptable cost in interruptions, "
        "than showing nothing (shadow scoring only)?",
        "",
        "## Design",
        "",
        "- **Arms.** Control: the policy scores every draft in shadow and no warning is shown. Treatment: the same policy, warnings shown. Both arms are scored, so every metric except user behavior is observable in both.",
        "- **Unit of randomization: the sender.** A sender's drafts share history, habits, and recipients, so randomizing emails would leak treatment across a sender's mail and understate variance. Analysis uses sender-level clustering.",
        f"- **Feasibility on this population.** The validation traffic has {count(pop.get('senders', 0))} senders and {100 * pop.get('largest_sender_share', 0):.1f}% of emails come from one of them, so a sender-level test cannot be run on it. "
        "A real test needs many senders with comparable volume.",
        "- **Exposure.** Fixed horizon; no interim looks at the primary metric.",
        "",
        "## Metrics",
        "",
        table(
            ["Role", "Metric", "Definition", "Baseline and its source"],
            [
                ["Primary", "Confirmed detections", "Warned emails a reviewer confirms are misdirected, over all confirmed misdirected emails (recall), from the stratified review", f"{number(design['detections'][0]['baseline_recall'], 2)}: {ratio(records.reference['recorded_test_pass']['warned_mistakes'], records.reference['recorded_test_pass']['misdirected'])}, the one recorded frozen test pass"],
                ["Guardrail", "Warning rate", "Emails warned over emails assessed", f"{ratio(validation['warnings'], validation['emails'])} on validation product-like, the subset that chose the cutoff"],
                ["Guardrail", "Confirmed false interventions", f"Reviewed warned emails confirmed all intended, per 1,000 legitimate emails; budget {design['false_interventions']['budget_per_1000']:g} per 1,000", f"{ratio(validation['false_interventions'], validation['legitimate'])} on validation and {ratio(records.reference['recorded_test_pass']['false_interventions'], records.reference['recorded_test_pass']['legitimate'])} on the recorded test pass; not confidence-supported (AC01 is insufficient evidence)"],
                ["Guardrail", "User corrections", "Share of warned emails in which the sender changes a flagged recipient before sending. **Not measurable today:** the UI records no correction, only an intended or unintended click", "none measured"],
                ["Guardrail", "Latency", f"Client p95 per arm, at least {count(design['latency']['requests_per_arm_minimum'])} requests per arm, below {design['latency']['p95_limit_ms']:.0f} ms", "the recorded AC05 measurement"],
                ["Guardrail", "Unable to assess", "Share of requests that return unable to assess, by category", ratio(records.replay["blocks"]["reference"]["summary"]["unable_to_assess"], records.replay["blocks"]["reference"]["summary"]["requests"]) + " in the reference windows"],
                ["Safety", "Blocks", "Must be 0", count(records.replay["blocks"]["reference"]["summary"]["blocks"]) + " in the reference windows"],
            ],
        ),
        "",
        "## Sample size",
        "",
        f"Alpha {design['alpha']}, power {design['power']}, assumed misdirection rate {100 * design['assumed_prevalence']:.1f}% (a simulation assumption), "
        f"{design['assumed_emails_per_sender']} emails per sender over the test period. Clustering inflates emails by the design effect 1 + (m - 1) * ICC; ICC is unknown, so three values are shown.",
        "",
        "### Confirmed detections",
        "",
        table(
            ["Baseline recall", "Target recall", "Confirmed misdirected emails per arm", "Emails per arm if independent", "With sender clustering (per arm)"],
            [[number(r["baseline_recall"], 2), number(r["target_recall"], 2), count(r["confirmed_misdirected_per_arm"]), count(r["emails_per_arm_if_independent"]), scaling(r["with_sender_clustering"])] for r in design["detections"]],
        ),
        "",
        "### Warning rate (detect a doubling)",
        "",
        table(
            ["Baseline rate", "Target rate", "Emails per arm if independent", "With sender clustering (per arm)"],
            [[number(r["baseline_rate"], 4), number(r["target_rate"], 4), count(r["emails_per_arm_if_independent"]), scaling(r["with_sender_clustering"])] for r in design["warning_rate"]],
        ),
        "",
        "### False-intervention guardrail",
        "",
        f"To show with {100 * (1 - design['alpha']):.0f}% confidence that the false-intervention rate is no higher than {design['false_interventions']['budget_per_1000']:g} per 1,000 after observing zero, "
        f"an arm needs about {count(design['false_interventions']['legitimate_emails_per_arm_for_zero_count_bound'])} reviewed legitimate emails if they were independent. "
        f"With sender clustering: {scaling(design['false_interventions']['with_sender_clustering'])}.",
        "",
        "## Stopping rules",
        "",
        "- **Stop an arm at once** on any block decision, any response that carries a decision or score with a failure, a served version that is not the frozen bundle, or an unable-to-assess alert (see [monitoring](MONITORING.md)).",
        f"- **Stop the treatment for harm** when confirmed false interventions reach {design['false_interventions']['stop_for_harm_confirmed_false_interventions']} within "
        f"{count(design['false_interventions']['stop_for_harm_at_legitimate_emails'])} reviewed legitimate emails: at the budget rate that count has a probability of 1% or less. It is a safety stop, not a success criterion.",
        "- **Do not stop early for success.** The primary metric is read once, at the planned horizon, on labels returned by then. A late-returning label is counted only if the protocol fixes a cutoff date before the test starts.",
        "- **Do not extend** a test whose primary metric is inconclusive without a new protocol; extending by peeking inflates the error rate.",
        "",
        "## Analysis and reading",
        "",
        "- Cluster-robust intervals at the sender level. Report counts and denominators for every metric.",
        "- Reviewed labels come from the stratified queue with known inclusion probabilities, so misses are weighted back. Feedback clicks are not labels.",
        "- A positive result would say the warning surfaced mistakes at a given interruption cost for the senders tested. It would not say the model improved.",
        "",
        "## Preconditions not met today",
        "",
        "- Enough senders, and a way to randomize them at request time.",
        "- Correction logging in the UI, and a reviewer workflow with real reviewers.",
        "- Shadow scoring that records the decision without showing it.",
        "- A privacy decision on the log fields the monitor needs (see [monitoring](MONITORING.md#what-the-structured-log-carries-and-what-it-does-not)).",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- RUNBOOK


def runbook(records: Records) -> str:
    policy, bundles, alerts = records.policy, records.bundles, records.alerts
    checksums = policy["checksums"]
    cases = bundles["cases"]
    thresholds = table(
        ["Signal", "Rule", "Severity"],
        [
            ["Any block decision", "count above 0", "critical"],
            ["Any response that breaks a contract invariant", "for example a failure body with a decision or score", "critical"],
            ["A served version other than the frozen bundle", "any", "critical"],
            ["Unexpected (non-contract) responses", "any", "high"],
            ["Unable-to-assess rate above the reference", f"one-sided exact test, alpha {RATE_ALPHA}, at least {MIN_REQUESTS_OPERATIONAL} requests", "high"],
            ["Input drift", f"PSI alert {PSI_ALERT}; indicator share shift {SHARE_SHIFT_ALERT:g}", "high"],
            ["Emails in the near band", f"one-sided exact test, alpha {RATE_ALPHA}, at least {MIN_EMAILS_SCORE_BAND} assessed emails", "medium"],
            ["Client p95 latency", f"above {version.LATENCY_TARGET_MS:.0f} ms or {version.LATENCY_RELATIVE_FACTOR:g} times the reference p95", "medium"],
        ],
    )
    lines = [
        "# Phase 8 — Runbook: rollout, rollback, and incident triage",
        "",
        f"Served bundle: {bundle_line(records)}. This runbook describes how a frozen, versioned bundle would be shadowed, canaried, rolled back, and investigated. "
        "It is a document, not deployment tooling: no container, CI, or live switch between two bundles exists yet, and those belong to the next phase. " + frozen_note(),
        "",
        "## The unit of change is a frozen bundle",
        "",
        "A bundle is the dataset snapshot, the feature artifact, the model, and the policy, each with a version and a checksum, loaded together and never edited in place.",
        "",
        table(
            ["Part", "Version", "Checksum (SHA-256)"],
            [
                ["Model", f"`{policy['model_version']}` (`{policy['model_run_name']}`)", f"`{checksums['model.joblib']}`"],
                ["Feature artifact manifest", f"`{policy['feature_spec_version']}`", f"`{checksums['artifact_manifest.json']}`"],
                ["Policy", f"`{policy['policy_version']}`, `T_warn = {policy['T_warn']}`, blocking disabled", "recorded inside the policy file"],
                ["Snapshot", f"`{records.replay['bundle']['snapshot_id']}`", "verified against the dataset manifest at startup"],
            ],
        ),
        "",
        "A change to any part is a new bundle with a new version, evaluated offline first. The cutoff is never moved inside a version.",
        "",
        "## What the service does today with a bad bundle",
        "",
        "Each case builds the real API on altered copies of the frozen files in a temporary directory, then calls `/health`, `/ready`, and `/assess` "
        "(`python -m med_monitor bundle-checks`). The frozen files are never edited.",
        "",
        table(
            ["Case", "Change", "`/health`", "`/ready`", "`/assess`", "Decision, score", "Outcome"],
            [
                [f"`{c['case']}`", c["change"], c["health_http"], c["ready_http"], f"{c['assess_http']} {c['assess_category'] or c['assess_status']}", "none, none" if c["decision"] is None and not c["email_risk_score_reported"] else f"{c['decision']}, score reported", c["outcome"]]
                for c in cases
            ],
        ),
        "",
        f"{'Every altered bundle was refused' if bundles['all_altered_bundles_refused'] else 'NOT every altered bundle was refused'}: the process stays up, `/ready` reports 503 with the reason, and `/assess` returns `unavailable` with no decision and no score, "
        "so a broken bundle can never produce an allow. The refusal reasons the service reported:",
        "",
        "\n".join(f"- `{c['case']}`: {c['ready_reason']}" for c in cases if c["ready_reason"]),
        "",
        f"**Not covered:** {bundles['not_covered']} The previous bundle is refused by design (case `previous_bundle`), so today's code cannot roll back to it. "
        "A rollback needs the previous code and the previous bundle as a pair, which is what packaging is for.",
        "",
        "## Rollout",
        "",
        "A new bundle moves through these stages. Each stage has an exit rule that is written before the stage starts.",
        "",
        "1. **Offline gates (before any traffic).** The bundle passes the offline checks in the promotion gates below, on a validation set separate from the one that chose its cutoff, with one test pass on a new frozen dataset version.",
        "2. **Shadow.** The candidate scores the same requests as the served bundle and its decisions are logged, not shown. Compare decisions, the warning rate, the near-band share, and latency against the served bundle on identical traffic. Exit: agreement on the rules in [monitoring](MONITORING.md), no critical or high alert, and reviewed samples from the stratified queue.",
        "3. **Canary.** A small set of senders, chosen by a seeded draw, sees the candidate's warnings. Everyone else keeps the served bundle. Exit: the guardrails in [the experiment proposal](EXPERIMENT_PROPOSAL.md) hold for the planned horizon.",
        "4. **Full rollout.** Only after the canary exits cleanly and a named reviewer signs the promotion record. The previous bundle stays deployable until the next bundle has run clean for a stated period.",
        "",
        "## Rollback",
        "",
        "**Roll back when** any critical alert fires, a guardrail is breached, a high-impact incident (below) is confirmed, or `/ready` no longer reports the expected versions.",
        "",
        "1. Stop routing new senders to the candidate. Keep the record of what it did.",
        "2. Restore the previous bundle: the previous code revision and the previous frozen bundle files together, pointed to by the service's path settings "
        "(`MED_API_POLICY`, `MED_API_MODEL`, `MED_API_FEATURES`, `MED_API_DATA`). Do not edit files in place.",
        "3. Confirm with `GET /ready` (versions and `T_warn` must match the previous policy file) and re-run the failure probes.",
        "4. Confirm the monitor: served versions match, no block decisions, unable-to-assess back to the reference.",
        "5. Write the incident record: trigger, time, bundle versions, counts, decision, and the offline check that must pass before the candidate returns.",
        "",
        "**Capabilities this needs that do not exist yet:** a way to hold two bundles loadable at once, a per-sender routing switch, a shadow mode that records without showing, and a rehearsed rollback. "
        "None was built in this phase.",
        "",
        "## Alert reference",
        "",
        thresholds,
        "",
        "## Incident triage",
        "",
        "Warnings are advisory and blocking is disabled, so the worst automatic outcome is an unnecessary interruption or a missed mistake. A failure is `unable_to_assess`, never an allow. "
        "In every incident: preserve the evidence first, change nothing in the frozen bundle, and never move `T_warn` to make a symptom go away.",
        "",
        _incident_false_positive(records),
        "",
        _incident_false_negatives(records),
        "",
        _incident_outage(records),
        "",
        "## Promotion gates",
        "",
        "No model, feature, or policy change is promoted on monitoring evidence alone. Every promotion needs all of:",
        "",
        "1. **A new version.** New model, feature, or policy versions get new artifact directories; nothing is edited in place.",
        "2. **An offline evaluation on data that did not choose the change.** Validation for selection, a separate portion for any calibration, and one pass on a new frozen test set. Report counts, denominators, and intervals.",
        "3. **The interruption budget.** False interventions per 1,000 legitimate emails against the budget, with the independence caveat recorded (AC01 is insufficient evidence today).",
        "4. **Parity.** The batch path and the single-draft path give identical decisions on every selection draft.",
        "5. **Failure behavior.** Every bundle mismatch case above is still refused, and no failure returns a decision or score.",
        "6. **Review.** A second person reads the evidence and signs the promotion record.",
        "7. **Staged exposure.** Shadow, then canary, with the exit rules above.",
        "",
        "A reviewed label, a click, or a monitoring alert can start this process. None of them can finish it.",
        "",
    ]
    return "\n".join(lines)


def _incident_false_positive(records: Records) -> str:
    return "\n".join(
        [
            "### A high-impact false positive",
            "",
            "**Signal.** A sender or a support contact reports a warning that stopped important, legitimate mail. Or the warning rate, the flagged-recipient count, or a confirmed false intervention rises.",
            "",
            "1. **Contain.** Do not change the cutoff. If a shadow mode exists, move the affected senders to it. Otherwise record the affected window and the count.",
            "2. **Capture** the request id, the bundle versions, and the reason codes the service returned. Do not copy the body, subject, or addresses out of the affected mailbox.",
            "3. **Classify.** Was the warning correct on the evidence (a real mistake the sender then confirmed), or a false intervention? A reviewer, not a click, decides.",
            "4. **Locate.** Compare the email risk score with `T_warn` (the margin is small: the highest legitimate validation score sits 2.3e-3 below it). Check the input-drift and near-band findings for the same period, and whether the recipient is a first contact.",
            "5. **Offline check.** Reproduce the assessment from the request. If it reproduces, the cause is the policy on this input; go to the promotion gates. If it does not, treat it as a service defect and check parity.",
            "6. **Decide** with a reviewer. A confirmed false intervention counts against the budget. It is a reason to open a new policy version, not to move the cutoff in place.",
            "",
        ]
    )


def _incident_false_negatives(records: Records) -> str:
    return "\n".join(
        [
            "### Rising false negatives",
            "",
            "**Signal.** Reviewed samples of allowed emails show more mistakes than before, or a reported mistake was allowed. Remember the policy already misses lookalike replacements (S01), familiar-recipient topic mistakes (S04), and mistaken first contacts (S11) by design of its cutoff.",
            "",
            "1. **Confirm with labels.** Only the stratified review of allowed emails can show a rise. Check the number of confirmed misdirected emails first: a performance statement needs "
            f"{MIN_REVIEWED_POSITIVES} on each side, and until then the honest report is that there is not enough evidence.",
            "2. **Separate the cause.** Input drift (did the mix change, for example toward first contacts), decision-rate change (did the warning rate move), and confirmed performance change are three findings; report each.",
            "3. **Slice.** Which scenario-like slice do the misses fall in: added recipient, lookalike, topic mismatch, first contact? Compare with the recorded per-scenario results.",
            "4. **Do not lower the cutoff.** Any lower cutoff produced false warnings on validation. A lower cutoff is a new policy version with its own budget evidence.",
            "5. **Offline check and review** as in the promotion gates. Record the finding even if nothing is promoted.",
            "",
        ]
    )


def _incident_outage(records: Records) -> str:
    return "\n".join(
        [
            "### A scoring outage",
            "",
            "**Signal.** `/ready` returns 503, the unable-to-assess rate alert fires, latency exceeds the target, or the timeout message appears.",
            "",
            "1. **Read the category.** `unavailable` with \"The scoring bundle is not loaded\" means startup failed; `/ready` gives the reason (a version or checksum mismatch, a missing file). "
            "\"Scoring timed out\" means the two-second scoring timeout fired. \"A recipient is not in the context snapshot directory\" is one address, not an outage.",
            "2. **Nothing fails open.** A failure returns unable to assess with no decision and no score. Clients must show it as unable to assess, never as allow.",
            "3. **Restore.** Fix the bundle path or files, or restore the previous bundle as in the rollback steps, and re-check `/ready`.",
            "4. **Verify.** Re-run the failure probes and a small replay; confirm the served versions and that unable-to-assess is back to the reference.",
            "5. **Follow up.** Record the duration and the count of requests that were unable to assess. Those requests were not assessed, and that burden belongs in the incident record.",
            "",
        ]
    )


BUILDERS = {
    "MONITORING.md": monitoring,
    "DRIFT_REPLAY.md": drift_replay,
    "FEEDBACK_REVIEW.md": feedback_review,
    "EXPERIMENT_PROPOSAL.md": experiment_proposal,
    "RUNBOOK.md": runbook,
}


def render_all(records: Records) -> dict[str, str]:
    return {name: builder(records) for name, builder in BUILDERS.items()}


def write_documents(docs_dir: Path = version.DOCS_DIR, artifact_dir: Path = ARTIFACT_DIR) -> list[Path]:
    records = load_records(artifact_dir)
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in render_all(records).items():
        path = docs_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
