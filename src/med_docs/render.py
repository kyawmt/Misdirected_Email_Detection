"""Render the generated documents and blocks from derived facts.

Standard library only. Every number is formatted from a record field through
`med_docs.facts`; a statement that depends on a comparison is guarded by
`_require`, so a record that no longer supports it stops the generator instead
of printing a false sentence.
"""

from __future__ import annotations

from med_docs import fmt
from med_docs.facts import MET, INSUFFICIENT, NOT_MET, reading
from med_docs.records import SOURCES, RecordError
from med_docs.version import (
    DIAGNOSTIC_SUBSET,
    DOCS_VERSION,
    KNOWN_MISSES,
    SCENARIO_TITLES,
    SELECTION_SUBSET,
    TEST_DIAGNOSTIC,
    TEST_PRODUCT,
)

PRODUCT = (SELECTION_SUBSET, TEST_PRODUCT)
SUBSET_ORDER = (SELECTION_SUBSET, DIAGNOSTIC_SUBSET, TEST_PRODUCT, TEST_DIAGNOSTIC)
SCENARIO_ORDER = ("S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S11", "routine")
COMPARISON_RUNS = (
    "always_allow",
    "rules",
    "tree_behavior_only",
    "logistic_behavior_only_unweighted",
    "logistic_behavior_only_balanced",
    "tree_all",
    "logistic_all_unweighted",
    "logistic_all_balanced",
)
RUN_ROLES = {
    "always_allow": "floor: warns on nothing",
    "rules": "behavioral rules score",
    "tree_behavior_only": "one depth-limited decision tree",
    "logistic_behavior_only_unweighted": "logistic regression",
    "logistic_behavior_only_balanced": "logistic regression, balanced class weight",
    "tree_all": "one depth-limited decision tree",
    "logistic_all_unweighted": "logistic regression",
    "logistic_all_balanced": "logistic regression, balanced class weight",
}
ABLATION_WORDS = {"none": "none", "behavior_only": "behavior only (no content cosine)", "all": "all features, content cosine included"}
CODE_KIND = {
    "CONTENT_RELATIONSHIP_MISMATCH": "reason",
    "EXTERNAL_RECIPIENT": "context",
    "LOOKALIKE_CONTACT_CONTEXT": "context",
    "UNUSUAL_RECIPIENT_COMBINATION": "context",
    "LIMITED_RELATIONSHIP_HISTORY": "evidence limitation",
    "LIMITED_TEXT": "evidence limitation",
}


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RecordError(f"A generated statement is no longer supported by the records: {message}")


# ------------------------------------------------------------------- shared


def bundle(facts: dict) -> dict:
    records = facts["records"]
    policy = records["policy"]
    _require(policy["blocking_enabled"] is False and policy["T_block"] is None, "blocking is disabled")
    return {
        "contract": records["deploy"]["bundle"]["contract_version"],
        "snapshot": policy["dataset_version"],
        "features": policy["feature_spec_version"],
        "model": policy["model_version"],
        "run": policy["model_run_name"],
        "policy": policy["policy_version"],
        "t_warn": policy["T_warn"],
        "monitor": records["monitor"]["monitor_version"],
        "deploy": records["deploy"]["deploy_version"],
        "dataset_generator": records["dataset"]["generator_version"],
        "seed": records["dataset"]["seed"],
    }


def bundle_sentence(facts: dict) -> str:
    b = bundle(facts)
    return (
        f"contract `{b['contract']}`, snapshot `{b['snapshot']}`, features `{b['features']}`, model `{b['model']}` (`{b['run']}`), "
        f"policy `{b['policy']}`, `T_warn = {b['t_warn']!r}`, blocking disabled"
    )


def prevalence_percent(facts: dict) -> str:
    return fmt.pct(float(facts["records"]["dataset"]["prevalence"]["product_like_rate"]), 1)


def train_enrichment_percent(facts: dict) -> str:
    return fmt.pct(float(facts["records"]["dataset"]["prevalence"]["train_enriched_rate"]), 1)


def _subset_label(name: str) -> str:
    return f"`{name}`"


def _cell(cell: dict | None) -> str:
    if cell is None:
        return "-"
    parts = []
    if cell["misdirected"]:
        parts.append(f"{cell['warned_misdirected']} / {cell['misdirected']} mistakes warned")
    if cell["legitimate"]:
        parts.append(f"{cell['warned_legitimate']} / {cell['legitimate']} legitimate warned")
    return "; ".join(parts)


# ---------------------------------------------------------------- the tables


def product_table(facts: dict) -> str:
    rows = []
    for name in PRODUCT:
        p = facts["points"][name]
        role = "chose the cutoff" if name == SELECTION_SUBSET else "the one frozen test pass"
        rows.append(
            [
                f"{_subset_label(name)} ({role})",
                fmt.n(p["emails"]),
                fmt.n(p["misdirected"]),
                fmt.of(p["warned_mistakes"], p["misdirected"]),
                f"{fmt.f(p['recall'])} {fmt.ci(*p['recall_exact'])}",
                fmt.n(p["legitimate"]),
                fmt.of(p["false_warnings"], p["legitimate"]),
                fmt.f(p["per_1000_legitimate"], 2),
                fmt.f(p["false_upper_per_1000"], 2),
                fmt.pct(p["coverage"]),
            ]
        )
    return fmt.table(
        [
            "Subset",
            "Emails",
            "Misdirected",
            "Warned mistakes",
            "Email recall, exact 95% (if independent)",
            "Legitimate",
            "False warnings",
            "Per 1,000 legitimate",
            "Exact 95% upper per 1,000 (if independent)",
            "Coverage",
        ],
        rows,
    )


def per_1000_table(facts: dict) -> str:
    rows = []
    for name in PRODUCT:
        p = facts["points"][name]
        low, high = p["detections_per_1000_exact"]
        rows.append(
            [
                _subset_label(name),
                fmt.n(p["emails"]),
                fmt.f(p["misdirected_per_1000"], 2),
                fmt.f(p["detections_per_1000"], 2),
                fmt.ci(low, high, 2),
                fmt.f(p["missed_per_1000"], 2),
                fmt.f(p["false_warnings_per_1000"], 2),
                fmt.f(p["interruptions_per_1000"], 2),
            ]
        )
    return fmt.table(
        [
            "Subset",
            "Emails",
            "Misdirected per 1,000 emails",
            "Detections per 1,000 emails",
            "Detections, exact 95% (if independent)",
            "Missed per 1,000 emails",
            "False warnings per 1,000 emails",
            "Interruptions per 1,000 emails",
        ],
        rows,
    )


def scenario_table(facts: dict) -> str:
    rows = []
    for scenario in SCENARIO_ORDER:
        cells = {name: facts["scenarios"][name].get(scenario) for name in SUBSET_ORDER}
        if all(cell is None for cell in cells.values()):
            continue
        rows.append(
            [
                f"**{scenario}**" if scenario in KNOWN_MISSES else scenario,
                SCENARIO_TITLES.get(scenario, ""),
                _cell(cells[SELECTION_SUBSET]),
                _cell(cells[TEST_PRODUCT]),
                reading(cells[TEST_PRODUCT]),
            ]
        )
    return fmt.table(["Scenario", "Story", f"`{SELECTION_SUBSET}`", f"`{TEST_PRODUCT}` (one test pass)", f"Reading on `{TEST_PRODUCT}`"], rows)


