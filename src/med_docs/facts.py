"""Derive what the documents state from the stored records.

Every status is computed here by a rule over record fields, and each rule is
printed beside its result in `docs/RESULTS.md`. No number is typed by hand. The
acceptance criteria are the ones in `docs/phase_1/ACCEPTANCE_CRITERIA.md`; a
status is one of **met**, **not met**, or **insufficient evidence**.

AC01 to AC05 and AC07 follow the rules `med_policy.report` applies. AC06, AC08,
AC09, and AC10 had no stored status before Phase 10: their rules are defined
here, over the Phase 8 and Phase 9 records, and are as strict as the evidence
those criteria ask for.
"""

from __future__ import annotations

from med_docs import fmt
from med_docs.version import (
    DIAGNOSTIC_SUBSET,
    INDEPENDENCE_ESTABLISHED,
    KNOWN_MISSES,
    LEGITIMATE_NOVELTY_SCENARIOS,
    SELECTION_SUBSET,
    TEST_DIAGNOSTIC,
    TEST_PRODUCT,
)

MET, NOT_MET, INSUFFICIENT = "met", "not met", "insufficient evidence"


# ------------------------------------------------------------- operating points


def point(block: dict, subset: str) -> dict:
    """One subset at the frozen cutoff, from its stored policy aggregates."""
    policy = block["policy"]
    email, fi, coverage = policy["email"], policy["interventions"], policy["coverage"]
    emails = email["n"]
    interrupted = fi["warnings"] + fi["blocks"]
    low, high = email["recall_interval_exact"]["low"], email["recall_interval_exact"]["high"]
    scale = email["positives"] / emails * 1000
    return {
        "subset": subset,
        "cutoff": policy["cutoff"],
        "emails": emails,
        "misdirected": email["positives"],
        "legitimate": email["legitimate"],
        "warned_mistakes": email["true_positives"],
        "missed": email["false_negatives"],
        "recall": email["recall"],
        "recall_exact": (low, high),
        "recall_bootstrap": (email["recall_interval_bootstrap"]["low"], email["recall_interval_bootstrap"]["high"]),
        "false_warnings": fi["false_interventions"],
        "per_1000_legitimate": fi["per_1000_legitimate"],
        "false_upper_per_1000": fi["interval_per_1000_exact"]["high"],
        "budget_per_1000": fi["budget_per_1000"],
        "warnings": fi["warnings"],
        "blocks": fi["blocks"],
        "interrupted": interrupted,
        "assessed": coverage["assessed"],
        "coverage": coverage["fraction"],
        "unintended_recipients": policy["recipient"]["positives"],
        "flagged_unintended_recipients": policy["recipient"]["true_positives"],
        # Per 1,000 emails: the denominator is every email in the subset, not only the legitimate ones.
        "misdirected_per_1000": fmt.rate_1000(email["positives"], emails),
        "detections_per_1000": fmt.rate_1000(email["true_positives"], emails),
        "detections_per_1000_exact": (low * scale, high * scale),
        "missed_per_1000": fmt.rate_1000(email["false_negatives"], emails),
        "false_warnings_per_1000": fmt.rate_1000(fi["false_interventions"], emails),
        "interruptions_per_1000": fmt.rate_1000(interrupted, emails),
    }


def baseline(block: dict) -> dict:
    """Always-allow and the rules policy at the same selection rule, on one validation subset."""
    return {
        name: {
            "warned": block[name]["email"]["true_positives"],
            "positives": block[name]["email"]["positives"],
            "false_warnings": block[name]["interventions"]["false_interventions"],
            "legitimate": block[name]["interventions"]["legitimate_emails"],
        }
        for name in ("always_allow", "rules_same_budget")
    }


def scenario_cells(block: dict) -> dict[str, dict]:
    return {cell["slice"]: cell for cell in block["slices"]["email_by_scenario"]}


def reading(cell: dict | None) -> str:
    """How one scenario came out at the cutoff. Every scenario is read from its own counts."""
    if cell is None:
        return "not in this subset"
    parts = []
    if cell["misdirected"]:
        warned, total = cell["warned_misdirected"], cell["misdirected"]
        if warned == 0:
            parts.append("**missed**")
        elif warned == total:
            parts.append("caught")
        else:
            parts.append("partly caught")
    if cell["legitimate"]:
        parts.append("false warnings" if cell["warned_legitimate"] else "allowed")
    return "; ".join(parts)


