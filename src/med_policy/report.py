"""Generate docs/phase_5 from the policy artifacts.

Every number comes from policy.json, validation_evaluation.json,
test_evaluation.json, latency.json, and the Phase 4 model metadata. Nothing
here is typed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from med_policy.version import (
    ARTIFACT_ROOT,
    BUDGET_PER_1000,
    DIAGNOSTIC_SUBSET,
    MODEL_DIR,
    SELECTION_SUBSET,
    TEST_SUBSETS,
)

TEST_PRODUCT, TEST_DIAGNOSTIC = TEST_SUBSETS


def write_documents(policy_dir: Path, docs_dir: Path) -> list[Path]:
    policy_dir = Path(policy_dir)
    docs_dir = Path(docs_dir)
    ctx = _context(policy_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    figures = docs_dir / "figures"
    figures.mkdir(exist_ok=True)
    written = []
    for name, subset, block in _curves(ctx):
        path = figures / f"pr_{name}.svg"
        path.write_text(_pr_svg(block, f"{subset}, email level"), encoding="utf-8")
        written.append(path)
    for filename, render in (
        ("EVALUATION_REPORT.md", _evaluation_report),
        ("THRESHOLD_POLICY.md", _threshold_policy),
        ("ERROR_ANALYSIS.md", _error_analysis),
        ("UNCERTAINTY_AND_PREVALENCE.md", _uncertainty),
        ("MODEL_CARD.md", _model_card),
    ):
        path = docs_dir / filename
        path.write_text(render(ctx), encoding="utf-8")
        written.append(path)
    return written


def stored_results(policy_dir: Path) -> dict:
    """The policy and its one-shot frozen result, as stored. Reads files only."""
    policy_dir = Path(policy_dir)
    frozen = policy_dir / "test_evaluation.json"
    return {
        "policy": json.loads((policy_dir / "policy.json").read_text(encoding="utf-8")),
        "test": json.loads(frozen.read_text(encoding="utf-8")) if frozen.exists() else None,
    }


def _context(policy_dir: Path) -> dict:
    load = lambda name: json.loads((policy_dir / name).read_text(encoding="utf-8"))  # noqa: E731
    ctx = {
        "policy": load("policy.json"),
        "validation": load("validation_evaluation.json"),
        "test": load("test_evaluation.json") if (policy_dir / "test_evaluation.json").exists() else None,
        "latency": load("latency.json") if (policy_dir / "latency.json").exists() else None,
        "model": json.loads((MODEL_DIR / "model_metadata.json").read_text(encoding="utf-8")),
        "experiments": json.loads((MODEL_DIR / "experiments.json").read_text(encoding="utf-8")),
    }
    api_latency = ARTIFACT_ROOT / "med-api-latency" / ctx["policy"]["policy_version"] / "latency.json"
    ctx["api_latency"] = json.loads(api_latency.read_text(encoding="utf-8")) if api_latency.exists() else None
    ctx["api_latency_path"] = str(api_latency)
    scores_path = policy_dir / "validation_scores.csv"
    ctx["validation_scores"] = pd.read_csv(scores_path, float_precision="round_trip") if scores_path.exists() else None
    ctx["blocks"] = dict(ctx["validation"]["subsets"])
    if ctx["test"]:
        ctx["blocks"].update(ctx["test"]["subsets"])
    ctx["status"] = _ac_status(ctx)
    return ctx


# ---------------------------------------------------------------- formatting


def _f(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _ci(interval, digits: int = 3) -> str:
    if not interval or "low" not in interval:
        return "n/a"
    return f"[{_f(interval['low'], digits)}, {_f(interval['high'], digits)}]"


def _table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _subsets(ctx: dict) -> list[str]:
    order = [SELECTION_SUBSET, DIAGNOSTIC_SUBSET, TEST_PRODUCT, TEST_DIAGNOSTIC]
    return [name for name in order if name in ctx["blocks"]]


def _product_subsets(ctx: dict) -> list[str]:
    return [name for name in (SELECTION_SUBSET, TEST_PRODUCT) if name in ctx["blocks"]]


def _bootstrap_fi(fi: dict) -> str:
    boot = fi["interval_per_1000_bootstrap"]
    if fi["false_interventions"] == 0:
        return f"no upper bound: a zero count resamples to [0.00, 0.00] in all {boot['n_kept']} draws"
    return f"{_ci(boot, 2)} ({boot['n_kept']} draws kept)"


def _fi(point: dict) -> str:
    fi = point["interventions"]
    return f"{fi['false_interventions']} / {fi['legitimate_emails']} = {_f(fi['per_1000_legitimate'], 2)} per 1,000"


def _features_phrase(ctx: dict) -> str:
    ablation = ctx["model"]["ablation"]
    if ablation == "all":
        return "all features, content cosine included"
    if ablation == "behavior_only":
        return "behavior-only features, no content cosine"
    return f"`{ablation}` features"


def _scenario_counts(ctx: dict, subset: str, scenario: str) -> tuple[int, int]:
    for cell in ctx["blocks"][subset]["slices"]["email_by_scenario"]:
        if cell["slice"] == scenario:
            return cell["warned_misdirected"], cell["misdirected"]
    return 0, 0


def _legit_warned(ctx: dict, subset: str, scenarios=("S03", "S05", "S06", "S07")) -> tuple[int, int]:
    warned = total = 0
    for cell in ctx["blocks"][subset]["slices"]["email_by_scenario"]:
        if cell["slice"] in scenarios:
            warned += cell["warned_legitimate"]
            total += cell["legitimate"]
    return warned, total


# ---------------------------------------------------------------- status


def _ac_status(ctx: dict) -> dict:
    test = ctx["test"]
    status = {}
    if not test:
        for key in ("AC01", "AC02"):
            status[key] = ("insufficient evidence", "The frozen test pass has not run.")
        status["AC03"] = ("not met", "The frozen test pass has not run.")
    else:
        point = test["subsets"][TEST_PRODUCT]["policy"]
        fi = point["interventions"]
        upper = fi["interval_per_1000_exact"]["high"]
        rate = fi["per_1000_legitimate"]
        if rate > BUDGET_PER_1000:
            status["AC01"] = ("not met", f"The point estimate {_f(rate, 2)} per 1,000 exceeds the budget.")
        elif upper <= BUDGET_PER_1000:
            status["AC01"] = (
                "met",
                f"On this simulation only: {fi['false_interventions']} false interventions on {fi['legitimate_emails']} legitimate "
                f"`{TEST_PRODUCT}` emails, {_f(rate, 2)} per 1,000, with an exact upper 95% bound of {_f(upper, 2)} per 1,000, within "
                f"the budget of {_f(BUDGET_PER_1000, 0)}. Warnings {fi['warnings']}, blocks {fi['blocks']}, coverage "
                f"{_pct(point['coverage']['fraction'])}, assumed prevalence 0.5%. The validation bound is not independent evidence, "
                "because validation chose the cutoff.",
            )
        else:
            status["AC01"] = (
                "insufficient evidence",
                f"The point estimate is {_f(rate, 2)} per 1,000 ({fi['false_interventions']} of {fi['legitimate_emails']}), "
                f"which meets the budget only provisionally. The exact upper 95% bound is {_f(upper, 2)} per 1,000, above "
                f"{_f(BUDGET_PER_1000, 0)}.",
            )
        email = point["email"]
        rules = test["subsets"][TEST_PRODUCT]["rules_same_budget"]
        low = email["recall_interval_exact"]["low"]
        if email["true_positives"] > 0 and low > 0 and rate <= BUDGET_PER_1000:
            outcomes = test["subsets"][TEST_PRODUCT]["outcomes"]
            warned, missed = _scenario_summary(outcomes["warned_mistakes"]), _scenario_summary(outcomes["missed_mistakes"])
            rules_fi = rules["interventions"]
            within = rules_fi["per_1000_legitimate"] <= BUDGET_PER_1000
            full = sorted(set(warned["scenarios"]) - set(missed["scenarios"]))
            partial = sorted(set(warned["scenarios"]) & set(missed["scenarios"]))
            never = sorted(set(missed["scenarios"]) - set(warned["scenarios"]))
            words = []
            if full:
                words.append(f"met for {', '.join(full)}")
            if partial:
                words.append(f"partly met for {', '.join(partial)}")
            if never:
                words.append(f"not met for {', '.join(never)}")
            status["AC02"] = (
                "; ".join(words) if missed["scenarios"] else "met",
                f"On this simulation only, on `{TEST_PRODUCT}`: {email['true_positives']} of {email['positives']} misdirected emails warned "
                f"({warned['text']}) with {email['false_positives']} false interventions; exact 95% recall interval "
                f"{_ci(email['recall_interval_exact'])}. Missed: {missed['text']}. Always-allow warns on none. The rules policy under "
                f"the same validation rule warned {rules['email']['true_positives']} with {rules_fi['false_interventions']} false "
                f"interventions ({_f(rules_fi['per_1000_legitimate'], 2)} per 1,000), "
                + ("within the budget on this test." if within else "which is outside the budget on this test."),
            )
        else:
            status["AC02"] = ("not met", "The frozen policy did not show recall above always-allow within the budget.")
        status["AC03"] = (
            "met",
            "T_warn was chosen on validation_product_like only, written to policy.json before any test label was read, "
            "and applied once to the frozen test. The policy checksum is stored in test_evaluation.json.",
        )
    status["AC04"] = ("met", "Blocking is disabled. T_block is null and the block count is 0 on every subset.")
    return status


def _curves(ctx: dict):
    for subset in _subsets(ctx):
        yield subset, subset, ctx["blocks"][subset]["ranking"]["email"]


def _pr_svg(curve: dict, title: str) -> str:
    width, height, pad = 360, 300, 44
    inner_w, inner_h = width - 2 * pad, height - 2 * pad

    def x(recall):
        return pad + recall * inner_w

    def y(precision):
        return pad + (1 - precision) * inner_h

    points = sorted(curve.get("points", []), key=lambda item: (item["recall"], -item["precision"]))
    path = " ".join(
        f"{'M' if index == 0 else 'L'}{x(p['recall']):.1f},{y(p['precision']):.1f}" for index, p in enumerate(points)
    )
    marked = curve.get("marked")
    marker = ""
    if marked and marked.get("precision") is not None:
        marker = (
            f'<circle cx="{x(marked["recall"]):.1f}" cy="{y(marked["precision"]):.1f}" r="5" class="mark"/>'
            f'<text x="{x(marked["recall"]) - 6:.1f}" y="{y(marked["precision"]) + 18:.1f}" class="label" text-anchor="end">T_warn</text>'
        )
    ap = curve.get("average_precision")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Precision-recall curve, {title}">
<style>
.axis{{stroke:#666;stroke-width:1}} .curve{{fill:none;stroke:#2b6cb0;stroke-width:2}} .mark{{fill:#c05621}}
text{{font-family:sans-serif;font-size:11px;fill:#333}} .label{{font-size:10px}}
</style>
<rect width="100%" height="100%" fill="#fff"/>
<line x1="{pad}" y1="{pad + inner_h}" x2="{pad + inner_w}" y2="{pad + inner_h}" class="axis"/>
<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad + inner_h}" class="axis"/>
<text x="{pad + inner_w / 2}" y="{height - 10}" text-anchor="middle">Recall</text>
<text x="12" y="{pad + inner_h / 2}" text-anchor="middle" transform="rotate(-90 12 {pad + inner_h / 2})">Precision</text>
<text x="{pad}" y="{pad + inner_h + 14}" text-anchor="middle">0</text><text x="{pad + inner_w}" y="{pad + inner_h + 14}" text-anchor="middle">1</text>
<text x="{pad - 8}" y="{pad + 4}" text-anchor="end">1</text><text x="{pad - 8}" y="{pad + inner_h + 4}" text-anchor="end">0</text>
<text x="{width / 2}" y="18" text-anchor="middle">{title}: AP {_f(ap)} ({curve.get('positives', 0)} pos / {curve.get('n', 0)})</text>
<path d="{path}" class="curve"/>
{marker}
</svg>
"""