def diagnostic_scenario_table(facts: dict) -> str:
    rows = []
    for scenario in SCENARIO_ORDER:
        cells = {name: facts["scenarios"][name].get(scenario) for name in (DIAGNOSTIC_SUBSET, TEST_DIAGNOSTIC)}
        if all(cell is None for cell in cells.values()):
            continue
        rows.append([f"**{scenario}**" if scenario in KNOWN_MISSES else scenario, SCENARIO_TITLES.get(scenario, ""), _cell(cells[DIAGNOSTIC_SUBSET]), _cell(cells[TEST_DIAGNOSTIC])])
    return fmt.table(["Scenario", "Story", f"`{DIAGNOSTIC_SUBSET}`", f"`{TEST_DIAGNOSTIC}` (one test pass)"], rows)


def misses_table(facts: dict) -> str:
    rows = []
    for scenario in KNOWN_MISSES:
        rows.append([f"**{scenario}**", SCENARIO_TITLES[scenario]] + [fmt.of(*facts["misses"][scenario][name]) for name in SUBSET_ORDER])
    return fmt.table(["Scenario", "Story"] + [f"`{name}`" for name in SUBSET_ORDER], rows)


def comparison_table(facts: dict) -> str:
    model = facts["records"]["model"]
    runs = {run["name"]: run for run in model["runs"]}
    rows = []
    for name in COMPARISON_RUNS:
        run = runs[name]
        note = []
        if name == model["selected"]:
            note.append("**selected**")
        if not run["eligible"]:
            note.append("floor, not eligible")
        rows.append(
            [
                f"`{name}`",
                RUN_ROLES[name],
                ABLATION_WORDS[run["ablation"]],
                f"{fmt.f(run['ap'])} {fmt.ci(run['ap_low'], run['ap_high'])}",
                f"{run['positives']} / {fmt.n(run['emails'])}",
                fmt.f(run["cv_mean"]),
                "; ".join(note) or "-",
            ]
        )
    return fmt.table(["Run", "What it is", "Features", "Email average precision, family bootstrap 95%", "Positives / emails", "Train-fold mean AP", "Note"], rows)


def latency_rows(facts: dict) -> tuple[list[str], list[list]]:
    records = facts["records"]
    api, deploy = records["api_latency"], records["deploy"]["latency"]
    env = api["environment"]
    docker = deploy["docker"]
    runtime = (
        f"client {deploy['client_machine']['platform']}; service in a container on Docker Desktop "
        f"({docker['cpus']} CPUs, {docker['memory_bytes'] // (1 << 20):,} MiB VM), limited to {deploy['target']['cpus']:g} CPUs"
    )
    ac05 = deploy["ac05"]
    probe, maximum = deploy["concurrent_probe"], deploy["maximum_input_probe"]
    failures = api["measured_calls"] - api["statuses"].get("assessed", 0)
    header = ["Measurement", "Boundary", "Requests", "In flight", "p50", "p95", "p99", "Failures", "Machine"]
    rows = [
        [
            "Phase 6: API, one-shot record",
            "in-process test client, no network, backend receipt to response",
            fmt.n(api["measured_calls"]),
            api["concurrency"],
            fmt.ms(api["client_p50_ms"]),
            fmt.ms(api["client_p95_ms"]),
            fmt.ms(api["client_p99_ms"]),
            failures,
            f"{env['platform']}, {env['cpu_count']} CPUs",
        ],
        [
            "Phase 9: API container, AC05 run",
            "HTTP client on the host to the container's published loopback port; includes port forwarding, excludes the review screen",
            fmt.n(ac05["requests"]),
            ac05["concurrency"],
            fmt.ms(ac05["client"]["p50_ms"]),
            fmt.ms(ac05["client"]["p95_ms"]),
            fmt.ms(ac05["client"]["p99_ms"]),
            ac05["failures"],
            runtime,
        ],
        [
            "Phase 9: four clients at once (not AC05)",
            "same, concurrent clients",
            fmt.n(probe["requests"]),
            probe["clients"],
            fmt.ms(probe["client"]["p50_ms"]),
            fmt.ms(probe["client"]["p95_ms"]) + (" **(above the target)**" if probe["client"]["p95_ms"] > deploy["target_p95_ms"] else ""),
            fmt.ms(probe["client"]["p99_ms"]),
            probe["failures"],
            "same",
        ],
        [
            "Phase 9: maximum-size inputs",
            "same, 20 unique recipients, longest subject and body the contract allows",
            maximum["requests"],
            1,
            fmt.ms(maximum["client"]["p50_ms"]),
            fmt.ms(maximum["client"]["p95_ms"]),
            fmt.ms(maximum["client"]["p99_ms"]),
            maximum["failures"],
            "same",
        ],
    ]
    return header, rows


def acceptance_table(facts: dict) -> str:
    rows = []
    for item in facts["acceptance"]:
        links = "; ".join(f"[{label}]({target})" for label, target in item["evidence"])
        rows.append([item["id"], item["name"], f"**{item['status']}**", item["headline"], links])
    return fmt.table(["ID", "Criterion", "Status", "Measured", "Evidence"], rows)


def acceptance_counts(facts: dict) -> dict[str, int]:
    counts = {MET: 0, NOT_MET: 0, INSUFFICIENT: 0}
    for item in facts["acceptance"]:
        status = item["status"]
        if status not in counts:
            raise ValueError(f"{item['id']} has status {status!r}; a final status is met, not met, or insufficient evidence")
        counts[status] += 1
    return counts


def acceptance_summary(facts: dict) -> str:
    """One line: how many criteria landed where."""
    counts = acceptance_counts(facts)
    parts = [f"{counts[MET]} met", f"{counts[INSUFFICIENT]} insufficient evidence", f"{counts[NOT_MET]} not met"]
    return ", ".join(parts)


# ------------------------------------------------------------------- RESULTS


