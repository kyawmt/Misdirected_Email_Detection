"""Generate docs/phase_7/WALKTHROUGH.md from live API calls.

Draft decisions, scores, and codes come from responses of the running API
(through the same client the UI uses). Step 5 comes from the stored
validation scores the exploration view reads, and the known-miss scenario
counts come from the stored validation results plus the one recorded test
pass. Desired outcomes are the product intent from
docs/phase_1/SCENARIOS.md and sit in their own column. Nothing is typed by
hand, and request ids and timings are left out so the document is stable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from med_ui import exploration as xp
from med_ui.client import ApiClient, ApiResponse
from med_ui.config import (
    DESIRED_OUTCOMES,
    EXAMPLE_SUBSETS,
    KNOWN_MISS_SCENARIOS,
    ROLES,
    TEST_EVALUATION_FILE,
    VALIDATION_EVALUATION_FILE,
    WALKTHROUGH_DESIRED,
)
from med_ui.examples import (
    Catalog,
    display_names,
    invalid_address_form,
    load_catalog,
    unknown_address_form,
)
from med_ui.presentation import DraftForm, ExpectedBundle, ResultView, build_request, readiness_view, response_view


@dataclass
class Row:
    step: str
    example: str
    rule: str
    desired: str
    measured: str
    request: dict | None = None
    view: ResultView | None = None


class WalkthroughError(RuntimeError):
    pass


def _assess(client: ApiClient, form: DraftForm, names: dict[str, str], expected: ExpectedBundle) -> tuple[dict, ApiResponse, ResultView]:
    request = build_request(form, names)
    response = client.assess(request)
    return request, response, response_view(response, expected)


def _measured(view: ResultView) -> str:
    if view.kind != "assessed":
        return f"unable to assess, category `{view.category}`: \"{view.message}\"; no decision, no risk score, no recipient table"
    flagged = f"flagged {', '.join(f'`{item}`' for item in view.flagged)}" if view.flagged else "no recipient flagged"
    return f"**{view.decision}**; email risk score {view.email_risk_text} (minus T_warn: {view.margin_text}); {flagged}"


def _codes(view: ResultView) -> str:
    parts = []
    for row in view.recipients:
        codes = [line.code for line in row.codes + row.limitations]
        if codes:
            parts.append(f"`{row.address}`: {', '.join(codes)}")
    return "; ".join(parts) if parts else "no codes or limitations"


def _without(form: DraftForm, addresses: tuple[str, ...]) -> DraftForm:
    drop = {item.casefold() for item in addresses}
    return replace(form, **{role: tuple(item for item in getattr(form, role) if item.casefold() not in drop) for role in ROLES})


def build_rows(client: ApiClient, catalog: Catalog, data: xp.ExplorationData, evaluations: dict) -> list[Row]:
    names = display_names(catalog.contacts)
    expected = xp.expected_bundle(data)
    ex = catalog.examples
    missing = [key for key in ("routine", "added_recipient", "first_contact", "lookalike_miss") if key not in ex]
    if missing:
        raise WalkthroughError(f"Curated examples missing: {missing}")
    rows: list[Row] = []

    def example_row(step: str, key: str, desired: str | None = None, extra: str = "") -> Row:
        example = ex[key]
        request, _, view = _assess(client, example.form, names, expected)
        measured = _measured(view)
        if extra == "codes" and view.kind == "assessed":
            measured += f". Codes: {_codes(view)}"
        row = Row(
            step=step,
            example=f"{example.rule.title} ({example.story.scenario_id}, `{example.draft_id}`)",
            rule=example.rule.rule,
            desired=desired or DESIRED_OUTCOMES[example.story.scenario_id],
            measured=measured,
            request=request,
            view=view,
        )
        rows.append(row)
        return row

    # 1. Routine mail.
    example_row("1", "routine")

    # 2. Warned added recipient, then remove the flagged recipients and reassess.
    warned = example_row("2a", "added_recipient", extra="codes")
    if warned.view.kind != "assessed":
        raise WalkthroughError("The added-recipient example was not assessed")
    edited = _without(ex["added_recipient"].form, warned.view.flagged)
    request, _, view = _assess(client, edited, names, expected)
    rows.append(
        Row(
            step="2b",
            example="The same draft with the flagged recipients removed",
            rule="Remove every recipient the API flagged in step 2a; keep everything else.",
            desired=WALKTHROUGH_DESIRED["reassess"],
            measured=_measured(view) + f". Codes: {_codes(view)}" if view.kind == "assessed" else _measured(view),
            request=request,
            view=view,
        )
    )

    # 3. Legitimate first contact and other legitimate boundary cases.
    first = example_row("3a", "first_contact", extra="codes")
    for step, key in (("3b", "topic_change"), ("3c", "cold_start")):
        if key in ex:
            example_row(step, key, extra="codes")

    # 4. Known misses, with recorded scenario counts.
    for step, key in (("4a", "lookalike_miss"), ("4b", "topic_miss"), ("4c", "first_contact_miss")):
        if key in ex:
            row = example_row(step, key)
            counts = ", ".join(f"{subset} {warned}/{total}" for subset, warned, total in scenario_counts(evaluations, ex[key].story.scenario_id))
            row.measured += f". Known limitation. Mistakes of this scenario warned: {counts}"

    # 5. Threshold exploration on stored validation scores.
    trade = xp.tradeoff_rows(data)
    lines = [xp.counts_sentence(item) for item in trade[:4]]
    if first.view.kind == "assessed":
        lines.append("Step 3a first contact: " + xp.position_sentence(xp.position_of(data, first.view.email_risk_score)))
    rows.append(
        Row(
            step="5",
            example=xp.exploration_title(data),
            rule="The policy cutoff, then each lower stored validation score where the counts change (first four rows).",
            desired=WALKTHROUGH_DESIRED["exploration"],
            measured=" ".join(lines) + " (Stored validation scores, not an API call; the decision shown by the UI is unchanged.)",
        )
    )

    # 6. Unknown address and invalid input.
    for step, form, label, rule in (
        (
            "6a",
            unknown_address_form(catalog),
            "Step 1 draft with an address that is not in the directory",
            "The first To address of the routine example with letters removed from the end of its local part until it is not in the directory.",
        ),
        (
            "6b",
            invalid_address_form(catalog),
            "Step 1 draft with a malformed address",
            "The first To address of the routine example with `@` replaced by `.`.",
        ),
    ):
        request, _, view = _assess(client, form, names, expected)
        rows.append(Row(step=step, example=label, rule=rule, desired=DESIRED_OUTCOMES["S10"], measured=_measured(view), request=request, view=view))

    # 7. Feedback on the warned draft, then reassess the same draft.
    target = warned.view.flagged[0] if warned.view.flagged else warned.view.recipients[0].address
    feedback = client.feedback(warned.view.request_id, target, "unintended")
    _, _, again = _assess(client, ex["added_recipient"].form, names, expected)
    same = again.kind == "assessed" and again.decision == warned.view.decision and again.email_risk_score == warned.view.email_risk_score
    rows.append(
        Row(
            step="7",
            example="Feedback on the step 2a assessment",
            rule=f"Mark the first flagged recipient (`{target}`) unintended with one `POST /feedback`, then assess the unchanged draft again.",
            desired=WALKTHROUGH_DESIRED["feedback"],
            measured=(
                f"`POST /feedback` returned HTTP {feedback.status_code}, status `{(feedback.body or {}).get('status')}`. "
                f"Reassessing the same draft: **{again.decision}**, email risk score {again.email_risk_text}; "
                f"{'same decision and score as before feedback' if same else 'DIFFERENT from before feedback'}."
            ),
        )
    )
    return rows


def scenario_counts(evaluations: dict, scenario_id: str) -> list[tuple[str, int, int]]:
    """(subset, warned, total) misdirected emails of one scenario: stored validation results, then the recorded test pass."""
    found = []
    for subset in EXAMPLE_SUBSETS:
        for item in evaluations["validation"]["subsets"].get(subset, {}).get("slices", {}).get("email_by_scenario", []):
            if item["slice"] == scenario_id and item["misdirected"]:
                found.append((subset, int(item["warned_misdirected"]), int(item["misdirected"])))
    if evaluations.get("test") is not None:
        for subset, item in _test_slices(evaluations["test"], scenario_id):
            if item["misdirected"]:
                found.append((f"{subset} (recorded test pass)", int(item["warned_misdirected"]), int(item["misdirected"])))
    return found


def _test_slices(test: dict, scenario_id: str):
    for subset, payload in test["subsets"].items():
        for item in payload.get("slices", {}).get("email_by_scenario", []):
            if item["slice"] == scenario_id:
                yield subset, item


def render(rows: list[Row], ready: dict, evaluations: dict) -> str:
    versions = ", ".join(
        f"{label} `{ready.get(key)}`"
        for key, label in (
            ("contract_version", "contract"),
            ("model_version", "model"),
            ("feature_spec_version", "features"),
            ("policy_version", "policy"),
            ("snapshot_id", "snapshot"),
        )
    )
    out = [
        "# Phase 7 — Walkthrough",
        "",
        "A seven-step script for the simulated draft-review screen. It follows the narrative walkthrough in "
        "[SCENARIOS.md](../phase_1/SCENARIOS.md#narrative-walkthrough-and-safeguards), adapted to what the served policy actually does.",
        "",
        f"Generated by `python -m med_ui walkthrough` against the running API ({versions}; `T_warn = {ready.get('T_warn')!r}`, blocking disabled). "
        "Draft decisions, risk scores, and codes in the measured column come from live API responses through the UI's own client. "
        "Step 5 reads the stored validation scores the exploration view uses, and the known-miss counts in step 4 come from the stored validation results and the one recorded test pass. "
        "Desired outcomes are product intent from the scenario list; measured outcomes are what this bundle returned. The two columns are kept apart on purpose (AC10).",
        "",
        "Curated examples are validation drafts chosen by rule, not by id (rules in [config.py](../../src/med_ui/config.py)). "
        f"They come from {', '.join(f'`{name}`' for name in EXAMPLE_SUBSETS)} only. "
        "The dataset's own walkthrough drafts are all in the frozen `test_diagnostic` subset. Only validation records are kept when the tables are streamed, so none of them is loaded into memory, shown, or scored. "
        "All people and addresses are fictional. Scores are risk scores, not probabilities. Every decision is simulated.",
        "",
        "## Desired and measured outcomes",
        "",
        "| Step | Example | Selection rule | Desired outcome (SCENARIOS.md) | Measured outcome |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        out.append(f"| {row.step} | {_cell(row.example)} | {_cell(row.rule)} | {_cell(row.desired)} | {_cell(row.measured)} |")
    out += [
        "",
        "## What each step shows",
        "",
        "1. **Routine mail allows.** Load the routine example and assess it. This is the no-intervention path.",
        "2. **A warned added recipient.** The flagged recipient carries the API's codes. `CONTENT_RELATIONSHIP_MISMATCH` is the reason tied to the model; "
        "`EXTERNAL_RECIPIENT`, `LOOKALIKE_CONTACT_CONTEXT`, and `UNUSUAL_RECIPIENT_COMBINATION` are context. Remove the flagged recipient: the old result is hidden as stale "
        "until the edited draft is assessed as a new request.",
        "3. **Legitimate first contact.** It is allowed, with `LIMITED_RELATIONSHIP_HISTORY` as an evidence limitation, and it scores just below the cutoff. "
        "Legitimate first contacts are why the cutoff sits where it does. The topic-change and cold-start drafts are the other legitimate boundary cases.",
        f"4. **Known misses.** Lookalike replacements, familiar-recipient topic mistakes, and mistaken first contacts ({', '.join(KNOWN_MISS_SCENARIOS)}) are allowed. "
        "The UI shows them on purpose, labeled as a known limitation with the recorded counts. Making them visible does not make the policy catch them.",
        "5. **Threshold exploration.** The collapsed section on the screen moves a what-if cutoff over the stored validation scores. Lowering the cutoff trades false warnings "
        "on legitimate mail for extra warned mistakes; the measured column gives the counts. The decision above it never changes, and these counts come from the subset that chose the cutoff.",
        "6. **Unable to assess.** A well-formed address that is not in the directory snapshot returns `unavailable`; a malformed address returns `invalid_input`. "
        "The screen shows the category and the service message and no decision, no risk score, and no recipient table.",
        "7. **Feedback.** Marking a recipient stores one line for later review. It is not a label until reviewed, it does not change the model, the policy, or the decision, "
        "and the same draft assesses the same way afterwards.",
        "",
        "## Step details",
        "",
    ]
    for row in rows:
        if row.request is None or row.view is None:
            continue
        out.append(f"### Step {row.step}: {row.example}")
        out.append("")
        request = row.request
        addresses = "; ".join(
            f"{role}: {', '.join(item['address'] for item in request[role])}" for role in ROLES if request[role]
        )
        out.append(f"Request: sender `{request['sender']['address']}`, {addresses}, subject \"{request['subject']}\", timestamp `{request['draft_timestamp']}`.")
        out.append("")
        view = row.view
        if view.kind != "assessed":
            out.append(f"Response: unable to assess, category `{view.category}`, message \"{view.message}\".")
            out.append("")
            continue
        out.append(f"Response: **{view.decision}**, email risk score {view.email_risk_text}.")
        out.append("")
        out.append("| Recipient | Roles | Risk score | Flagged | Codes from the API | Evidence limitations |")
        out.append("| --- | --- | --- | --- | --- | --- |")
        for recipient in view.recipients:
            codes = ", ".join(f"`{line.code}` ({line.kind})" for line in recipient.codes) or "none"
            limits = ", ".join(f"`{line.code}`" for line in recipient.limitations) or "none"
            out.append(
                f"| `{recipient.address}` | {', '.join(recipient.roles)} | {recipient.risk_text} | {'yes' if recipient.flagged else 'no'} | {codes} | {limits} |"
            )
        out.append("")
    out += [
        "## Limitations the walkthrough makes visible",
        "",
        "Known misses, as misdirected emails warned of all misdirected emails of the scenario. Validation counts are the stored policy results; "
        "test counts are the one recorded test pass, quoted here and never used to choose an example or a cutoff.",
        "",
        "| Scenario | " + " | ".join(subset for subset, _, _ in scenario_counts(evaluations, KNOWN_MISS_SCENARIOS[0])) + " |",
        "| --- |" + " --- |" * len(scenario_counts(evaluations, KNOWN_MISS_SCENARIOS[0])),
        *(
            f"| {scenario} | " + " | ".join(f"{warned} of {total}" for _, warned, total in scenario_counts(evaluations, scenario)) + " |"
            for scenario in KNOWN_MISS_SCENARIOS
        ),
        "",
        "- A well-formed address outside the directory snapshot is `unable_to_assess` / `unavailable`, not a warning (Phase 1 contract).",
        "- Scores are uncalibrated risk scores. Blocking is disabled: no decision stops a draft.",
        "- The warning budget (AC01) is recorded as insufficient evidence. Zero false warnings on validation and on the one test pass describe this corpus only.",
        "",
    ]
    return "\n".join(out)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def load_evaluations(policy_dir: Path) -> dict:
    policy_dir = Path(policy_dir)
    evaluations = {"validation": json.loads((policy_dir / VALIDATION_EVALUATION_FILE).read_text(encoding="utf-8"))}
    test_path = policy_dir / TEST_EVALUATION_FILE
    if test_path.exists():
        evaluations["test"] = json.loads(test_path.read_text(encoding="utf-8"))
    return evaluations


def generate(client: ApiClient, data_dir: Path, policy_dir: Path) -> str:
    data = xp.load_exploration(policy_dir)
    ready = client.ready()
    readiness = readiness_view(ready, xp.expected_bundle(data))
    if not readiness.ok:
        raise WalkthroughError(f"{readiness.headline} {readiness.problem or ''}")
    catalog = load_catalog(data_dir, policy_dir)
    evaluations = load_evaluations(policy_dir)
    rows = build_rows(client, catalog, data, evaluations)
    return render(rows, ready.body, evaluations)