def scenario_groups(test_cells: dict[str, dict]) -> tuple[list[str], list[str], list[str]]:
    """Scenarios whose mistakes were all warned, some warned, and none warned."""
    full, partial, never = [], [], []
    for scenario, cell in sorted(test_cells.items()):
        if not cell["misdirected"]:
            continue
        warned, total = cell["warned_misdirected"], cell["misdirected"]
        (full if warned == total else never if warned == 0 else partial).append(scenario)
    return full, partial, never


def ac02_phrase(test_cells: dict[str, dict]) -> str:
    """The AC02 status words Phase 5 prints, derived from scenario counts."""
    full, partial, never = scenario_groups(test_cells)
    words = []
    if full:
        words.append(f"met for {', '.join(full)}")
    if partial:
        words.append(f"partly met for {', '.join(partial)}")
    if never:
        words.append(f"not met for {', '.join(never)}")
    return "; ".join(words) if (partial or never) else "met"


# ------------------------------------------------------------------- fixtures


def _recipients(fixture: dict) -> list[dict]:
    return fixture["expected"].get("recipients") or []


def _assessed(fixture: dict) -> bool:
    return fixture["expected"].get("status") == "assessed"


def _codes(recipient: dict) -> list[str]:
    return [item["code"] for item in recipient["reason_codes"]]


def _limitation_codes(recipient: dict) -> list[str]:
    return [item["code"] for item in recipient["evidence_limitations"]]


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-12


# ----------------------------------------------------------------- acceptance