def results(facts: dict) -> str:
    records = facts["records"]
    points = facts["points"]
    test, selection = points[TEST_PRODUCT], points[SELECTION_SUBSET]
    policy = records["policy"]
    lines: list[str] = []
    add = lines.append
    sources = [str(path) for group in SOURCES.values() for path in group]

    add("# Results")
    add("")
    add(
        f"Generated by `python -m med_docs report` (`{DOCS_VERSION}`) from stored records. No number in this page is typed by hand, and a test regenerates the page and requires an exact match. "
        "It reads aggregate fields only: of the frozen test record it reads an explicit list of counts and intervals (see [Records read](#records-read)) and never a per-draft outcome, a draft id, or a subject."
    )
    add("")
    add(f"Served bundle: {bundle_sentence(facts)}. Scores are uncalibrated risk scores, not probabilities. All data is fictional, on reserved `.example` domains. "
        f"The product-like mix assumes {prevalence_percent(facts)} misdirected emails; that is a simulation assumption, not a measured rate. "
        "Diagnostic subsets are scenario challenge sets with many mistakes; their rates are labeled below and are never product-like results.")
    add("")
    add("Everything here describes a simulation on synthetic data. It does not show real-world detection accuracy, a confidence-supported warning budget, or production readiness, and it does not show that detection improved over any earlier version.")
    add("")

    # 1 -------------------------------------------------------------------
    add("## 1. Product-like emails: detections and interruptions")
    add("")
    add(
        f"`{SELECTION_SUBSET}` chose the cutoff, so its row is not independent evidence. `{TEST_PRODUCT}` is the one frozen test pass, scored once after the policy was written. "
        "A warning and a simulated block both count as an interruption; blocking is disabled, so every interruption is a warning."
    )
    add("")
    add(product_table(facts))
    add("")
    add("### Per 1,000 emails")
    add("")
    add(
        f"The denominator here is every email in the subset, legitimate and misdirected, so these rates describe what a sender would meet in a stream of mail at the simulated mix of {prevalence_percent(facts)} "
        f"({fmt.f(test['misdirected_per_1000'], 2)} misdirected emails per 1,000). The false-warning rate in the table above uses legitimate emails only, as the acceptance criterion defines it."
    )
    add("")
    add(per_1000_table(facts))
    add("")
    _require(test["false_warnings"] == 0 and test["interrupted"] == test["warned_mistakes"], "every test interruption was a warned mistake")
    add(
        f"- On `{TEST_PRODUCT}` the policy interrupted {fmt.f(test['interruptions_per_1000'], 2)} emails per 1,000 ({fmt.n(test['interrupted'])} of {fmt.n(test['emails'])}). "
        f"All {fmt.n(test['warnings'])} were on misdirected emails, so detections and interruptions are the same count; {fmt.f(test['missed_per_1000'], 2)} per 1,000 mistakes were missed."
    )
    add(
        f"- Zero false warnings do not show a zero rate. The exact 95% upper bound ({fmt.f(test['false_upper_per_1000'], 2)} per 1,000 legitimate emails) holds only if emails are independent, and they are not shown to be: "
        "most test drafts come from one sender ([independence table](phase_5/UNCERTAINTY_AND_PREVALENCE.md#independence)). The recall intervals carry the same condition."
    )
    add(f"- Precision is not reported here: with no false warnings it is forced to 1.000 and says nothing about use. [Precision at the upper false-warning bound, by prevalence](phase_5/UNCERTAINTY_AND_PREVALENCE.md#prevalence-sensitivity) is in the Phase 5 report.")
    add(f"- Recall has {selection['misdirected']} and {test['misdirected']} positive emails behind it, so its intervals are wide. Family-bootstrap intervals and the other subsets are in the [evaluation report](phase_5/EVALUATION_REPORT.md).")
    add("")

    # 2 -------------------------------------------------------------------
    add("## 2. Outcomes by scenario")
    add("")
    add(
        "Counts are emails at the frozen cutoff. A warned mistake is a detection; a warned legitimate email is a false warning. "
        "Scenario ids are audit labels from the generator and never model inputs. Stories are in the [scenario list](phase_1/SCENARIOS.md)."
    )
    add("")
    add(scenario_table(facts))
    add("")
    add("### The scenarios the policy does not catch")
    add("")
    highest = policy["selection"]["highest_legitimate_email_risk"]
    fixtures = records["deploy"]["fixtures"]
    miss_scores = [fixtures[key]["expected"]["email_risk_score"] for key in ("known_miss_lookalike", "known_miss_topic", "known_miss_first_contact")]
    _require(all(scores < policy["T_warn"] for scores in miss_scores), "the recorded known-miss fixtures score below the cutoff")
    _require(all(sum(w for w, _ in facts["misses"][s].values()) == 0 for s in KNOWN_MISSES), "S01, S04, and S11 were never warned")
    add(
        f"S01 (lookalike replacement), S04 (familiar recipient, unusual topic), and S11 (mistaken first contact) were not warned on any of the four subsets. "
        "These are failures of detection, shown plainly: the policy would allow each of them."
    )
    add("")
    add(misses_table(facts))
    add("")
    add(
        f"The cutoff sits just above the highest legitimate validation email ({fmt.score(highest)} against `T_warn` {fmt.score(policy['T_warn'])}, a gap of {policy['T_warn'] - highest:.2e}). "
        f"The recorded known-miss fixtures score {', '.join(fmt.score(value) for value in miss_scores)}, all below that legitimate email, so a cutoff low enough to warn on them would also warn on legitimate mail "
        "in the validation data. The recorded fixtures are in the [test report](phase_9/TEST_REPORT.md#scenario-regression-suite)."
    )
    add("")
    add("### Diagnostic subsets (scenario challenge sets, not product-like rates)")
    add("")
    add(
        f"These subsets hold many mistakes and several drafts per family, so their rates are not {prevalence_percent(facts)} prevalence results and they have no valid false-warning upper bound. They show scenario behavior only."
    )
    add("")
    add(diagnostic_scenario_table(facts))
    add("")

    # 3 -------------------------------------------------------------------
    add("## 3. Baselines and model comparison")
    add("")
    model = records["model"]
    eligibility = model["eligibility"]
    audit = model["audit"]
    selected = model["selected"]
    _require(selected == policy["model_run_name"], "the selected run is the one the policy names")
    add(
        f"Email average precision on `{SELECTION_SUBSET}` (threshold-free), with a family-bootstrap 95% interval and the number of positive emails. "
        f"`always_allow` is the floor. The selected run is `{selected}`; the selection rule and the other runs are in the [decision record](phase_4/DECISION_RECORD.md) and [experiment table](phase_4/EXPERIMENT_TABLE.md). "
        "Average precision ranks emails; it does not set the warning cutoff, and a better ranking is not by itself a reason to warn more senders."
    )
    add("")
    add(comparison_table(facts))
    add("")
    best_behavior = max((run for run in model["runs"] if run["ablation"] == "behavior_only" and run["kind"] == "logistic"), key=lambda run: run["ap"])
    chosen = next(run for run in model["runs"] if run["name"] == selected)
    add(
        f"- Content features matter on this generator. The best behavior-only logistic run reaches {fmt.f(best_behavior['ap'])} against {fmt.f(chosen['ap'])} for the selected run, and content cosine alone separates train mistakes from ordinary mail "
        f"with a separation of {fmt.f(audit['content_separation']['content_cosine'])}, inside the audit bounds of {fmt.f(audit['auc_bounds'][0], 2)} and {fmt.f(audit['auc_bounds'][1], 2)} but not far inside."
    )
    add(
        f"- The all-features model was allowed into selection only after three train-only checks: the audit flagged {len(audit['flagged_content'])} text features, and the all-features logistic run beat the behavior-only run in every train fold "
        f"(smallest margin {eligibility['min_margin_over_behavior_only']:+.3f}) and the content-only run in every fold (smallest margin {eligibility['min_margin_over_content_only']:+.3f}). Validation was not used for these checks."
    )
    add(f"- The tree is one depth-limited decision tree, compared on the same splits. It was not selected. All figures are validation figures from the Phase 4 record, with {chosen['positives']} positive emails.")
    add("")

    # 4 -------------------------------------------------------------------
    add("## 4. Latency")
    add("")
    add(
        f"Target: warm client p95 below {fmt.f(facts['records']['api_latency']['target_p95_ms'], 0)} ms with one request in flight, on documented hardware. Each row states its boundary and machine; the boundaries differ, so the rows are not interchangeable."
    )
    add("")
    header, rows = latency_rows(facts)
    add(fmt.table(header, rows))
    add("")
    api, deploy = records["api_latency"], records["deploy"]["latency"]
    add(
        f"- Cold start: {fmt.f(api['cold_start_seconds'], 2)} s to create the app and load the bundle (Phase 6, in process); {fmt.f(deploy['served']['load_seconds'], 2)} s for the API container to become ready (Phase 9)."
    )
    add(
        f"- The four-client probe is not AC05, which specifies one request in flight. It shows that one API process on {deploy['target']['cpus']:g} CPUs queues requests, and its client p95 ({fmt.ms(deploy['concurrent_probe']['client']['p95_ms'])}) "
        f"is {'above' if deploy['concurrent_probe']['client']['p95_ms'] > deploy['target_p95_ms'] else 'below'} the target. Capacity planning is out of scope."
    )
    add(
        f"- Parity: {fmt.n(api['parity']['decisions_matching_validation_table'])} of {fmt.n(api['parity']['assessed'])} API decisions matched the stored validation table in the Phase 6 run, and "
        f"{fmt.n(deploy['ac05']['parity']['decisions_matching'])} of {fmt.n(deploy['ac05']['parity']['compared'])} in the Phase 9 run."
    )
    add("")

    # 5 -------------------------------------------------------------------
    add("## 5. Acceptance criteria")
    add("")
    add(
        f"The criteria are defined in the [acceptance criteria](phase_1/ACCEPTANCE_CRITERIA.md), which is the product contract and keeps its Phase 1 wording. This is the final status of each, on this simulation only: {acceptance_summary(facts)}. "
        "Each status is **met**, **not met**, or **insufficient evidence**. AC02 is judged as a whole; its per-scenario results are in its row and in section 2."
    )
    add("")
    add(acceptance_table(facts))
    add("")
    add("### Measured values and decision rules")
    add("")
    add(
        "AC01 to AC05 and AC07 follow the rules the Phase 5 report applies. AC06, AC08, AC09, and AC10 had no stored status before this page; their rules are in `med_docs.facts` and printed here, and a status turns to **not met** if a record stops satisfying its rule. "
        "AC06 was reported as partial in the Phase 5 report because the request normalizer, which merges repeated addresses, was a Phase 6 component."
    )
    add("")
    for item in facts["acceptance"]:
        add(f"**{item['id']} — {item['name']}: {item['status']}.** {item['measured']}")
        add("")
        add(f"*Rule:* {item['rule']}")
        add("")

    # 6 -------------------------------------------------------------------
    add("## 6. Demonstrated versus assumed")
    add("")
    add("### Demonstrated on this simulation (measured, with denominators)")
    add("")
    add(f"- At the frozen cutoff on the one product-like test pass: {fmt.of(test['warned_mistakes'], test['misdirected'])} mistakes warned and {fmt.of(test['false_warnings'], test['legitimate'])} legitimate emails warned (section 1).")
    add("- Which scenarios the policy catches, partly catches, and never warns on, including three it never warns on (section 2).")
    add(f"- Which model and which features were selected, from validation only, and what the content features add on this generator (section 3).")
    add(f"- Warm latency on one machine, with the boundary of each measurement and one probe above the target (section 4).")
    deploy_records = records["deploy"]
    rehearsal = deploy_records["rehearsal"]
    add(
        f"- Failures fail closed: {len(records['monitor']['bundle_checks']['cases']) - 1} altered bundles refused, {sum(len(run['candidates']) for run in rehearsal.values())} failing rollback candidates, "
        f"and {sum(1 for item in deploy_records['fixtures'].values() if item['expected'].get('status') == 'unable_to_assess')} failure fixtures, each with no decision and no score."
    )
    add(
        f"- A local rollback was rehearsed in {len(rehearsal)} ways (container and process): {sum(1 for run in rehearsal.values() if run['passed'])} of {len(rehearsal)} passed, and the known-good deployable was restored and re-verified against "
        f"{rehearsal['container']['restores'][0]['fixtures_passed']} recorded fixtures each time."
    )
    add("")
    add("### Assumed, or not established")
    add("")
    dataset = records["dataset"]
    feedback = records["monitor"]["feedback"]
    add(f"- **Prevalence.** {prevalence_percent(facts)} misdirected product-like mail is a simulation assumption. The training subset is enriched to {train_enrichment_percent(facts)} and is not an operating point. Real prevalence is unknown.")
    add(f"- **Independence.** Emails are not shown to be independent draws: most test drafts come from one sender. AC01 stays **{next(i['status'] for i in facts['acceptance'] if i['id'] == 'AC01')}** for this reason, and every exact interval above is conditional on independence.")
    add(f"- **Fictional data.** Labels are stipulations ({dataset['quality']['checks']['Q07']['detail']}), the people and addresses are fictional, and the generator wrote the scenarios, so results depend on its assumptions.")
    add(f"- **Few positives.** {selection['misdirected']} and {test['misdirected']} misdirected emails in the two product-like subsets; recall estimates are coarse.")
    add(f"- **Calibration.** `calibration: {policy['calibration']}`. Scores rank risk; they are not probabilities.")
    add(
        f"- **One machine.** Latency and the container checks ran on one {records['api_latency']['environment']['machine']} machine and one container runtime (Docker Desktop). "
        f"One other CPU architecture was checked ({deploy_records['other_platform']['platform']}, emulated): {deploy_records['other_platform']['passed']} of {deploy_records['other_platform']['passed'] + deploy_records['other_platform']['failed']} fixtures passed."
    )
    add(
        f"- **No real users or reviewers.** Reviewed labels on the monitored traffic: {feedback['reviewed_labels_on_monitored_traffic']}. The review in the monitoring replay is `{feedback['label_source']}`; "
        f"feedback changed {feedback['labels_changed_by_feedback']} labels and left the policy and model unchanged ({yes_no(feedback['policy_and_model_unchanged'])}). Monitoring thresholds are conventions no real incident has tested."
    )
    for item in deploy_records["clean_checkout"]["not_verified"]:
        # Quoted from the Phase 9 record, which was true when it was written; the later
        # GitHub status is hand-written in the limitations document.
        add(f"- **Not verified when the Phase 9 record was written.** {item[0].upper() + item[1:]}. Later status: [CI on GitHub](LIMITATIONS_AND_FUTURE_WORK.md#ci-on-github).")
    add("- **Not tested.** No Linux host and no Windows host was used, nothing was pushed to a registry or hosted, and there is no shadow mode, canary, or live rollback switch. See [limitations and future work](LIMITATIONS_AND_FUTURE_WORK.md).")
    add("")

    # 7 -------------------------------------------------------------------
    add("## Records read")
    add("")
    add("Every figure above comes from one of these stored records. The generator never opens a data table, scores a draft, or fits anything.")
    add("")
    add(fmt.table(["Record"], [[f"`{path}`"] for path in sources]))
    add("")
    add(
        f"`artifacts/{policy['policy_version']}/test_evaluation.json` also stores, under each subset, per-draft outcomes for frozen test drafts. The generator removes those members from the file's text before parsing it (it reads past their characters to find where each member ends but never decodes them, so no per-draft value is constructed) and then reads only these key paths: "
        "the top-level policy and version fields, and for each test subset the `policy` counts, intervals, interventions, and coverage and `slices/email_by_scenario`. "
        "The validation record is read through the same allow-list, and its per-draft outcomes are removed the same way."
    )
    add("")
    return "\n".join(lines)