# ---------------------------------------------------------------- shared text


def _scenario_summary(rows: list[dict]) -> dict:
    """Scenario counts and recipient-count range for a list of email outcomes."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["scenario_id"]] = counts.get(row["scenario_id"], 0) + 1
    if not rows:
        return {"scenarios": [], "text": "none"}
    sizes = [row["n_recipients"] for row in rows]
    if min(sizes) == max(sizes):
        size = f"{min(sizes)} recipient{'s' if min(sizes) != 1 else ''} each"
    else:
        size = f"{min(sizes)} to {max(sizes)} recipients"
    scores = [row["email_risk"] for row in rows]
    low, high = f"{min(scores):.4g}", f"{max(scores):.4g}"
    score = f"risk score {low}" if low == high else f"risk scores {low} to {high}"
    listed = ", ".join(f"{key} {value}" for key, value in sorted(counts.items()))
    return {"scenarios": list(counts), "text": f"{listed}; {size}; {score}"}


def _s01_s04_line(ctx: dict) -> str:
    """Per-subset warned/missed counts for S01, S04, and S11, from the stored slices."""
    pieces = []
    for subset in _subsets(ctx):
        cells = []
        for scenario in ("S01", "S04", "S11"):
            warned, total = _scenario_counts(ctx, subset, scenario)
            if total:
                cells.append(f"{scenario} {warned} of {total} warned")
        pieces.append(f"`{subset}`: {', '.join(cells) if cells else 'none present'}")
    return "; ".join(pieces)


def _shortcut_block(ctx: dict) -> str:
    runs = {run["name"]: run for run in ctx["experiments"]["runs"]}
    model = ctx["model"]
    selected = runs.get(model["run_name"], {})
    behavior = runs.get(f"logistic_behavior_only_{model['config'].get('class_weight', 'unweighted')}") or runs.get("logistic_behavior_only_unweighted")
    audit = (ctx["experiments"].get("eligibility") or {}).get("audit") or {}
    cosine = (audit.get("content_separation") or {}).get("content_cosine")
    burst = ctx["blocks"][SELECTION_SUBSET]["recency_burst"]
    fc = ctx["blocks"][SELECTION_SUBSET]["first_contact"]
    product_pos = ctx["blocks"][SELECTION_SUBSET]["policy"]["email"]["positives"]
    test_pos = ctx["blocks"][TEST_PRODUCT]["policy"]["email"]["positives"] if TEST_PRODUCT in ctx["blocks"] else None
    content_line = (
        f"- **Content signal.** The scorer uses {_features_phrase(ctx)}. On train, content cosine alone separates mistakes from ordinary mail with separation {_f(cosine)} (the eligibility audit flags a feature only beyond 0.95). "
        if cosine is not None
        else "- **Content signal.** "
    )
    if behavior and model["ablation"] == "all":
        content_line += (
            f"The same-family behavior-only model has product-like validation email average precision {_f(behavior['validation_product_like']['email']['average_precision'])} "
            f"against {_f(selected.get('validation_product_like', {}).get('email', {}).get('average_precision'))} for the scorer. "
        )
    content_line += f"S01, S04, and S11 outcomes by subset: {_s01_s04_line(ctx)}. The drafts are listed in the [error analysis](ERROR_ANALYSIS.md)."
    lines = [
        "Read every recall figure in this phase next to these limits of the synthetic data and the frozen scorer:",
        "",
        content_line,
        f"- **Five-minute recency.** {burst['legitimate_under_5_minutes']} of {burst['legitimate_rows']} legitimate recipient rows on `{SELECTION_SUBSET}` had earlier mail between the sender and that recipient under five minutes before the draft; {burst['unintended_under_5_minutes']} of {burst['unintended_rows']} unintended rows did.",
        f"- **First contacts.** Rewriting the {fc['unintended_rows']} unintended `{SELECTION_SUBSET}` rows as first contacts (no pair history, no pair text) moves their median risk score from {_f(fc['median_before'], 4)} to {_f(fc['median_after'], 4)}; {fc['flagged_before']} are flagged as stored and {fc['flagged_after_rewrite']} after the rewrite. The {fc['novel_intended_rows']} intended first-contact rows reach a highest risk score of {_f(fc['novel_intended_max_score'], 5)}, just below `T_warn`, and none is flagged. Legitimate first contacts are among the highest-scoring legitimate rows; the high cutoff, not the score, keeps them allowed.",
        f"- **Few positives.** `{SELECTION_SUBSET}` has {product_pos} misdirected emails"
        + (f" and `{TEST_PRODUCT}` has {test_pos}" if test_pos is not None else "")
        + ". Recall intervals are wide.",
        f"- **Weak regularization.** The scorer is logistic regression with `C = {model['config']['C']:g}`"
        + (", the top edge of its training grid" if selected.get("grid_edge") == "top" else "")
        + ". Coefficients on overlapping counts are not separate effects.",
    ]
    return "\n".join(lines)


def _status_table(ctx: dict) -> str:
    rows = [[key, f"**{word}**", reason] for key, (word, reason) in ctx["status"].items()]
    return _table(["Criterion", "Status", "Evidence"], rows)


# ---------------------------------------------------------------- documents


def _evaluation_report(ctx: dict) -> str:
    policy = ctx["policy"]
    parts = [
        "# Phase 5 — Evaluation report",
        "",
        f"This report evaluates the frozen logistic **risk score** (`{policy['model_version']}`, run `{policy['model_run_name']}`, {_features_phrase(ctx)}) on dataset `{policy['dataset_version']}` with features `{policy['feature_spec_version']}`, under warning policy `{policy['policy_version']}`. Scores are risk scores, not probabilities: no calibrator was fit. `T_warn = {policy['T_warn']:.6f}` was chosen on `{SELECTION_SUBSET}` only. The frozen test subsets were scored once, after `policy.json` was written.",
        "",
        "Email risk is the maximum recipient risk score. An email warns when its risk score is at or above `T_warn`. Blocking is disabled.",
        "",
        "## Acceptance status",
        "",
        _status_table(ctx),
        "",
        f"AC05 is measured at the API boundary in Phase 6; see [latency](#latency-ac05). AC06 is partial here: maximum aggregation, threshold equality, and flagging every recipient at or above `T_warn` are implemented and tested; duplicate-address merging is in the Phase 6 request normalizer. AC07: {_ac07_text(ctx)} AC08 and AC09 are Phase 6 behaviors and are not assessed in this report.",
        "",
        "## Operating points at the frozen cutoff",
        "",
    ]
    rows = []
    for subset in _subsets(ctx):
        block = ctx["blocks"][subset]
        for label, key in (("policy", "policy"), ("rules, same validation rule", "rules_same_budget"), ("always-allow", "always_allow")):
            point = block[key]
            email = point["email"]
            rows.append(
                [
                    f"`{subset}`",
                    label,
                    f"{email['true_positives']} / {email['positives']}",
                    _f(email["recall"]),
                    _f(email["precision"]),
                    _fi(point),
                    point["interventions"]["warnings"],
                    point["interventions"]["blocks"],
                    f"{point['recipient']['true_positives']} / {point['recipient']['positives']}",
                    _pct(point["attribution"]["fraction"]),
                    _pct(point["coverage"]["fraction"]),
                ]
            )
    parts.append(
        _table(
            ["Subset", "Scorer", "Warned mistakes", "Email recall", "Email precision", "False interventions", "Warnings", "Blocks", "Flagged unintended recipients", "Mistakes with a flagged unintended recipient", "Coverage"],
            rows,
        )
    )
    rules_cutoff = ctx["validation"]["rules_same_budget"]["cutoff"]
    caveats = []
    for subset in _product_subsets(ctx):
        row = next(r for r in ctx["blocks"][subset]["prevalence"] if abs(r["prevalence"] - 0.005) < 1e-12)
        caveats.append(f"{_f(row['precision_at_fpr_upper'])} on `{subset}`")
    parts += [
        "",
        f"Email precision of 1.000 on a policy row is forced by zero observed false warnings; it is not an estimate of precision in use. At the exact upper 95% false-positive rate and the assumed 0.5% prevalence, precision would be {' and '.join(caveats)}. See [uncertainty and prevalence](UNCERTAINTY_AND_PREVALENCE.md).",
        "",
        f"The confidence bound on `{SELECTION_SUBSET}` is not independent confirmation of the budget, because that subset selected the cutoff. Only the one `{TEST_PRODUCT}` pass can support or fail AC01.",
        "",
        f"The rules policy uses the same selection rule on `{SELECTION_SUBSET}` and gets cutoff {_f(rules_cutoff, 4)}. It is a comparison for AC02 only. Always-allow is the floor.",
        "",
        "## Confusion counts",
        "",
    ]
    rows = []
    for subset in _subsets(ctx):
        point = ctx["blocks"][subset]["policy"]
        email, recipient = point["email"], point["recipient"]
        rows.append(
            [f"`{subset}`", email["true_positives"], email["false_positives"], email["false_negatives"], email["true_negatives"], recipient["true_positives"], recipient["false_positives"], recipient["false_negatives"], recipient["true_negatives"], _f(recipient["recall"])]
        )
    parts.append(_table(["Subset", "Email TP", "Email FP", "Email FN", "Email TN", "Recipient TP", "Recipient FP", "Recipient FN", "Recipient TN", "Recipient recall"], rows))
    parts += ["", "## Intervals", ""]
    rows = []
    for subset in _subsets(ctx):
        point = ctx["blocks"][subset]["policy"]
        fi = point["interventions"]
        independent = subset in (SELECTION_SUBSET, TEST_PRODUCT)
        rows.append(
            [
                f"`{subset}`",
                _ci(fi["interval_per_1000_exact"], 2) if independent else "not valid (shared families)",
                _bootstrap_fi(fi),
                _ci(point["email"]["recall_interval_exact"]) if independent else "not valid (shared families)",
                f"{_ci(point['email']['recall_interval_bootstrap'])} ({point['email']['recall_interval_bootstrap']['n_kept']} draws kept)",
            ]
        )
    parts.append(_table(["Subset", "False interventions per 1,000, exact 95%", "Same, family bootstrap", "Email recall, exact 95%", "Email recall, family bootstrap"], rows))
    parts += [
        "",
        "The family bootstrap of a zero count is always [0, 0]. It says nothing about an upper bound. The exact interval treats emails as independent, which holds on product-like subsets because each family has one draft. See [uncertainty and prevalence](UNCERTAINTY_AND_PREVALENCE.md).",
        "",
        "## Precision–recall curves",
        "",
        "Average precision is carried forward from the frozen risk score. The marked point is the frozen cutoff.",
        "",
    ]
    rows = []
    for subset in _subsets(ctx):
        ranking = ctx["blocks"][subset]["ranking"]
        rows.append([f"`{subset}`", _f(ranking["email"]["average_precision"]), _ci(ranking["email"]["average_precision_bootstrap"]), _f(ranking["recipient"]["average_precision"]), f"![PR curve](figures/pr_{subset}.svg)"])
    parts.append(_table(["Subset", "Email AP", "Email AP, family bootstrap", "Recipient AP", "Curve"], rows))
    parts += ["", "## Slices", "", "Counts are at the frozen cutoff. A warning on S03, S05, S06, or S07 is a false positive.", ""]
    for subset in _subsets(ctx):
        sl = ctx["blocks"][subset]["slices"]
        parts += [f"### `{subset}`", ""]
        parts.append(
            _table(
                ["Recipient slice", "Rows", "Unintended", "Flagged unintended", "Intended", "Flagged intended"],
                [[f"{name}: {c['slice']}", c["rows"], c["unintended"], c["flagged_unintended"], c["intended"], c["flagged_intended"]] for name, key in (("internal", "recipient_by_internal"), ("contact", "recipient_by_familiarity")) for c in sl[key]],
            )
        )
        parts.append("")
        parts.append(
            _table(
                ["Email slice", "Emails", "Misdirected", "Warned misdirected", "Legitimate", "Warned legitimate", "Families"],
                [[f"{name}: {c['slice']}", c["emails"], c["misdirected"], c["warned_misdirected"], c["legitimate"], c["warned_legitimate"], c["families"]] for name, key in (("recipients", "email_by_recipient_count"), ("unintended recipients", "email_by_unintended_count")) for c in sl[key]],
            )
        )
        parts.append("")
        parts.append(
            _table(
                ["Scenario", "Emails", "Misdirected", "Warned misdirected (scenario recall)", "Legitimate", "Warned legitimate", "Families"],
                [[c["slice"], c["emails"], c["misdirected"], f"{c['warned_misdirected']} / {c['misdirected']}" if c["misdirected"] else "—", c["legitimate"], c["warned_legitimate"], c["families"]] for c in sl["email_by_scenario"]],
            )
        )
        parts.append("")
    parts += ["## Legitimate first contacts and the paired check", ""]
    rows = []
    for subset in _subsets(ctx):
        fc = ctx["blocks"][subset]["first_contact"]
        rows.append([f"`{subset}`", fc["novel_intended_rows"], fc["novel_intended_flagged"], _f(fc["novel_intended_max_score"], 5), fc["unintended_rows"], fc["flagged_before"], fc["flagged_after_rewrite"], _f(fc["median_before"], 4), _f(fc["median_after"], 4)])
    parts.append(_table(["Subset", "Intended first-contact rows", "Flagged", "Max risk score", "Unintended rows", "Flagged as stored", "Flagged after first-contact rewrite", "Median before", "Median after"], rows))
    parts += [
        "",
        f"The rewrite removes pair history and pair text from each unintended row. AC07: {_ac07_text(ctx)}",
        "",
        "## Calibration",
        "",
        f"`calibration: {policy['calibration']}`. {policy['calibration_reason']}",
        "",
        _table(
            ["Risk score bin", "Rows", "Mean risk score", "Observed unintended fraction"],
            [[f"{_f(b['bin_low'], 1)}–{_f(b['bin_high'], 1)}", b["rows"], _f(b["mean_risk_score"]), _f(b["observed_unintended_fraction"])] for b in ctx["validation"]["reliability_validation_diagnostic"]],
        ),
        "",
        "This table is on `validation_diagnostic`, which is not the 0.5% operating mix. It is a shape check. Most rows fall in the lowest and highest bins; read each bin's row count before its fraction.",
        "",
        "## Latency (AC05)",
        "",
        _latency_text(ctx),
        "",
        "## Synthetic shortcuts",
        "",
        _shortcut_block(ctx),
        "",
    ]
    return "\n".join(parts)


def _latency_text(ctx: dict) -> str:
    lat = ctx.get("api_latency")
    if not lat:
        return f"Not measured for this policy yet. The API boundary measurement is written to `{ctx['api_latency_path']}` by `python -m med_api latency`."
    return (
        f"Measured once at the API boundary for this policy bundle (`{ctx['api_latency_path']}`): {lat['measured_calls']} `POST /assess` calls "
        f"on `{lat['subset']}` after {lat['warmup_calls']} warm-up calls, one in flight. Client p50 {_f(lat['client_p50_ms'], 2)} ms, "
        f"p95 {_f(lat['client_p95_ms'], 2)} ms against a {lat['target_p95_ms']:.0f} ms target: AC05 **{lat['ac05']}** on this machine. "
        "Details, workload, and hardware are in [the Phase 6 scoring flow](../phase_6/SCORING_FLOW.md#latency-ac05)."
    )


def _ac07_text(ctx: dict) -> str:
    parts = []
    for subset in _subsets(ctx):
        warned, total = _legit_warned(ctx, subset)
        s11_warned, s11_total = _scenario_counts(ctx, subset, "S11")
        parts.append(f"`{subset}` {warned} of {total} S03/S05/S06/S07 emails warned, S11 {s11_warned} of {s11_total} warned")
    fc = ctx["blocks"][SELECTION_SUBSET]["first_contact"]
    return (
        "**insufficient evidence**. Wrong interventions on the legitimate-novelty scenarios: "
        + "; ".join(parts)
        + f". Those allows are the desired outcome, but legitimate first contacts score close to the cutoff (highest {_f(fc['novel_intended_max_score'], 5)} on `{SELECTION_SUBSET}` against `T_warn` {_f(ctx['policy']['T_warn'], 5)}), "
        "and removing pair history from a familiar mistake raises its risk score. The report cannot show that novelty is weighed only with other signals rather than setting a score near the cutoff by itself."
    )


def _threshold_policy(ctx: dict) -> str:
    policy = ctx["policy"]
    selection = policy["selection"]
    chosen = selection["chosen"]
    conf = policy["validation_confusion"]
    return "\n".join(
        [
            "# Phase 5 — Threshold policy",
            "",
            f"Policy `{policy['policy_version']}` applies to model `{policy['model_version']}` (run `{policy['model_run_name']}`), features `{policy['feature_spec_version']}`, and dataset `{policy['dataset_version']}`. It lives in `artifacts/{policy['policy_version']}/policy.json`.",
            "",
            "## Decision rule",
            "",
            _table(["Item", "Rule"], [[key, value] for key, value in policy["decision_rule"].items()]),
            "",
            f"`T_warn = {policy['T_warn']!r}`. `blocking_enabled: false`. `T_block: null`. The decision function never returns `block`. Scores are **risk scores**; `calibration: {policy['calibration']}`.",
            "",
            "## Selection",
            "",
            selection["rule"],
            "",
            _table(
                ["Item", "Value"],
                [
                    ["Selection subset", f"`{selection['subset']}`, email level"],
                    ["Candidates", selection["n_candidates"]],
                    ["Candidates with 0 false interventions", selection["zero_false_intervention_candidates"]],
                    ["Chosen recall", f"{chosen['true_positives']} / {conf['email']['positives']} = {_f(chosen['recall'])}"],
                    ["Chosen false interventions", f"{chosen['false_interventions']} / {conf['email']['legitimate']}"],
                    ["Tied candidates", len(selection["tied_candidates"])],
                    ["Highest legitimate email risk score", _f(selection["highest_legitimate_email_risk"], 6)],
                ],
            ),
            "",
            f"`T_warn` equals the risk score of the lowest-scoring warned mistake on validation. The highest legitimate email scores {_f(selection['highest_legitimate_email_risk'], 6)}, {policy['T_warn'] - selection['highest_legitimate_email_risk']:.2e} below it. A small shift in legitimate scores on new data would add false warnings.",
            "",
            "## Budget",
            "",
            _table(["Item", "Definition"], [[key, value] for key, value in policy["budget"].items()]),
            "",
            f"`{SELECTION_SUBSET}` has {conf['email']['legitimate']} legitimate emails, so one false warning is {_f(1000 / conf['email']['legitimate'], 3)} per 1,000. Its confidence bound is not independent confirmation of the budget, because this subset selected the cutoff.",
            "",
            "## Calibration",
            "",
            f"`calibration: {policy['calibration']}`. {policy['calibration_reason']}",
            "",
            "## Scoring-path parity",
            "",
            _parity_text(policy),
            "",
            "## Validation confusion at the cutoff",
            "",
            _table(
                ["Level", "n", "Positives", "TP", "FP", "FN", "TN"],
                [[level, c["n"], c["positives"], c["true_positives"], c["false_positives"], c["false_negatives"], c["true_negatives"]] for level, c in (("email", conf["email"]), ("recipient", conf["recipient"]))],
            ),
            "",
            f"Warnings: {conf['warnings']}. Blocks: {conf['blocks']}.",
            "",
            "## Load checks",
            "",
            "The decision function loads `policy.json` with the model bundle and refuses to decide when:",
            "",
            "- the policy file is missing, unreadable, or lacks a required field",
            "- the policy, model, or feature-spec version differs from the installed one, or the model run name differs",
            "- the SHA-256 of `model.joblib` or of the feature `artifact_manifest.json` differs from the value in the policy",
            "- blocking is enabled, `T_block` is set, `T_warn` is not a finite number, or the policy claims calibrated scores",
            "",
            "Any of these, or a feature or model error while scoring, returns `unable_to_assess` with no decision and no risk score. It never returns allow.",
            "",
            "## Checksums",
            "",
            _table(["File", "SHA-256"], [[name, f"`{value}`"] for name, value in policy["checksums"].items()]),
            "",
            f"{policy['statement']}",
            "",
            "`validation_scores.csv` stores email risk scores with 17 significant digits and a `warned` column computed from the in-memory comparison. Read it with round-trip float parsing (for pandas, `float_precision=\"round_trip\"`): the lowest warned validation mistake scores exactly `T_warn`, and a lossy parse can move it below the cutoff.",
            "",
        ]
    )


def _parity_text(policy: dict) -> str:
    parity = policy.get("scoring_path_parity")
    if not parity:
        return "No scoring-path parity record is stored with this policy."
    lines = [
        f"`T_warn` was selected on {parity['selected_on']}. Before `policy.json` was written, every `{parity['subset']}` draft was scored again with {parity['compared_with']}.",
        "",
        _table(
            ["Item", "Value"],
            [
                ["Drafts compared", parity["drafts"]],
                ["Identical decisions", f"{parity['identical_decisions']} / {parity['drafts']}"],
                ["Largest email risk score difference", f"{parity['max_abs_email_risk_difference']:.2e} (bound {parity['bound']:g})"],
            ]
            + [[f"Draft at `T_warn`: `{item['draft_id']}`", f"batch {item['batch']!r}, single-draft {item['single']!r}, {item['decision']}"] for item in parity["drafts_at_T_warn"]],
        ),
        "",
        "Scores are not required to be bit-identical across the two paths, because summation order can differ. Decisions are required to match on every draft, and they do.",
    ]
    return "\n".join(lines)


def _example_rows(examples: dict) -> list[list]:
    labels = {
        "allowed_ordinary": "Allowed ordinary email",
        "warned_mistake": "Warned mistake",
        "missed_mistake": "Missed mistake",
        "legitimate_first_contact": "Legitimate first contact",
    }
    rows = []
    for key, label in labels.items():
        item = examples.get(key)
        if item is None:
            rows.append([label, "none in this subset", "", "", "", ""])
            continue
        rows.append([label, f"`{item['draft_id']}`", item["scenario_id"], f"{item['email_risk']:.6g}", item["decision"], f"\"{item['subject']}\""])
    return rows


def _missed_note(ctx: dict) -> str:
    lines = []
    for subset in (SELECTION_SUBSET, DIAGNOSTIC_SUBSET):
        outcomes = ctx["blocks"][subset]["outcomes"]
        lines.append(f"- `{subset}`: warned {_scenario_summary(outcomes['warned_mistakes'])['text']}. Missed {_scenario_summary(outcomes['missed_mistakes'])['text']}.")
    scores = ctx.get("validation_scores")
    product_missed = ctx["blocks"][SELECTION_SUBSET]["outcomes"]["missed_mistakes"]
    if scores is not None and product_missed:
        worst = max(row["email_risk"] for row in product_missed)
        above = int(((scores["email_risk"] > worst) & ~scores["misdirected"].astype(bool)).sum())
        lines.append(
            f"- On `{SELECTION_SUBSET}` the highest missed mistake scores {worst:.6g}, and {above} legitimate emails score above it. The selection rule cannot warn on it without a false warning."
        )
    fc = ctx["blocks"][SELECTION_SUBSET]["first_contact"]
    lines += [
        "",
        f"The zero-false-warning rule puts `T_warn` at {ctx['policy']['T_warn']:.6g}, above every legitimate validation email. Legitimate first contacts are among the highest-scoring legitimate emails (up to {fc['novel_intended_max_score']:.6g}), so they set how high the cutoff must go. Mistakes that score below that band, including every S01, S04, and S11 validation mistake, are allowed.",
    ]
    return "\n".join(lines)


def _validation_warned(ctx: dict) -> set[str]:
    found = set()
    for subset in (SELECTION_SUBSET, DIAGNOSTIC_SUBSET):
        found.update(row["scenario_id"] for row in ctx["blocks"][subset]["outcomes"]["warned_mistakes"])
    return found


def _error_analysis(ctx: dict) -> str:
    parts = [
        "# Phase 5 — Error analysis",
        "",
        f"Examples use the frozen policy (`T_warn = {ctx['policy']['T_warn']:.6f}`). Scores are risk scores. Subjects are fictional and shortened.",
        "",
        "## Validation examples",
        "",
    ]
    for subset, examples in ctx["validation"]["examples_validation"].items():
        parts += [f"### `{subset}`", "", _table(["Case", "Draft", "Scenario", "Email risk score", "Decision", "Subject"], _example_rows(examples)), ""]
    parts += [
        _missed_note(ctx),
        "",
    ]
    for subset in _subsets(ctx):
        outcomes = ctx["blocks"][subset]["outcomes"]
        parts += [f"### Missed and false warnings, `{subset}`", ""]
        rows = [["missed", f"`{r['draft_id']}`", r["scenario_id"], f"{r['email_risk']:.6g}", r["n_recipients"]] for r in outcomes["missed_mistakes"]]
        rows += [["false warning", f"`{r['draft_id']}`", r["scenario_id"], f"{r['email_risk']:.6g}", r["n_recipients"]] for r in outcomes["false_warnings"]]
        parts.append(_table(["Outcome", "Draft", "Scenario", "Email risk score", "Recipients"], rows) if rows else "No missed mistakes and no false warnings.")
        parts.append("")
    if ctx["test"]:
        missed = {}
        for subset in TEST_SUBSETS:
            for r in ctx["blocks"][subset]["outcomes"]["missed_mistakes"]:
                missed[r["scenario_id"]] = missed.get(r["scenario_id"], 0) + 1
        warned = {}
        for subset in TEST_SUBSETS:
            for r in ctx["blocks"][subset]["outcomes"]["warned_mistakes"]:
                warned[r["scenario_id"]] = warned.get(r["scenario_id"], 0) + 1
        fw = sum(len(ctx["blocks"][s]["outcomes"]["false_warnings"]) for s in TEST_SUBSETS)
        parts += [
            "## Note on the single test pass",
            "",
            f"This is inspection after the one test pass. It does not permit moving the cutoff. Across `{TEST_PRODUCT}` and `{TEST_DIAGNOSTIC}`, missed mistakes by scenario: {', '.join(f'{k} {v}' for k, v in sorted(missed.items())) or 'none'}. Warned mistakes by scenario: {', '.join(f'{k} {v}' for k, v in sorted(warned.items())) or 'none'}. False warnings: {fw}. Scenarios warned on test but never warned on validation: {', '.join(sorted(set(warned) - _validation_warned(ctx))) or 'none'}. Scenarios missed on test and never warned on validation: {', '.join(sorted(set(missed) - set(warned) - _validation_warned(ctx))) or 'none'}.",
            "",
        ]
    parts += ["## Synthetic shortcuts", "", _shortcut_block(ctx), ""]
    return "\n".join(parts)


def _bound_reach(ctx: dict) -> str:
    pieces = []
    for subset in _product_subsets(ctx):
        fi = ctx["blocks"][subset]["policy"]["interventions"]
        reach = fi["zero_count_upper_per_1000"] <= BUDGET_PER_1000
        pieces.append(
            f"With {fi['legitimate_emails']} legitimate emails on `{subset}`, zero false warnings give an upper bound of {_f(fi['zero_count_upper_per_1000'], 2)} per 1,000, "
            + ("within the budget." if reach else "above the budget, so no result on that subset could support the claim.")
        )
    return " ".join(pieces)


def _uncertainty(ctx: dict) -> str:
    parts = [
        "# Phase 5 — Uncertainty and prevalence",
        "",
        "## Interval methods",
        "",
        f"- **Family bootstrap.** {ctx['validation']['bootstrap']['n_resamples']} draws, seed {ctx['validation']['bootstrap']['seed']}, resampling `family_id` clusters of emails; the 2.5 and 97.5 percentiles are reported with the number of draws kept. Diagnostic families contain several drafts, so only this interval respects their dependence. A zero false-intervention count bootstraps to [0, 0] in every draw, which is not an upper bound, so the diagnostic false-intervention rate has no valid upper bound in this report. The diagnostic recall bootstrap is still reported.",
        "- **Exact binomial (Clopper–Pearson).** Used for the false-intervention rate and recall on product-like subsets, where each family has one draft and emails are independent. It gives a positive upper bound for a zero count. The AC01 strong claim uses this upper bound.",
        "",
        "## The sample-size limit on AC01",
        "",
    ]
    rows = []
    for subset in _product_subsets(ctx):
        fi = ctx["blocks"][subset]["policy"]["interventions"]
        rows.append([f"`{subset}`", fi["legitimate_emails"], _f(1000 / fi["legitimate_emails"], 3), fi["false_interventions"], _f(fi["per_1000_legitimate"], 2), _f(fi["interval_per_1000_exact"]["high"], 2), _f(fi["zero_count_upper_per_1000"], 2)])
    parts.append(_table(["Subset", "Legitimate emails", "One false warning, per 1,000", "False warnings", "Rate per 1,000", "Exact upper 95%", "Upper 95% if zero"], rows))
    parts += [
        "",
        f"The budget is {_f(BUDGET_PER_1000, 0)} false intervention per 1,000 legitimate emails. A point estimate within the budget is provisional; the strong AC01 claim needs the exact upper bound at or below the budget. {_bound_reach(ctx)} Only the `{TEST_PRODUCT}` pass counts for AC01, because `{SELECTION_SUBSET}` chose the cutoff.",
        "",
        "## Prevalence sensitivity",
        "",
        "0.5% is a simulation assumption. Precision at the frozen cutoff is computed from the product-like true-positive rate and false-positive rate, at several assumed prevalences. When the observed false-positive rate is 0, point precision is 1.0 at every prevalence, which overstates it; the second column uses the exact upper false-positive rate instead. Neither column is chosen as the result.",
        "",
    ]
    for subset in _product_subsets(ctx):
        rows = [[_pct(r["prevalence"]), _f(r["tpr"]), _f(r["fpr_point"], 5), _f(r["precision_point"]), _f(r["fpr_upper"], 5), _f(r["precision_at_fpr_upper"])] for r in ctx["blocks"][subset]["prevalence"]]
        parts += [f"### `{subset}`", "", _table(["Prevalence", "TPR", "FPR", "Precision", "FPR upper 95%", "Precision at FPR upper"], rows), ""]
    parts += [
        "Diagnostic-set rates are not product-like prevalence results and are not used in this table. Train precision at the 10% training mix is not an operating point.",
        "",
    ]
    return "\n".join(parts)


def _model_card(ctx: dict) -> str:
    policy = ctx["policy"]
    model = ctx["model"]
    rows = []
    for subset in _subsets(ctx):
        point = ctx["blocks"][subset]["policy"]
        email = point["email"]
        rows.append([f"`{subset}`", f"{email['true_positives']} / {email['positives']}", _fi(point), _f(ctx["blocks"][subset]["ranking"]["email"]["average_precision"]), email["n"]])
    return "\n".join(
        [
            "# Phase 5 — Model card",
            "",
            "## Intended use",
            "",
            "Rank recipients of a fictional draft email by **risk score** of being unintended, and warn before a simulated send when the email risk score reaches the frozen cutoff. The corpus is synthetic, on reserved `.example` domains. This card describes a simulation, not a deployable product.",
            "",
            "## Out of scope",
            "",
            "Real mail, blocking, probability interpretation of scores, reason-code text, duplicate-address merging, distribution lists, and any prevalence other than the simulated mix.",
            "",
            "## Frozen bundle",
            "",
            _table(
                ["Component", "Version"],
                [
                    ["Dataset", f"`{policy['dataset_version']}`"],
                    ["Features", f"`{policy['feature_spec_version']}`"],
                    ["Model", f"`{policy['model_version']}` (`{policy['model_run_name']}`, logistic regression, `C = {model['config']['C']:g}`, {model['config']['class_weight']}, {_features_phrase(ctx)})"],
                    ["Policy", f"`{policy['policy_version']}`, `T_warn = {policy['T_warn']:.6f}`, blocking disabled, calibration not fit"],
                    ["Seed", model["seed"]],
                ],
            ),
            "",
            "## Metrics at the frozen cutoff",
            "",
            _table(["Subset", "Warned mistakes", "False interventions", "Email AP", "Emails"], rows),
            "",
            "Diagnostic subsets are scenario challenge sets and not the operating mix. Intervals are in the [evaluation report](EVALUATION_REPORT.md).",
            "",
            "## Acceptance status",
            "",
            _status_table(ctx),
            "",
            "## Failure modes",
            "",
            f"- Mistaken first contacts (S11), lookalike replacements (S01), and familiar-recipient, unusual-topic mistakes (S04) are allowed at the frozen cutoff: {_s01_s04_line(ctx)}.",
            "- Legitimate first contacts score just below the cutoff. A small drift in legitimate scores, or a new kind of legitimate first contact, would add false warnings.",
            "- The cutoff sits just above the highest legitimate validation score, so it is tight by construction.",
            "- Content cosine is an input. Off-topic mistakes are partly caught because the generator wrote them off-topic.",
            "- An address that is not in the directory is `unable_to_assess`, not a warning. A missing or mismatched policy or model also returns `unable_to_assess`; it never allows.",
            "",
            _shortcut_block(ctx),
            "",
        ]
    )