def acceptance(records: dict, points: dict, scenarios: dict) -> list[dict]:
    policy = records["policy"]
    t_warn = policy["T_warn"]
    test, selection = points[TEST_PRODUCT], points[SELECTION_SUBSET]
    deploy, monitor, latency = records["deploy"], records["monitor"], records["api_latency"]
    fixtures = deploy["fixtures"]
    budget = policy["budget"]["budget_per_1000"]
    out = []

    # AC01 ------------------------------------------------------------------
    if test["per_1000_legitimate"] > budget:
        ac01 = NOT_MET
    elif test["false_upper_per_1000"] <= budget and INDEPENDENCE_ESTABLISHED:
        ac01 = MET
    else:
        ac01 = INSUFFICIENT
    out.append(
        {
            "id": "AC01",
            "name": "Interruption budget",
            "headline": f"{fmt.of(test['false_warnings'], test['legitimate'])} legitimate emails warned ({fmt.f(test['per_1000_legitimate'], 2)} per 1,000); exact upper {fmt.f(test['false_upper_per_1000'], 2)} only if emails were independent",
            "status": ac01,
            "measured": (
                f"{fmt.of(test['false_warnings'], test['legitimate'])} legitimate `{TEST_PRODUCT}` emails warned "
                f"({fmt.f(test['per_1000_legitimate'], 2)} per 1,000; warnings {test['warnings']}, blocks {test['blocks']}, coverage {fmt.pct(test['coverage'])}). "
                f"The exact 95% upper bound, {fmt.f(test['false_upper_per_1000'], 2)} per 1,000, holds only if emails are independent, and independence is not established: "
                f"most test drafts come from one sender. On `{SELECTION_SUBSET}`: {fmt.of(selection['false_warnings'], selection['legitimate'])}, but that subset chose the cutoff."
            ),
            "rule": (
                f"not met if the point estimate on `{TEST_PRODUCT}` is above {fmt.f(budget, 0)} per 1,000; met only if the exact upper bound is within the budget and emails can be treated as independent; otherwise insufficient evidence. "
                "No record establishes independence, so a zero count is a descriptive pass on this corpus and not a confidence-supported claim."
            ),
            "evidence": [("Evaluation report", "phase_5/EVALUATION_REPORT.md"), ("Independence", "phase_5/UNCERTAINTY_AND_PREVALENCE.md#independence")],
        }
    )

    # AC02 ------------------------------------------------------------------
    test_cells = scenarios[TEST_PRODUCT]
    phrase = ac02_phrase(test_cells)
    base = baseline(records["validation"]["subsets"][SELECTION_SUBSET])
    # Phase 1 defines AC02 as recall maximized subject to AC01, with useful detections beyond always-allow
    # and the rules policy. The constraint is part of the criterion, so AC02 cannot be better supported than
    # AC01: utility alone gives insufficient evidence while AC01 is. The per-scenario reading Phase 5 printed
    # stays in the measured text.
    utility = (
        test["warned_mistakes"] > 0
        and test["recall_exact"][0] > 0
        and selection["warned_mistakes"] > base["always_allow"]["warned"]
        and selection["warned_mistakes"] > base["rules_same_budget"]["warned"]
    )
    if not utility or ac01 == NOT_MET:
        ac02 = NOT_MET
    elif ac01 == MET:
        ac02 = MET
    else:
        ac02 = INSUFFICIENT
    measured = (
        f"`{TEST_PRODUCT}`: {fmt.of(test['warned_mistakes'], test['misdirected'])} mistakes warned, recall {fmt.f(test['recall'])} {fmt.ci(*test['recall_exact'])} if emails were independent, with {test['false_warnings']} false warnings. "
        f"Always-allow warns on none. On `{SELECTION_SUBSET}` the rules policy at the same selection rule warned {base['rules_same_budget']['warned']} of {base['rules_same_budget']['positives']}, "
        f"the policy {fmt.of(selection['warned_mistakes'], selection['misdirected'])}. "
        f"Per scenario (the Phase 5 reading): {phrase}."
    )
    if ac02 == INSUFFICIENT:
        measured += " The detections and the baseline comparison are descriptive results on this corpus; the status is insufficient evidence because the budget they are held to (AC01) is."
    out.append(
        {
            "id": "AC02",
            "name": "Detection utility",
            "headline": f"{fmt.of(test['warned_mistakes'], test['misdirected'])} mistakes warned, recall {fmt.f(test['recall'])} {fmt.ci(*test['recall_exact'])}; no mistake warned in {', '.join(scenario_groups(test_cells)[2]) or 'no scenario'}",
            "status": ac02,
            "measured": measured,
            "rule": (
                "Phase 1 defines AC02 as recall maximized subject to AC01, with useful detections beyond always-allow and the rules policy at the same selection rule. "
                "Not met when the policy does not beat both baselines, warns on no mistake of `" + TEST_PRODUCT + "`, or AC01 is not met. "
                "Met only when the baselines are beaten and AC01 is met. Otherwise insufficient evidence: the baselines are beaten but the budget is held to AC01's standard, "
                "and AC01 is insufficient evidence, so the constraint is not shown to hold. "
                "No recall floor is set. The per-scenario reading is reported, not part of the status: a scenario is met when every mistake of it on `" + TEST_PRODUCT + "` was warned, partly met when some were, not met when none were."
            ),
            "evidence": [("Evaluation report", "phase_5/EVALUATION_REPORT.md"), ("Error analysis", "phase_5/ERROR_ANALYSIS.md")],
        }
    )

    # AC03 ------------------------------------------------------------------
    chosen_on = policy["selection"]["subset"]
    before = policy["created_at"] < records["test"]["top"]["evaluated_at"]
    same_policy = records["test"]["top"]["policy_sha256"] == records["policy_sha256"]
    ok = chosen_on == SELECTION_SUBSET and policy["test_subsets_used"] is False and before and same_policy
    out.append(
        {
            "id": "AC03",
            "name": "Threshold integrity",
            "headline": f"cutoff chosen on `{chosen_on}`; policy written before the one test pass",
            "status": MET if ok else NOT_MET,
            "measured": (
                f"`T_warn` was chosen on `{chosen_on}` only ({policy['selection']['chosen']['true_positives']} of {selection['misdirected']} mistakes, {policy['selection']['chosen']['false_interventions']} of {n_legit(selection)} legitimate emails). "
                f"`policy.json` was written {policy['created_at']}, before the one test pass ({records['test']['top']['evaluated_at']}); the policy SHA-256 stored with the test pass equals the file's."
            ),
            "rule": "met when the policy names the validation subset as its selection data, records that no test subset was used, was written before the test pass, and is the same file the test pass checksummed.",
            "evidence": [("Threshold policy", "phase_5/THRESHOLD_POLICY.md")],
        }
    )

    # AC04 ------------------------------------------------------------------
    blocks = sum(item["blocks"] for item in points.values())
    ok = policy["blocking_enabled"] is False and policy["T_block"] is None and blocks == 0 and records["test"]["top"]["blocking_enabled"] is False
    out.append(
        {
            "id": "AC04",
            "name": "Conservative blocking",
            "headline": f"blocking disabled; {blocks} blocks",
            "status": MET if ok else NOT_MET,
            "measured": f"Blocking is disabled (`T_block` is null). Blocks: {blocks} across the four evaluated subsets. The service refuses a policy that enables blocking (bundle check case `policy_enables_blocking`).",
            "rule": "met when the policy disables blocking, sets no `T_block`, and no evaluated subset recorded a block.",
            "evidence": [("Threshold policy", "phase_5/THRESHOLD_POLICY.md"), ("Runbook", "phase_8/RUNBOOK.md#what-the-service-does-today-with-a-bad-bundle")],
        }
    )

    # AC05 ------------------------------------------------------------------
    one = deploy["latency"]["ac05"]
    target = latency["target_p95_ms"]
    ok = (
        latency["ac05"] == "met"
        and latency["concurrency"] == 1
        and latency["client_p95_ms"] < target
        and list(latency["statuses"]) == ["assessed"]
        and one["result"] == "met"
        and one["concurrency"] == 1
        and one["client_p95_ms"] < target
        and one["failures"] == 0
    )
    probe = deploy["latency"]["concurrent_probe"]["client"]["p95_ms"]
    out.append(
        {
            "id": "AC05",
            "name": "Latency",
            "headline": f"client p95 {fmt.ms(latency['client_p95_ms'])} (Phase 6) and {fmt.ms(one['client_p95_ms'])} (Phase 9), one request in flight",
            "status": MET if ok else NOT_MET,
            "measured": (
                f"Client p95 {fmt.ms(latency['client_p95_ms'])} over {fmt.n(latency['measured_calls'])} calls (Phase 6, in process) and {fmt.ms(one['client_p95_ms'])} over {fmt.n(one['requests'])} requests "
                f"(Phase 9, container over loopback), one request in flight, against a {fmt.f(target, 0)} ms target; this machine only. "
                f"With {deploy['latency']['concurrent_probe']['clients']} clients at once the client p95 was {fmt.ms(probe)}, {'above' if probe > target else 'below'} the target; AC05 specifies one request in flight."
            ),
            "rule": "met when both records report one request in flight, no failures, every request assessed, and a client p95 below the target.",
            "evidence": [("Scoring flow", "phase_6/SCORING_FLOW.md#latency-ac05"), ("Warm latency", "phase_9/TEST_REPORT.md#warm-latency")],
        }
    )

    # AC06 ------------------------------------------------------------------
    assessed = {key: item for key, item in fixtures.items() if _assessed(item)}
    max_ok = [key for key, item in assessed.items() if _close(item["expected"]["email_risk_score"], max(r["risk_score"] for r in _recipients(item)))]
    flag_ok = [key for key, item in assessed.items() if all(r["flagged"] == (r["risk_score"] >= t_warn) for r in _recipients(item))]
    routine, dup = fixtures["routine_allow"], fixtures["duplicate_roles"]
    merged = _recipients(dup)[0]["roles"] == ["to", "cc"] and len(_recipients(dup)) == len(_recipients(routine))
    multi = fixtures["multi_recipient_warn"]
    multi_flagged = sum(1 for r in _recipients(multi) if r["flagged"])
    equality = fixtures["threshold_equality_warn"]
    mutations = {item["mutation"]: item["detected"] for item in deploy["mutation"]["mutations"]}
    cells = records["validation"]["subsets"][SELECTION_SUBSET]["slices"]["email_by_recipient_count"]
    breakdown = "; ".join(
        "{} recipients: {}".format(c["slice"], "{} of {} mistakes warned".format(c["warned_misdirected"], c["misdirected"]) if c["misdirected"] else "no mistakes in the subset")
        for c in cells
    )
    aggregation_mutations = ("mean_instead_of_maximum", "equality_allows")
    ok = (
        len(max_ok) == len(assessed)
        and len(flag_ok) == len(assessed)
        and merged
        and len(_recipients(multi)) >= 5
        and multi_flagged >= 2
        and multi["expected"]["decision"] == "warn"
        and equality["expected"]["decision"] == "warn"
        and _close(equality["expected"]["email_risk_score"], t_warn)
        and mutations.get("mean_instead_of_maximum") is True
        and mutations.get("equality_allows") is True
        and [cell["slice"] for cell in cells] == ["1", "2", "3-4", "5+"]
    )
    out.append(
        {
            "id": "AC06",
            "name": "Recipient completeness",
            "headline": f"{len(max_ok)} of {len(assessed)} assessed fixtures follow maximum aggregation; equality warns",
            "status": MET if ok else NOT_MET,
            "measured": (
                f"In {len(max_ok)} of {len(assessed)} recorded assessed fixtures the email risk equals the highest recipient risk, and in {len(flag_ok)} of {len(assessed)} the flagged recipients are exactly those at or above `T_warn`. "
                f"A repeated address is merged into one recipient with both roles ({len(_recipients(dup))} recipients, as in the unrepeated request). "
                f"The multi-recipient mistake fixture has {len(_recipients(multi))} recipients, {multi_flagged} flagged, and one warning. A score equal to `T_warn` warns. "
                f"Mutations that take the mean instead of the maximum, or let equality allow, were caught ({sum(1 for key in aggregation_mutations if mutations.get(key))} of {len(aggregation_mutations)}). "
                f"Error breakdown by recipient count (validation): {breakdown}."
            ),
            "rule": "met when every recorded assessed fixture follows maximum aggregation and the flag rule, the duplicate and multi-recipient fixtures behave as stated, equality warns, both aggregation mutations were caught, and the recipient-count breakdown is stored.",
            "evidence": [("Scenario regression", "phase_9/TEST_REPORT.md#scenario-regression-suite"), ("Evaluation report", "phase_5/EVALUATION_REPORT.md")],
        }
    )

    # AC07 ------------------------------------------------------------------
    wrong = {}
    for subset in (SELECTION_SUBSET, TEST_PRODUCT):
        warned = total = 0
        for scenario in LEGITIMATE_NOVELTY_SCENARIOS:
            cell = scenarios[subset].get(scenario)
            if cell:
                warned += cell["warned_legitimate"]
                total += cell["legitimate"]
        wrong[subset] = (warned, total)
    s11 = {subset: (scenarios[subset]["S11"]["warned_misdirected"], scenarios[subset]["S11"]["misdirected"]) for subset in (SELECTION_SUBSET, TEST_PRODUCT)}
    highest = policy["selection"]["highest_legitimate_email_risk"]
    anything_wrong = any(warned for warned, _ in wrong.values())
    out.append(
        {
            "id": "AC07",
            "name": "Legitimate novelty",
            "headline": f"{wrong[TEST_PRODUCT][0]} of {fmt.n(wrong[TEST_PRODUCT][1])} legitimate novelty emails warned on `{TEST_PRODUCT}`; S11 mistakes not warned",
            "status": NOT_MET if anything_wrong else INSUFFICIENT,
            "measured": (
                "Legitimate novelty and topic-change emails (S03, S05, S06, S07) warned: "
                + "; ".join(f"`{subset}` {warned} of {fmt.n(total)}" for subset, (warned, total) in wrong.items())
                + ". Mistaken first contacts (S11), the counterexample to a novelty-only rule, warned: "
                + "; ".join(f"`{subset}` {warned} of {total}" for subset, (warned, total) in s11.items())
                + f" (misses, counted under AC02). The highest legitimate validation email scores {fmt.score(highest)}, {t_warn - highest:.2e} below `T_warn`."
            ),
            "rule": "not met if any legitimate novelty or topic-change email was warned. Otherwise insufficient evidence: no record shows that novelty is weighed only together with other signals, and legitimate first contacts score close to the cutoff.",
            "evidence": [("Evaluation report", "phase_5/EVALUATION_REPORT.md#legitimate-first-contacts-and-the-paired-check")],
        }
    )

    # AC08 ------------------------------------------------------------------
    failures = {key: item for key, item in fixtures.items() if item["expected"].get("status") == "unable_to_assess"}
    clean = [
        key
        for key, item in failures.items()
        if item["expected"].get("decision") in (None, "") and "email_risk_score" not in item["expected"] and "recipients" not in item["expected"]
        and item["expected"]["category"] in ("invalid_input", "unavailable")
        and item["expected"]["status_code"] == (422 if item["expected"]["category"] == "invalid_input" else 503)
    ]
    categories = {item["expected"]["category"] for item in failures.values()}
    smoke_names = ("screen_invalid_input", "screen_unavailable", "screen_edit_then_reassess")
    smoke_ok = all(
        any(check["name"] == name and check["passed"] for check in run["checks"]) for run in deploy["smoke"].values() for name in smoke_names
    )
    altered = [case for case in monitor["bundle_checks"]["cases"] if case["case"] != "control_unchanged"]
    refused = [case for case in altered if case["outcome"].startswith("refused")]
    candidates = [c for run in deploy["rehearsal"].values() for c in run["candidates"].values()]
    closed = [c for c in candidates if c["assess_status"] == ["unable_to_assess"] and c["assess_decisions"] == ["None"] and c["assess_scores"] == ["None"] and c["ready_http"] == 503]
    cold, little = fixtures["cold_start_allow"], fixtures["little_text_allow"]
    limitations = {
        "cold": any("LIMITED_RELATIONSHIP_HISTORY" in _limitation_codes(r) for r in _recipients(cold)),
        "text": any("LIMITED_TEXT" in _limitation_codes(r) for r in _recipients(little)),
    }
    ok = (
        bool(failures)
        and len(clean) == len(failures)
        and categories == {"invalid_input", "unavailable"}
        and smoke_ok
        and monitor["bundle_checks"]["all_altered_bundles_refused"]
        and monitor["bundle_checks"]["control_served"]
        and len(refused) == len(altered)
        and bool(candidates)
        and len(closed) == len(candidates)
        and all(limitations.values())
    )
    out.append(
        {
            "id": "AC08",
            "name": "Failure clarity",
            "headline": f"{len(clean)} of {len(failures)} failure fixtures, {len(refused)} of {len(altered)} altered bundles, {len(closed)} of {len(candidates)} failing candidates fail closed",
            "status": MET if ok else NOT_MET,
            "measured": (
                f"{len(clean)} of {len(failures)} recorded failure fixtures returned `unable_to_assess` with a category, no decision, no score, and no recipients ({sum(1 for k in clean if failures[k]['expected']['category'] == 'invalid_input')} `invalid_input`, "
                f"{sum(1 for k in clean if failures[k]['expected']['category'] == 'unavailable')} `unavailable`). {len(refused)} of {len(altered)} altered bundles were refused with no decision and no score. "
                f"{len(closed)} of {len(candidates)} failing rollback candidates answered `unable_to_assess` and disabled assessment on the review screen. Both smoke runs passed the invalid-input, unavailable, and edit-then-reassess checks (a draft edit hides the earlier result). "
                "Cold-start and little-text fixtures are assessed with a visible limitation, not forced to allow or warn."
            ),
            "rule": "met when every failure fixture, altered bundle, and failing rollback candidate fails closed (no decision, no score), both smoke runs passed the screen's failure and stale-result checks, and the cold-start and little-text fixtures carry their evidence limitations.",
            "evidence": [("Error behavior", "phase_6/ERROR_BEHAVIOR.md"), ("Bundle checks", "phase_8/RUNBOOK.md#what-the-service-does-today-with-a-bad-bundle"), ("Rollback rehearsal", "phase_9/ROLLBACK_REHEARSAL.md"), ("Smoke", "phase_9/TEST_REPORT.md#end-to-end-smoke")],
        }
    )

    # AC09 ------------------------------------------------------------------
    warned = {key: item for key, item in assessed.items() if item["expected"]["decision"] == "warn"}
    flagged = [r for item in warned.values() for r in _recipients(item) if r["flagged"]]
    with_codes = [r for r in flagged if _codes(r)]
    reason = [r for r in flagged if "CONTENT_RELATIONSHIP_MISMATCH" in _codes(r)]
    provenance = deploy["bundle"]
    provenance_ok = all(provenance.get(key) for key in ("model_version", "feature_spec_version", "policy_version", "snapshot_id", "contract_version")) and provenance["T_warn"] == t_warn
    provenance_mutations = ("history_rule_changed", "cutoff_misreported")
    ok = (
        bool(flagged)
        and len(with_codes) == len(flagged)
        and provenance_ok
        and all(mutations.get(key) is True for key in provenance_mutations)
        and policy["scores_are"] == "risk_scores"
        and policy["calibration"] == "not_fit"
    )
    out.append(
        {
            "id": "AC09",
            "name": "Traceable explanations",
            "headline": f"{len(with_codes)} of {len(flagged)} flagged recipients carry codes; provenance compared",
            "status": MET if ok else NOT_MET,
            "measured": (
                f"All {len(flagged)} flagged recipients in the {len(warned)} recorded warning fixtures carry at least one code ({len(reason)} carry the reason `CONTENT_RELATIONSHIP_MISMATCH`; the others carry context codes, which are not proof of a mistake). "
                f"Every recorded assessment is compared on model, feature, policy, and snapshot versions, `T_warn`, and the history rule; the mutations that misreport the history rule or the cutoff were caught ({sum(1 for key in provenance_mutations if mutations.get(key))} of {len(provenance_mutations)}). "
                f"Scores are labeled `{policy['scores_are']}` and calibration is `{policy['calibration']}`."
            ),
            "rule": "met when every flagged recipient in the recorded warning fixtures carries a code, the bundle's provenance is stored and compared, both provenance mutations were caught, and the policy labels scores as risk scores without calibration.",
            "evidence": [("API contract", "phase_6/API_CONTRACT.md"), ("Scenario regression", "phase_9/TEST_REPORT.md#scenario-regression-suite")],
        }
    )

    # AC10 ------------------------------------------------------------------
    quality = records["dataset"]["quality"]
    drafts = {key: item for key, item in fixtures.items() if item["kind"] == "draft"}
    separate = all(item["desired"] in ("allow", "warn") and item["known_miss"] == (item["desired"] != item["expected"]["decision"]) for item in drafts.values())
    misses = [key for key, item in drafts.items() if item["known_miss"]]
    statement_ok = records["dataset"]["prevalence"]["statement"].startswith("Product-like prevalence is a simulation assumption")
    ok = quality["passed"] and quality["checks"]["Q04"]["passed"] and quality["checks"]["Q22"]["passed"] and separate and statement_ok
    out.append(
        {
            "id": "AC10",
            "name": "Scope and evidence honesty",
            "headline": f"{len(quality['checks'])} dataset checks passed; desired and recorded outcomes kept apart",
            "status": MET if ok else NOT_MET,
            "measured": (
                f"Dataset checks: {len(quality['checks'])} passed, including addresses on reserved example domains ({quality['checks']['Q04']['detail']}) and frozen test subsets. "
                f"{len(drafts)} draft fixtures store the desired outcome beside the recorded one, with {len(misses)} labeled known misses. The 0.5% prevalence is stated as a simulation assumption in the dataset manifest. "
                "This is a documentation criterion, checked by `tests/test_public_docs.py` and `tests/test_phase10.py` and by the separation of desired, measured, research, and unresolved statements in the documents it links."
            ),
            "rule": "met when the dataset checks pass (fictional addresses, frozen test subsets), each draft fixture keeps desired and recorded outcomes apart, and the prevalence is stated as an assumption. The documentation wording is checked by tests, not measured.",
            "evidence": [("Walkthrough", "phase_7/WALKTHROUGH.md"), ("Limitations", "LIMITATIONS_AND_FUTURE_WORK.md"), ("Data quality", "phase_2/DATA_QUALITY_AND_LEAKAGE.md")],
        }
    )
    return out


def n_legit(point_: dict) -> str:
    return fmt.n(point_["legitimate"])


# --------------------------------------------------------------------- derive


def derive(records: dict) -> dict:
    """All facts the renderers use, computed once from the loaded records."""
    validation, test = records["validation"]["subsets"], records["test"]["subsets"]
    blocks = {SELECTION_SUBSET: validation[SELECTION_SUBSET], DIAGNOSTIC_SUBSET: validation[DIAGNOSTIC_SUBSET], TEST_PRODUCT: test[TEST_PRODUCT], TEST_DIAGNOSTIC: test[TEST_DIAGNOSTIC]}
    points = {name: point(block, name) for name, block in blocks.items()}
    scenarios = {name: scenario_cells(block) for name, block in blocks.items()}
    misses = {
        scenario: {subset: (scenarios[subset][scenario]["warned_misdirected"], scenarios[subset][scenario]["misdirected"]) for subset in points}
        for scenario in KNOWN_MISSES
    }
    return {
        "records": records,
        "points": points,
        "scenarios": scenarios,
        "misses": misses,
        "acceptance": acceptance(records, points, scenarios),
    }
