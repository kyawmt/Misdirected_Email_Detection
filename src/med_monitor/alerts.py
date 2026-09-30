"""Alert checks over stored window summaries.

Everything here is a pure function of the stored replay record and the
reference, so a report can be regenerated without scoring anything. Each check
returns a status, the counts behind it, and the rule that produced it. A check
below its minimum sample size says `insufficient_sample` and reports no test.

The three findings the brief separates are built here from separate inputs:
input drift from feature rows, decision-rate change from decisions, and
confirmed performance change from reviewed labels.
"""

from __future__ import annotations

from med_monitor.drift import (
    ALERT,
    INSUFFICIENT,
    OK,
    decision_rate_change,
    performance_change,
    rate_finding,
)
from med_monitor.version import (
    CURRENT_WINDOWS,
    LATENCY_RELATIVE_FACTOR,
    LATENCY_TARGET_MS,
    MIN_EMAILS_SCORE_BAND,
    MIN_REQUESTS_OPERATIONAL,
)

CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"


def expected_version_key(policy: dict) -> str:
    return "|".join(policy[name] for name in ("model_version", "feature_spec_version", "policy_version"))


def _check(check_id: str, family: str, severity: str, status: str, statement: str, **detail) -> dict:
    return {"id": check_id, "family": family, "severity": severity, "status": status, "statement": statement, **detail}


def _ok_or(status_bad: bool, bad: str = ALERT, good: str = OK) -> str:
    return bad if status_bad else good


def operational_checks(summary: dict, reference: dict, expected_key: str) -> list[dict]:
    """Checks on one window (or block) summary against the pooled reference-period summary."""
    checks = []
    blocks = summary["blocks"]
    checks.append(
        _check(
            "blocks",
            "operational",
            CRITICAL,
            _ok_or(blocks > 0),
            f"{blocks} block decisions in {summary['requests']} requests; blocking is disabled and the count must be 0.",
            counts={"blocks": blocks, "requests": summary["requests"]},
        )
    )
    problems = summary["invariant_problems"]
    checks.append(
        _check(
            "response_invariants",
            "operational",
            CRITICAL,
            _ok_or(bool(problems)),
            "No response broke a contract invariant." if not problems else "; ".join(f"{text} ({count})" for text, count in problems.items()),
            counts=dict(problems),
        )
    )
    # Only responses that name a bundle can show a different bundle. A failure with no provenance is an availability
    # signal, checked apart, and is not evidence that another bundle answered.
    wrong = {key: count for key, count in summary["versions"].items() if key != expected_key}
    named = sum(summary["versions"].values())
    checks.append(
        _check(
            "served_versions",
            "operational",
            CRITICAL,
            _ok_or(bool(wrong)),
            f"All {named} responses that name a bundle report {expected_key.replace('|', ', ')}." if not wrong else f"Responses from other bundles: {wrong}.",
            counts={"expected": expected_key, "other": wrong, "naming_a_bundle": named},
        )
    )
    unloaded = summary["failures_without_provenance"]
    checks.append(
        _check(
            "bundle_available",
            "operational",
            HIGH,
            _ok_or(unloaded > 0),
            "No failure came from a service without a loaded bundle." if not unloaded else f"{unloaded} of {summary['requests']} responses were failures with no version provenance: the service answered without a loaded bundle.",
            counts={"failures_without_provenance": unloaded, "requests": summary["requests"]},
        )
    )
    unexpected = summary["unexpected_responses"]
    checks.append(
        _check(
            "unexpected_responses",
            "operational",
            HIGH,
            _ok_or(unexpected > 0),
            f"{unexpected} responses were not a contract-shaped body.",
            counts={"unexpected": unexpected},
        )
    )
    ref_unable = {"k": reference["unable_to_assess"], "n": reference["requests"]}
    cur_unable = {"k": summary["unable_to_assess"], "n": summary["requests"]}
    finding = rate_finding("unable_to_assess_rate", ref_unable, cur_unable, alternative="greater", min_n=MIN_REQUESTS_OPERATIONAL)
    checks.append(
        _check(
            "unable_to_assess_rate",
            "operational",
            HIGH,
            finding["status"],
            _rate_statement("unable to assess", finding),
            finding=finding,
            categories=summary["failures"],
        )
    )
    p95 = summary["client_latency_ms"]["p95"]
    ref_p95 = reference["client_latency_ms"]["p95"]
    if summary["requests"] < MIN_REQUESTS_OPERATIONAL or p95 is None:
        checks.append(
            _check(
                "latency_p95",
                "operational",
                MEDIUM,
                INSUFFICIENT,
                f"No latency statement: {summary['requests']} requests, minimum {MIN_REQUESTS_OPERATIONAL}.",
                timing_dependent=True,
            )
        )
    else:
        relative = LATENCY_RELATIVE_FACTOR * ref_p95 if ref_p95 is not None else None
        over_target = p95 > LATENCY_TARGET_MS
        over_relative = relative is not None and p95 > relative
        checks.append(
            _check(
                "latency_p95",
                "operational",
                MEDIUM,
                _ok_or(over_target or over_relative),
                f"Client p95 {p95:.2f} ms against a {LATENCY_TARGET_MS:.0f} ms target and {LATENCY_RELATIVE_FACTOR:g} times the reference p95 "
                f"({ref_p95:.2f} ms).",
                timing_dependent=True,
                counts={"p95_ms": p95, "reference_p95_ms": ref_p95, "requests": summary["requests"]},
            )
        )
    assessed, ref_assessed = summary["assessed"], reference["assessed"]
    for check_id, key, label in (
        ("limited_relationship_history_rate", "emails_with_limited_relationship_history", "emails with a recipient that has limited relationship history"),
        ("limited_text_rate", "emails_with_limited_text", "emails with limited draft text"),
    ):
        finding = rate_finding(
            check_id,
            {"k": reference[key], "n": ref_assessed},
            {"k": summary[key], "n": assessed},
            alternative="greater",
            min_n=MIN_EMAILS_SCORE_BAND,
        )
        checks.append(_check(check_id, "operational", MEDIUM, finding["status"], _rate_statement(label, finding), finding=finding))
    flag = "cold_start_sender"
    finding = rate_finding(
        "cold_start_sender_rate",
        {"k": reference["email_flags_from_feature_rows"].get(flag, 0), "n": ref_assessed},
        {"k": summary["email_flags_from_feature_rows"].get(flag, 0), "n": assessed},
        alternative="greater",
        min_n=MIN_EMAILS_SCORE_BAND,
    )
    checks.append(
        _check(
            "cold_start_sender_rate",
            "operational",
            MEDIUM,
            finding["status"],
            _rate_statement("emails from a sender with no earlier mail (feature rows)", finding),
            finding=finding,
        )
    )
    near = rate_finding(
        "near_cutoff_scores",
        {"k": reference["near_band_emails"], "n": ref_assessed},
        {"k": summary["near_band_emails"], "n": assessed},
        alternative="greater",
        min_n=MIN_EMAILS_SCORE_BAND,
    )
    checks.append(
        _check(
            "near_cutoff_scores",
            "score_distribution",
            MEDIUM,
            near["status"],
            _rate_statement("emails scoring in the band just below the cutoff", near),
            finding=near,
            margin_to_cutoff=summary["margin_to_cutoff"],
            reference_margin_to_cutoff=reference["margin_to_cutoff"],
        )
    )
    return checks