# ------------------------------------------------------------ README headline


def readme_headline(facts: dict) -> str:
    points = facts["points"]
    v, t = points[SELECTION_SUBSET], points[TEST_PRODUCT]
    records = facts["records"]
    deploy, api = records["deploy"]["latency"], records["api_latency"]
    rows = [
        ["Emails, of which misdirected", f"{fmt.n(v['emails'])}, {v['misdirected']}", f"{fmt.n(t['emails'])}, {t['misdirected']}"],
        ["Mistakes warned (recall, exact 95% if independent)", f"{fmt.of(v['warned_mistakes'], v['misdirected'])} ({fmt.f(v['recall'])} {fmt.ci(*v['recall_exact'])})", f"{fmt.of(t['warned_mistakes'], t['misdirected'])} ({fmt.f(t['recall'])} {fmt.ci(*t['recall_exact'])})"],
        ["Legitimate emails warned", fmt.of(v["false_warnings"], v["legitimate"]), fmt.of(t["false_warnings"], t["legitimate"])],
        ["Detections, interruptions per 1,000 emails", f"{fmt.f(v['detections_per_1000'], 2)}, {fmt.f(v['interruptions_per_1000'], 2)}", f"{fmt.f(t['detections_per_1000'], 2)}, {fmt.f(t['interruptions_per_1000'], 2)}"],
    ]
    table = fmt.table(["Product-like emails", f"`{SELECTION_SUBSET}` (chose the cutoff)", f"`{TEST_PRODUCT}` (one frozen pass)"], rows)
    never = ", ".join(KNOWN_MISSES)
    ac01 = next(item for item in facts["acceptance"] if item["id"] == "AC01")
    lines = [
        table,
        "",
        f"- Product-like mix: {prevalence_percent(facts)} misdirected, a simulation assumption. Per-1,000 rates use every email in the subset as the denominator.",
        f"- Never warned on any subset: {never}. The policy allows these mistakes.",
        f"- AC01 (at most {fmt.f(t['budget_per_1000'], 0)} false warning per 1,000 legitimate emails): **{ac01['status']}**. {fmt.of(t['false_warnings'], t['legitimate'])} is a descriptive pass on this corpus; the exact upper bound, {fmt.f(t['false_upper_per_1000'], 2)} per 1,000, holds only if emails are independent, and most test drafts come from one sender.",
        f"- Client p95 latency {fmt.ms(api['client_p95_ms'])} in process and {fmt.ms(deploy['ac05']['client_p95_ms'])} against the container, one request in flight, on one machine; target {fmt.f(api['target_p95_ms'], 0)} ms.",
        f"- Acceptance criteria: {acceptance_summary(facts)}. See [results](docs/RESULTS.md) for denominators, intervals, and each rule.",
        "- Scores are uncalibrated risk scores, not probabilities. Blocking is disabled. Nothing here shows that detection improved.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------- MODEL CARD


def card_versions(facts: dict) -> str:
    records = facts["records"]
    b = bundle(facts)
    files = records["deploy"]["bundle_files"]
    meta = records["model"]["metadata"]
    images = records["deploy"]["images"]
    served = records["api_latency"]["versions"]
    rows = [
        ["Dataset", f"`{b['snapshot']}` (generator `{b['dataset_generator']}`, seed {b['seed']})", f"manifest {fmt.cut(files['data/med-synth-v4/dataset_manifest.json'])}"],
        ["Features", f"`{b['features']}`", f"manifest {fmt.cut(files['artifacts/med-features-v2/artifact_manifest.json'])}"],
        ["Model", f"`{b['model']}`, run `{b['run']}`", f"`model.joblib` {fmt.cut(files['artifacts/med-model-v2/model.joblib'])}"],
        ["Policy", f"`{b['policy']}`, `T_warn = {b['t_warn']!r}`, blocking disabled, calibration `{records['policy']['calibration']}`", f"`policy.json` {fmt.cut(records['policy_sha256'])}"],
        ["API contract", f"`{b['contract']}`", "-"],
        ["Monitoring record", f"`{b['monitor']}`", "write-once records"],
        ["Deployment record", f"`{b['deploy']}`", "write-once records"],
        ["Document generator", f"`{DOCS_VERSION}`", "-"],
        ["Libraries (served)", f"Python {served['python']}, scikit-learn {served['scikit_learn']}, NumPy {served['numpy']}, FastAPI {served['fastapi']}", f"model fit with scikit-learn {meta['sklearn_version']}"],
        ["Images", ", ".join(f"`{item['reference']}` ({item['architecture']}, {fmt.mib(item['size_bytes'])})" for item in images.values()), ", ".join(fmt.cut(item["id"].split(":", 1)[1]) for item in images.values())],
    ]
    return fmt.table(["Component", "Version", "Identity (SHA-256 prefix)"], rows)


def card_training(facts: dict) -> str:
    records = facts["records"]
    dataset, model, features = records["dataset"], records["model"], records["features"]
    train = dataset["row_counts"]["subsets"]["train"]
    splits = dataset["splits"]
    scope = features["fit_scope"]
    folds = model["folds"]
    meta = model["metadata"]
    lines = [
        f"- **Training subset** `{meta['training_subset']}`: {fmt.n(train['drafts'])} emails, {fmt.n(train['misdirected'])} misdirected ({fmt.pct(train['misdirected'] / train['drafts'])}, enriched; not an operating point), "
        f"{fmt.n(model['train']['recipient_rows'])} recipient rows of which {fmt.n(model['train']['positive_rows'])} unintended. Sent {splits['train']['start'][:10]} to {splits['train']['end'][:10]} (end exclusive); earlier mail from {splits['warmup']['start'][:10]} is history only.",
        f"- **Text vocabulary and weights** were fit on {fmt.n(scope['document_count'])} sent messages before {scope['fit_sent_at_end_exclusive'][:10]} (vocabulary {fmt.n(scope['vocabulary_size'])}; warm-up mail included; validation and test mail excluded), not on validation or test.",
        f"- **Tuning** used expanding chronological folds inside `train`: {len(folds)} blocks covering weeks {folds[0]['week_start']} to {folds[-1]['week_end']}, of which {model['folds_scored']} were scored; each block keeps a draft's family together. The regularization constant was chosen from the grid {', '.join(fmt.f(value, 3).rstrip('0').rstrip('.') for value in model['c_grid'])} by mean email average precision across the scored folds.",
        f"- **Selected** `C = {meta['config']['C']:g}`, the top of the grid, with `class_weight = {meta['config']['class_weight']}`. A weaker-regularized fit was not searched, and coefficients on overlapping count features are not separate effects.",
        f"- **Eligibility** of an all-features model required a clean shortcut audit and a win over the behavior-only and content-only runs in every train fold (smallest margins {model['eligibility']['min_margin_over_behavior_only']:+.3f} and {model['eligibility']['min_margin_over_content_only']:+.3f}).",
        f"- **Seed** {meta['seed']}. The scratch rebuild of features and model reproduced the feature files and the model byte for byte ([reproducibility](phase_9/REPRODUCIBILITY.md)).",
    ]
    return "\n".join(lines)


def card_model(facts: dict) -> str:
    records = facts["records"]
    meta = records["model"]["metadata"]
    fill_minutes = meta["recency_fill_days"] * 24 * 60
    rows = [
        ["Estimator", f"{meta['kind']} regression, one linear model on standardized features"],
        ["Run", f"`{meta['run_name']}` (`{meta['ablation']}` features)"],
        ["Input features", f"{meta['n_features']} per recipient row"],
        ["Regularization", f"`C = {meta['config']['C']:g}`, class weight `{meta['config']['class_weight']}`"],
        ["Output", f"`{meta['scores_are']}`: one score per recipient; the email score is the maximum over unique recipients"],
        ["Calibration", f"`{meta['calibration']}`; thresholds `{meta['thresholds']}` in the model, set by the policy"],
        ["No history", f"unobserved recency is replaced by the training median of observed recency ({meta['recency_fill_days']} days, {fmt.f(fill_minutes, 1)} minutes) and then log-transformed, with an indicator that the value was missing"],
        ["Libraries", f"scikit-learn {meta['sklearn_version']}, NumPy {meta['numpy_version']}"],
    ]
    return fmt.table(["Item", "Value"], rows)


def card_evaluation(facts: dict) -> str:
    records = facts["records"]
    dataset = records["dataset"]
    counts = dataset["row_counts"]["subsets"]
    splits = dataset["splits"]
    use = {
        "train": ("fit the model and the text transformer's history", "no"),
        SELECTION_SUBSET: ("model selection and the one cutoff choice", "no"),
        DIAGNOSTIC_SUBSET: ("scenario diagnostics", "no"),
        TEST_PRODUCT: ("one evaluation of the frozen policy", "yes"),
        TEST_DIAGNOSTIC: ("one scenario evaluation of the frozen policy", "yes"),
    }
    rows = []
    for name in ("train", SELECTION_SUBSET, DIAGNOSTIC_SUBSET, TEST_PRODUCT, TEST_DIAGNOSTIC):
        c = counts[name]
        rows.append([f"`{name}`", fmt.n(c["drafts"]), fmt.n(c["misdirected"]), fmt.n(c["legitimate"]), use[name][0], use[name][1]])
    top = records["test"]["top"]
    lines = [
        fmt.table(["Subset", "Emails", "Misdirected", "Legitimate", "Used for", "Frozen"], rows),
        "",
        f"Validation mail was sent {splits['validation']['start'][:10]} to {splits['validation']['end'][:10]}; test mail {splits['test']['start'][:10]} to {splits['test']['end'][:10]} (ends exclusive). "
        f"The policy file was written {records['policy']['created_at']} and the frozen subsets were scored once, {top['evaluated_at']}, with the policy whose SHA-256 the test record stores ({fmt.cut(top['policy_sha256'])}). "
        f"Product-like subsets hold exactly {prevalence_percent(facts)} misdirected emails by construction.",
    ]
    return "\n".join(lines)


def card_operating_point(facts: dict) -> str:
    policy = facts["records"]["policy"]
    selection = policy["selection"]
    chosen = selection["chosen"]
    confusion = policy["validation_confusion"]["email"]
    highest = selection["highest_legitimate_email_risk"]
    rows = [
        ["Decision rule", f"email risk = {policy['decision_rule']['email_risk']}; allow when `{policy['decision_rule']['allow']}`; warn when `{policy['decision_rule']['warn']}`; block: {policy['decision_rule']['block']}"],
        ["`T_warn`", f"`{policy['T_warn']!r}`"],
        ["Chosen on", f"`{selection['subset']}`, email level"],
        ["Candidates", f"{fmt.n(selection['n_candidates'])}, of which {selection['zero_false_intervention_candidates']} had no false interventions; {len(selection['tied_candidates'])} at the chosen recall"],
        ["Chosen operating point", f"{chosen['true_positives']} of {confusion['positives']} mistakes warned, {chosen['false_interventions']} of {fmt.n(confusion['legitimate'])} legitimate emails warned"],
        ["Highest legitimate validation score", f"{fmt.score(highest)}, {policy['T_warn'] - highest:.2e} below `T_warn`"],
        ["Budget", f"at most {fmt.f(policy['budget']['budget_per_1000'], 0)} false intervention per 1,000 legitimate emails; an intervention is {policy['budget']['intervention']}; the denominator is {policy['budget']['denominator']}"],
        ["Parity check before the policy was written", f"{fmt.n(policy['scoring_path_parity']['identical_decisions'])} of {fmt.n(policy['scoring_path_parity']['drafts'])} decisions identical between the batch path and the single-draft path the API uses; largest score difference {policy['scoring_path_parity']['max_abs_email_risk_difference']:.2e}"],
        ["Calibration", f"`{policy['calibration']}`"],
    ]
    return fmt.table(["Item", "Value"], rows) + f"\n\nSelection rule: {selection['rule']}"


def card_results(facts: dict) -> str:
    lines = [
        product_table(facts),
        "",
        per_1000_table(facts),
        "",
        "Diagnostic subsets, scenario challenge sets and not product-like results:",
        "",
    ]
    rows = []
    for name in (DIAGNOSTIC_SUBSET, TEST_DIAGNOSTIC):
        p = facts["points"][name]
        rows.append([f"`{name}`", fmt.n(p["emails"]), fmt.of(p["warned_mistakes"], p["misdirected"]), fmt.of(p["false_warnings"], p["legitimate"]), "family-bootstrap interval only; see the evaluation report"])
    lines.append(fmt.table(["Subset", "Emails", "Warned mistakes", "Legitimate emails warned", "Interval"], rows))
    lines += ["", "Acceptance status (rules and measured values in [results](RESULTS.md#5-acceptance-criteria)):", "", fmt.table(["ID", "Criterion", "Status"], [[i["id"], i["name"], f"**{i['status']}**"] for i in facts["acceptance"]])]
    return "\n".join(lines)


def card_failures(facts: dict) -> str:
    records = facts["records"]
    policy = records["policy"]
    model = records["model"]
    audit = model["audit"]
    highest = policy["selection"]["highest_legitimate_email_risk"]
    chosen = next(run for run in model["runs"] if run["name"] == model["selected"])
    best_behavior = max((run for run in model["runs"] if run["ablation"] == "behavior_only" and run["kind"] == "logistic"), key=lambda run: run["ap"])
    lines = [
        misses_table(facts),
        "",
        f"- **Legitimate first contacts sit just below the cutoff.** The highest legitimate validation email scores {fmt.score(highest)}, {policy['T_warn'] - highest:.2e} below `T_warn`. A small shift in legitimate scores, or a new kind of legitimate first contact, would add false warnings.",
        f"- **Content cosine is a strong signal on this generator.** Its train separation is {fmt.f(audit['content_separation']['content_cosine'])}, inside the audit bounds ({fmt.f(audit['auc_bounds'][0], 2)} to {fmt.f(audit['auc_bounds'][1], 2)}) but not far inside. Validation email average precision is {fmt.f(chosen['ap'])} for the selected run and {fmt.f(best_behavior['ap'])} for the best behavior-only logistic run.",
        f"- **Few positives.** {facts['points'][SELECTION_SUBSET]['misdirected']} and {facts['points'][TEST_PRODUCT]['misdirected']} misdirected emails in the product-like subsets.",
        f"- **Reason codes in the recorded warning fixtures.** {reason_code_sentence(facts)}",
    ]
    return "\n".join(lines)


def reason_code_sentence(facts: dict) -> str:
    fixtures = facts["records"]["deploy"]["fixtures"]
    warned = [item for item in fixtures.values() if item["kind"] == "draft" and item["expected"].get("decision") == "warn"]
    flagged = [r for item in warned for r in item["expected"]["recipients"] if r["flagged"]]
    reason = [r for r in flagged if any(c["code"] == "CONTENT_RELATIONSHIP_MISMATCH" for c in r["reason_codes"])]
    return (
        f"{len(reason)} of {len(flagged)} flagged recipients in {len(warned)} warning fixtures carry the reason `CONTENT_RELATIONSHIP_MISMATCH`; "
        f"the remaining {len(flagged) - len(reason)} {'carries' if len(flagged) - len(reason) == 1 else 'carry'} only context codes."
    )


# ------------------------------------------------------------- DEMO SCRIPT


def _fixture(facts: dict, key: str) -> dict:
    return facts["records"]["deploy"]["fixtures"][key]


def _recipient_codes(fixture: dict) -> list[tuple[str, str]]:
    seen = []
    for recipient in fixture["expected"]["recipients"]:
        for item in recipient["reason_codes"]:
            seen.append((item["code"], item["text"]))
    return seen


def demo_step_1(facts: dict) -> str:
    f = _fixture(facts, "routine_allow")
    e = f["expected"]
    flagged = sum(1 for r in e["recipients"] if r["flagged"])
    _require(e["decision"] == "allow" and flagged == 0, "the routine fixture is an allow with no flagged recipient")
    return "\n".join(
        [
            f"- Recorded fixture `routine_allow` (validation draft `{f['draft_id']}`, scenario {f['scenario']}): decision **{e['decision']}**, email risk score {fmt.score(e['email_risk_score'])} against `T_warn` {fmt.score(bundle(facts)['t_warn'])}, {len(e['recipients'])} recipients, {flagged} flagged.",
            "- Screen: [step 1 of the generated walkthrough](phase_7/WALKTHROUGH.md#step-1-routine-project-update-s05-d003390) and its [screenshot](phase_7/screenshots/step1_routine_allow.png).",
        ]
    )


def demo_step_2(facts: dict) -> str:
    f = _fixture(facts, "added_recipient_warn")
    e = f["expected"]
    t_warn = bundle(facts)["t_warn"]
    flagged = [r for r in e["recipients"] if r["flagged"]]
    _require(e["decision"] == "warn" and len(flagged) == 1, "the added-recipient fixture is a warning on one recipient")
    codes = ", ".join(f"`{item['code']}`" for item in flagged[0]["reason_codes"])
    return "\n".join(
        [
            f"- Recorded fixture `added_recipient_warn` (validation draft `{f['draft_id']}`, scenario {f['scenario']}): decision **{e['decision']}**, email risk score {fmt.score(e['email_risk_score'])}, {fmt.delta(e['email_risk_score'] - t_warn)} from `T_warn`; {len(flagged)} of {len(e['recipients'])} recipients flagged (the one added as {'/'.join(flagged[0]['roles'])}); codes {codes}.",
            "- Screen: [step 2a of the generated walkthrough](phase_7/WALKTHROUGH.md#step-2a-forecast-with-an-added-vendor-s02-d003027) and its [screenshot](phase_7/screenshots/step2_added_recipient_warn.png); the edit-and-reassess result is in [step 2b](phase_7/WALKTHROUGH.md#step-2b-the-same-draft-with-the-flagged-recipients-removed).",
        ]
    )


def demo_step_3(facts: dict) -> str:
    f = _fixture(facts, "added_recipient_warn")
    rows = [[f"`{code}`", CODE_KIND[code], text] for code, text in _recipient_codes(f)]
    return fmt.table(["Code the API returned", "Kind", "Text the API returned"], rows)


def demo_step_4(facts: dict) -> str:
    records = facts["records"]
    policy = records["policy"]
    selection = policy["selection"]
    chosen = selection["chosen"]
    confusion = policy["validation_confusion"]["email"]
    first = _fixture(facts, "legitimate_first_contact_allow")["expected"]
    miss = _fixture(facts, "known_miss_lookalike")
    me = miss["expected"]
    highest = selection["highest_legitimate_email_risk"]
    _require(me["decision"] == "allow" and me["email_risk_score"] < first["email_risk_score"], "the known miss scores below the legitimate first contact")
    _require(first["decision"] == "allow", "the legitimate first contact is allowed")
    _require(any(item["code"] == "LIMITED_RELATIONSHIP_HISTORY" for r in first["recipients"] for item in r["evidence_limitations"]), "the legitimate first contact carries a limited-history limitation")
    return "\n".join(
        [
            f"- Cutoff `T_warn = {policy['T_warn']!r}`, chosen on `{selection['subset']}`: {chosen['true_positives']} of {confusion['positives']} mistakes warned and {chosen['false_interventions']} of {fmt.n(confusion['legitimate'])} legitimate emails warned. The highest legitimate validation email scores {fmt.score(highest)}, {policy['T_warn'] - highest:.2e} below the cutoff.",
            f"- Recorded fixture `legitimate_first_contact_allow` (draft `{_fixture(facts, 'legitimate_first_contact_allow')['draft_id']}`): allowed at {fmt.score(first['email_risk_score'])} with an evidence limitation. This is the legitimate email that holds the cutoff up.",
            f"- Recorded known miss `known_miss_lookalike` (draft `{miss['draft_id']}`, scenario {miss['scenario']}, a mistake): allowed at {fmt.score(me['email_risk_score'])}, below the legitimate first contact. A cutoff low enough to warn on it would also warn on that legitimate email in the validation data.",
            "- Screen: the collapsed threshold-exploration section, [step 5 of the generated walkthrough](phase_7/WALKTHROUGH.md#desired-and-measured-outcomes) (what-if counts on validation scores only; the decision above it never changes), and [step 4a](phase_7/WALKTHROUGH.md#step-4a-staffing-note-to-a-similar-name-s01-d003002) for the miss.",
        ]
    )


def demo_step_5(facts: dict) -> str:
    monitor = facts["records"]["monitor"]
    windows = monitor["windows"]
    last = windows[-1]
    ref = monitor["reference"]
    reference_windows = [w for w in windows if w["role"] == "reference"]
    injected = [w for w in windows if w["injected_emails"]]
    _require(last["injected_emails"] > 0 and last["warnings"] == 0, "the last replay window carries injected first contacts and no warning")
    return "\n".join(
        [
            f"- Replay of {len(windows)} windows of {fmt.n(last['requests'])} validation emails through the API (plan checksum {fmt.cut(monitor['plan_checksum'])}); windows {reference_windows[0]['window']} to {reference_windows[-1]['window']} are the reference period ({fmt.n(ref['requests'])} emails). Windows {injected[0]['window']} to {injected[-1]['window']} replace a growing share of routine mail with legitimate first contacts (injected share {', '.join(fmt.pct(w['planned_injected_share'], 0) for w in injected)}).",
            f"- Last window: {last['injected_emails']} of {fmt.n(last['requests'])} emails injected, {last['limited_history_emails']} with limited relationship history (reference: {ref['emails_with_limited_relationship_history']} of {fmt.n(ref['requests'])}), {last['near_band_emails']} scoring just below the cutoff (reference: {ref['near_band_emails']} of {fmt.n(ref['requests'])}), {last['warnings']} warned (reference: {ref['warnings']} of {fmt.n(ref['requests'])}); highest allowed score {fmt.score(last['highest_allowed'])}, margin to the cutoff {last['margin_to_cutoff']:.2e} (reference {ref['margin_to_cutoff']:.2e}).",
            f"- Unable to assess in the replay: {sum(w['unable_to_assess'] for w in windows)} of {fmt.n(sum(w['requests'] for w in windows))} requests. Reviewed labels on this traffic: {monitor['feedback']['reviewed_labels_on_monitored_traffic']}; the review is simulated.",
            "- Command output: [the drift replay timeline and its three findings](phase_8/DRIFT_REPLAY.md#timeline) (input drift, decision-rate change, and confirmed performance change are kept apart).",
        ]
    )


def demo_step_6(facts: dict) -> str:
    deploy = facts["records"]["deploy"]
    container, process = deploy["rehearsal"]["container"], deploy["rehearsal"]["process"]
    candidate_lines = []
    for name, c in container["candidates"].items():
        _require(c["ready_http"] == 503 and c["assess_status"] == ["unable_to_assess"] and c["assess_decisions"] == ["None"], "a failing candidate answers unable_to_assess")
        candidate_lines.append(
            f"  - `{name}` ({c['fault']}): `/ready` {c['ready_http']} ({c['ready_reason'].split(':', 1)[-1].strip()}); `POST /assess` `unable_to_assess`, decision and score absent; the suite flagged {c['flagged_by_the_suite']} of {c['assessed_fixtures']} assessed fixtures; assessment disabled on the review screen: {yes_no(c['assessment_disabled_on_screen'])}."
        )
    restores = container["restores"]
    return "\n".join(
        [
            f"- Container rehearsal ({container['date_utc']}): **{'passed' if container['passed'] else 'failed'}**, {container['steps_passed']} of {container['steps']} steps. Known-good image `{container['known_good_id'].split(':', 1)[1][:12]}…` swapped for two failing candidates, each restored and re-verified ({restores[0]['fixtures_passed']} of {restores[0]['fixtures_passed'] + restores[0]['fixtures_failed']} fixtures, `/ready` {restores[0]['ready_http']}); image unchanged: {yes_no(container['known_good_unchanged'])}.",
            *candidate_lines,
            f"- Process rehearsal: {'passed' if process['passed'] else 'failed'}, {process['steps_passed']} of {process['steps']} steps, published bundle files unchanged: {yes_no(process['published_bundle_files_unchanged'])}.",
            f"- Bundle checks from monitoring: {sum(1 for c in facts['records']['monitor']['bundle_checks']['cases'] if c['outcome'].startswith('refused'))} of {len(facts['records']['monitor']['bundle_checks']['cases']) - 1} altered bundles refused, each with no decision and no score.",
            "- Command output: [rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md).",
        ]
    )


# ----------------------------------------------------------- LIMITATIONS


def limit_evidence(facts: dict) -> str:
    records = facts["records"]
    policy = records["policy"]
    model = records["model"]
    audit = model["audit"]
    highest = policy["selection"]["highest_legitimate_email_risk"]
    chosen = next(run for run in model["runs"] if run["name"] == model["selected"])
    best_behavior = max((run for run in model["runs"] if run["ablation"] == "behavior_only" and run["kind"] == "logistic"), key=lambda run: run["ap"])
    feedback = records["monitor"]["feedback"]
    env = records["api_latency"]["environment"]
    deploy = records["deploy"]
    other = deploy["other_platform"]
    lines = [
        "Scenarios never warned on, by subset (warned mistakes / all mistakes of the scenario):",
        "",
        misses_table(facts),
        "",
        f"- **Margin.** Highest legitimate validation email {fmt.score(highest)}; `T_warn` {fmt.score(policy['T_warn'])}; gap {policy['T_warn'] - highest:.2e}.",
        f"- **Content.** Train separation of content cosine {fmt.f(audit['content_separation']['content_cosine'])}; selected run AP {fmt.f(chosen['ap'])} against {fmt.f(best_behavior['ap'])} for the best behavior-only logistic run, on {chosen['positives']} positive emails.",
        f"- **Prevalence and positives.** Product-like prevalence {prevalence_percent(facts)} (assumed); {facts['points'][SELECTION_SUBSET]['misdirected']} and {facts['points'][TEST_PRODUCT]['misdirected']} misdirected emails in the validation and test product-like subsets.",
        f"- **Reviewed labels.** {feedback['reviewed_labels_on_monitored_traffic']} reviewed labels exist for the monitored traffic; the replay's review is `{feedback['label_source']}`.",
        f"- **Machine.** {env['platform']}, {env['cpu_count']} CPUs; containers on Docker Desktop. A second architecture ({other['platform']}, emulated) passed {other['passed']} of {other['passed'] + other['failed']} fixtures.",
    ]
    for item in deploy["clean_checkout"]["not_verified"]:
        lines.append(f"- **Not verified when the Phase 9 record was written.** {item[0].upper() + item[1:]}. Later status: [CI on GitHub](#ci-on-github).")
    return "\n".join(lines)


# ---------------------------------------------------------- ARCHITECTURE


def architecture_artifacts(facts: dict) -> str:
    records = facts["records"]
    b = bundle(facts)
    files = records["deploy"]["bundle_files"]
    digests = records["deploy"]["digests"]
    anchored = digests["files"]
    rows = [
        ["Dataset snapshot", f"`{b['snapshot']}`", f"`dataset_manifest.json` {fmt.cut(files['data/med-synth-v4/dataset_manifest.json'])}", "`dataset_manifest.json` holds a SHA-256 and a record count per table; the API and `check-bundle` compare them", "API: `/ready` 503 and `unable_to_assess`; `check-bundle` fails"],
        ["Feature artifact", f"`{b['features']}`", f"`artifact_manifest.json` {fmt.cut(files['artifacts/med-features-v2/artifact_manifest.json'])}", "`artifact_manifest.json` holds a SHA-256 per file; verified when the artifact loads", "API: `/ready` 503 and `unable_to_assess`; `check-bundle` also fails if a frozen feature file exists"],
        ["Model", f"`{b['model']}` (`{b['run']}`)", f"`model.joblib` {fmt.cut(files['artifacts/med-model-v2/model.joblib'])}", "`policy.json` records the model's SHA-256 and the feature manifest's SHA-256", "API: checksum mismatch refused"],
        ["Policy", f"`{b['policy']}`", f"`policy.json` {fmt.cut(records['policy_sha256'])}", "names the model run, versions, and checksums; its own digest is anchored in `bundle_digests.json` for builds and CI", "refused on another version, run, or checksum; blocking on; a non-finite cutoff; a calibrated claim; a missing file"],
        ["Stored validation files", "`validation_scores.csv`, `validation_evaluation.json`", f"{fmt.cut(anchored['artifacts/med-policy-v2/validation_scores.csv'])}, {fmt.cut(anchored['artifacts/med-policy-v2/validation_evaluation.json'])}", "anchored digests, compared when the review-screen image is built", "image build and CI fail"],
        ["Monitoring and deployment records", f"`{b['monitor']}`, `{b['deploy']}`", "-", "write-once: a command that names an existing record is refused", "the command refuses; nothing is overwritten"],
    ]
    return fmt.table(["Artifact", "Version", "Identity (SHA-256 prefix)", "Checksum rule", "Refusal rule"], rows)


def architecture_images(facts: dict) -> str:
    images = facts["records"]["deploy"]["images"]
    rows = []
    for name, item in images.items():
        rows.append(
            [
                f"`{item['reference']}`",
                "scoring API (core install)" if name == "api" else "review screen (`ui` extra)",
                f"{item['architecture']}, {fmt.mib(item['size_bytes'])}, {item['packages']} packages, user {item['user']}",
                "no" if not item["pyarrow_importable"] else "yes",
                f"{item['files_in_app']} files read-only",
            ]
        )
    return fmt.table(["Image", "Holds", "Build", "pyarrow importable", "Bundle files"], rows)


# ------------------------------------------------------------------ registry


def model_card_blocks(facts: dict) -> dict[str, str]:
    return {
        "card_versions": card_versions(facts),
        "card_training": card_training(facts),
        "card_model": card_model(facts),
        "card_evaluation": card_evaluation(facts),
        "card_operating_point": card_operating_point(facts),
        "card_results": card_results(facts),
        "card_failures": card_failures(facts),
    }


def readme_blocks(facts: dict) -> dict[str, str]:
    return {"headline": readme_headline(facts)}


def demo_blocks(facts: dict) -> dict[str, str]:
    return {
        "demo_step_1": demo_step_1(facts),
        "demo_step_2": demo_step_2(facts),
        "demo_step_3": demo_step_3(facts),
        "demo_step_4": demo_step_4(facts),
        "demo_step_5": demo_step_5(facts),
        "demo_step_6": demo_step_6(facts),
    }


def limitations_blocks(facts: dict) -> dict[str, str]:
    return {"limit_evidence": limit_evidence(facts)}


def architecture_blocks(facts: dict) -> dict[str, str]:
    return {"artifact_table": architecture_artifacts(facts), "image_table": architecture_images(facts)}