def _rate_statement(label: str, finding: dict) -> str:
    ref, cur = finding["reference"], finding["current"]
    text = f"{cur['k']} of {cur['n']} {label} against {ref['k']} of {ref['n']} in the reference period"
    if finding["status"] == INSUFFICIENT:
        return f"No statement: {text}; minimum {finding['min_n']} on each side."
    return f"{text}; exact test p = {finding['p_value']:.3g} (alpha {finding['alpha']})."


def input_check(drift: dict, reference_block: dict) -> dict:
    """Input drift as its own finding. Features new relative to the reference block are named."""
    baseline = set(reference_block["alert"]) if reference_block["status"] != INSUFFICIENT else set()
    new = [name for name in drift["alert"] if name not in baseline]
    return _check(
        "input_drift",
        "input_drift",
        HIGH,
        drift["status"],
        drift["statement"],
        alert_features=drift["alert"],
        watch_features=drift["watch"],
        alert_features_not_in_reference_block=new,
        rows=drift["rows"],
    )


def evaluate(replay: dict, reference: dict, expected_key: str, review: dict | None = None) -> dict:
    """Checks for every current window and the current block, plus the three block-level findings.

    `review` is the stored `feedback_review.json`, when it exists; without it the
    performance finding reports that no reviewed labels were supplied.
    """
    windows = {item["window"]: item for item in replay["windows"]}
    ref_block = replay["blocks"]["reference"]
    cur_block = replay["blocks"]["current"]
    ref_summary = ref_block["summary"]
    out = {"windows": {}, "block": {}, "timeline": []}
    for number in CURRENT_WINDOWS:
        item = windows[number]
        checks = operational_checks(item["summary"], ref_summary, expected_key)
        checks.append(input_check(item["input_drift"], ref_block["input_drift"]))
        decision = decision_rate_change(
            {"k": ref_summary["warnings"], "n": ref_summary["assessed"]},
            {"k": item["summary"]["warnings"], "n": item["summary"]["assessed"]},
        )
        checks.append(_check("decision_rate_change", "decision_rate", HIGH, decision["status"], _rate_statement("emails warned", decision), finding=decision))
        out["windows"][number] = {"checks": checks, "alerts": [c["id"] for c in checks if c["status"] == ALERT]}
    block_checks = operational_checks(cur_block["summary"], ref_summary, expected_key)
    block_checks.append(input_check(cur_block["input_drift"], ref_block["input_drift"]))
    decision = decision_rate_change(
        {"k": ref_summary["warnings"], "n": ref_summary["assessed"]},
        {"k": cur_block["summary"]["warnings"], "n": cur_block["summary"]["assessed"]},
    )
    block_checks.append(_check("decision_rate_change", "decision_rate", HIGH, decision["status"], _rate_statement("emails warned", decision), finding=decision))
    performance = _performance(review)
    block_checks.append(_check("confirmed_performance_change", "performance", HIGH, performance["status"], performance["statement"], finding=performance))
    out["block"] = {"checks": block_checks, "alerts": [c["id"] for c in block_checks if c["status"] == ALERT]}
    first: dict[str, int] = {}
    for number in CURRENT_WINDOWS:
        for check_id in out["windows"][number]["alerts"]:
            first.setdefault(check_id, number)
    out["timeline"] = [{"check": check_id, "first_alert_window": number} for check_id, number in sorted(first.items(), key=lambda item: (item[1], item[0]))]
    return out


def _performance(review: dict | None) -> dict:
    if not review or "efficacy" not in review:
        return {
            "finding": "confirmed_performance_change",
            "status": INSUFFICIENT,
            "statement": "No performance statement: no reviewed-label record was supplied.",
        }
    horizon = review["efficacy"]["comparison_horizon_days"]
    sides = review["efficacy"]["by_horizon"][str(horizon)]
    return performance_change(sides["reference"], sides["current"])
