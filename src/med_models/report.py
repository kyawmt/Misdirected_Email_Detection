"""Write the Phase 4 documents from experiment output."""

from __future__ import annotations

from med_models.version import DATASET_VERSION, FEATURE_SPEC_VERSION, MODEL_VERSION, N_BOOTSTRAP, SEED


def write_documents(directory, payload: dict, metadata: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    runs = payload["runs"]
    selected = _run(runs, payload["selected"])
    (directory / "EXPERIMENT_TABLE.md").write_text(_experiment_table(payload, runs), encoding="utf-8")
    (directory / "COMPARISON.md").write_text(_comparison(runs), encoding="utf-8")
    (directory / "ABLATIONS.md").write_text(_ablations(runs), encoding="utf-8")
    (directory / "MODEL_ARTIFACT.md").write_text(_artifact_doc(metadata), encoding="utf-8")
    (directory / "DECISION_RECORD.md").write_text(_decision(payload, selected, runs), encoding="utf-8")


def _experiment_table(payload: dict, runs: list[dict]) -> str:
    lines = [
        f"# Phase 4 — Experiment table",
        "",
        f"Model bundle `{MODEL_VERSION}`. Dataset `{DATASET_VERSION}`. Features `{FEATURE_SPEC_VERSION}`. Seed `{SEED}`.",
        "",
        "C and tree settings were chosen by mean email-level average precision on expanding chronological folds inside `train`. Each row below was then fit on all of `train` and scored once on validation. No frozen test subset was scored. No threshold was chosen.",
        "",
        f"Bootstrap intervals resample `family_id` clusters, {N_BOOTSTRAP} draws, seed `{SEED}`. The interval is the 2.5 and 97.5 percentiles of draws that contain both classes.",
        "",
        "## Folds",
        "",
        _fold_table(payload["folds"]),
        "",
        "## Validation runs",
        "",
        _run_table(runs),
        "",
        f"Average precision is the area under the precision-recall curve. Email risk is the maximum recipient score. An email is positive when any recipient was unintended. `validation_product_like` has {_positives(runs)} misdirected emails, so its intervals are wide. Diagnostic rates are not 0.5% prevalence results.",
        "",
        "## Train cross-validation of the chosen settings",
        "",
        _cv_table(runs),
        "",
    ]
    return "\n".join(lines)


def _comparison(runs: list[dict]) -> str:
    lines = [
        "# Phase 4 — Baseline and challenger comparison",
        "",
        "Always-allow scores every recipient 0. The rules score is the mean of three behavioral checks and cannot reach 1 from one check. Logistic regression and one depth-limited tree are the learned models. Fusion is an equal-weight sum of the three rule checks plus a content term. It is not a behavior-only model.",
        "",
        "The tree is a single decision tree rather than a boosted ensemble so the novelty split can be read. Its depth and leaf size are the only tuned settings. Class weight for the tree is fixed at balanced.",
        "",
        _run_table([run for run in runs if run["ablation"] in {"behavior_only", "none", "fusion", "all"} and _primary(run)]),
        "",
        "Behavior-only rows drop `content_cosine`, `content_similarity_observed`, and `pair_text_message_count`. All-features rows keep them. Whether an all-features model may be selected is decided by the recorded eligibility checks in the [decision record](DECISION_RECORD.md), not by this table. Unobserved recency is imputed with the training median and then log-transformed, so the 3650-day fallback is not a raw input.",
        "",
    ]
    return "\n".join(lines)


def _ablations(runs: list[dict]) -> str:
    lines = [
        "# Phase 4 — Ablations",
        "",
        "Each learned ablation was tuned on `train` only, then scored once. Behavior-only drops the three content-cosine columns. Drop-content drops every text-derived column, draft-length flags included. Content-only keeps only text-derived columns. `behavior_recency_floor` floors recency at one day. `behavior_drop_rate` removes `pair_outbound_rate_per_day`. Neither diagnostic enters model selection.",
        "",
        _run_table([run for run in runs if run["kind"] in {"logistic", "tree"}]),
        "",
        "## Behavior-only against all features",
        "",
        _gap_table(runs),
        "",
    ]
    return "\n".join(lines)


def _artifact_doc(metadata: dict) -> str:
    columns = ", ".join(f"`{name}`" for name in metadata["feature_columns"])
    return "\n".join(
        [
            "# Phase 4 — Selected model artifact",
            "",
            f"Bundle `{metadata['model_version']}` scores one risk number per recipient. The number is a risk score. It was not calibrated, and no warning or block threshold is stored.",
            "",
            "## Files",
            "",
            "| File | Role |",
            "| --- | --- |",
            "| `model.joblib` | Fitted scorer and metadata. Loading does not refit. |",
            "| `experiments.json` | Every recorded run, including the ones that were not selected. |",
            "| `model_metadata.json` | The selected run's versions, features, folds, and checksums. |",
            "",
            "## Identity",
            "",
            f"- Selected run: `{metadata['run_name']}` ({metadata['kind']}, ablation `{metadata['ablation']}`).",
            f"- Configuration: `{metadata['config']}`.",
            f"- Dataset: `{metadata['dataset_version']}`.",
            f"- Feature spec: `{metadata['feature_spec_version']}`.",
            f"- Text transformer SHA-256: `{metadata['text_transformer_sha256']}`.",
            f"- Feature schema SHA-256: `{metadata['feature_schema_sha256']}`.",
            f"- scikit-learn `{metadata['sklearn_version']}`, NumPy `{metadata['numpy_version']}`.",
            "",
            "## Inputs",
            "",
            "The scorer reads only these columns, in this order:",
            "",
            columns,
            "",
            "Labels, roles, scenarios, splits, subsets, families, and other audit fields are rejected. A different feature-spec version or a different installed feature list is rejected.",
            "",
            "## Preprocessing stored with the model",
            "",
            _recency_fill_text(metadata),
            "",
            "## Output",
            "",
            "One `risk_score` per recipient row. Email risk, when needed, is the maximum of those scores. The bundle does not return a decision.",
            "",
            "## Load checks",
            "",
            f"- `model_version` must be `{metadata['model_version']}`.",
            "- `feature_spec_version` must match the installed feature package.",
            "- `full_feature_columns` must match `FEATURE_COLUMNS` in order.",
            "- The loader does not call `fit`.",
            "",
        ]
    )


def _recency_fill_text(metadata: dict) -> str:
    fill = metadata.get("recency_fill_days")
    if metadata.get("kind") not in {"logistic", "tree"} or "pair_recency_days" not in metadata["feature_columns"]:
        return "The selected scorer does not read `pair_recency_days`, so no recency fill is stored."
    if fill is None:
        return "No recency fill value was recorded for this bundle."
    return (
        "When recency was not observed (`pair_recency_observed` is 0), the feature row carries the "
        "documented 3650-day fallback. The model does not read that value: it replaces it with the median "
        f"observed `pair_recency_days` on the training rows, {float(fill):.6g} days "
        f"({float(fill) * 1440:.1f} minutes), and then applies `log1p`. A first contact therefore enters the model "
        "with the recency of a typical recent correspondent, and `pair_recency_observed` = 0 is the input that "
        "marks it as unobserved. Counts also take `log1p`. "
        + ("Logistic regression then standardizes with the training mean and standard deviation." if metadata.get("kind") == "logistic" else "The tree does not standardize.")
        + " All of these values are fit on `train` only and stored in `model.joblib`."
    )


def _decision(payload: dict, selected: dict, runs: list[dict]) -> str:
    product = selected["validation_product_like"]["email"]
    diagnostic = selected["validation_diagnostic"]["email"]
    novelty = selected.get("novelty", {})
    lines = [
        "# Phase 4 — Model selection",
        "",
        f"Model bundle `{MODEL_VERSION}`. Dataset `{DATASET_VERSION}`. Features `{FEATURE_SPEC_VERSION}`.",
        "",
        "## Rule",
        "",
        "Choose the simplest eligible model whose email-level average precision on `validation_product_like` falls inside the family bootstrap interval of the best eligible model on that same metric. Rules are simpler than logistic regression. Logistic regression is simpler than the tree. When two models are equally simple, the higher mean email average precision from the training folds wins. That tie-break does not use the validation point estimate. Always-allow is the floor and is not eligible. Fusion and the diagnostic runs (recency floor, dropped rate) are not eligible.",
        "",
        "Behavior-only models are always eligible. An all-features model is eligible only if the checks in the next section hold for its model family.",
        "",
        "## Eligibility of all-features models",
        "",
        _eligibility_section(payload),
        "",
        "## Selected model",
        "",
        f"The rule selects `{selected['name']}`.",
        "",
        f"On `validation_product_like` its email average precision is {_fmt_ap(product)} "
        f"({product['positives']} positive emails out of {product['n']}). "
        f"On `validation_diagnostic` it is {_fmt_ap(diagnostic)} "
        f"({diagnostic['positives']} positive emails out of {diagnostic['n']}). "
        "The diagnostic figure is not a 0.5% prevalence result.",
        "",
        "## Why this model",
        "",
        _why(selected, runs),
        "",
        "## Content features",
        "",
        _content_paragraph(selected, runs),
        "",
        "## First contact",
        "",
        _first_contact_paragraph(selected),
        "",
        _s11_section(selected, runs),
        "",
        "## Recency",
        "",
        _recency_paragraph(payload, runs),
        "",
        "## Coefficients",
        "",
        _coefficient_paragraph(selected, runs, payload),
        "",
        "## Tree scores",
        "",
        _tree_paragraph(runs),
        "",
        "## Novelty coefficient",
        "",
        _novelty_paragraph(selected, runs, novelty),
        "",
        "## Rejected options",
        "",
        _rejected(selected, runs),
        "",
        "## Limitations",
        "",
        _limitations(payload, selected, runs),
        "",
    ]
    return "\n".join(lines)


def _eligibility_section(payload: dict) -> str:
    evidence = payload.get("eligibility") or {}
    audit = evidence.get("audit") or {}
    lines = [evidence.get("rule", ""), ""]
    if "content_auc" in audit:
        bounds = audit["auc_bounds"]
        listed = ", ".join(
            f"`{name}` AUC {value:.3f} (separation {audit['content_separation'][name]:.3f})"
            for name, value in audit["content_auc"].items()
        )
        lines.append(
            f"Check 1, train shortcut audit (from the feature artifact): content features {listed}. "
            f"Flag bounds are {bounds[0]} and {bounds[1]}. "
            + ("No content feature is flagged, so the check passes." if audit["passed"] else f"Flagged: {', '.join(audit['flagged_content'])}. The check fails.")
        )
    else:
        lines.append(f"Check 1, train shortcut audit: {audit.get('reason', 'not available')}. The check fails.")
    lines += [
        "",
        "Checks 2 and 3 compare email average precision fold by fold on the expanding chronological train folds, each model at its own tuned setting. A margin is all-features minus the other model on that fold.",
        "",
        "| Family | All-features run | Check 2: min margin over behavior-only (per fold) | Check 3: min margin over content-only (per fold) | Checks passed | Eligible |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for family, item in (evidence.get("families") or {}).items():
        stability = item["fold_stability"]
        content = item["not_content_alone"]
        passed = [name for name, ok in item["checks"].items() if ok]
        lines.append(
            f"| {family} | `{item['run']}` | {_margin(stability)} | {_margin(content)} | {', '.join(passed) or 'none'} | "
            f"{'yes' if item['eligible'] else 'no (failed: ' + ', '.join(item['failed']) + ')'} |"
        )
    lines += [
        "",
        "Train-fold mean email average precision by ablation, with the product-like validation figure beside it for reference only:",
        "",
        "| Family | All | Behavior-only | Content-only | Drop content (all text) | Drop similarity |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for family, item in (evidence.get("families") or {}).items():
        cells = []
        for ablation in ("all", "behavior_only", "content_only", "drop_content", "drop_similarity"):
            entry = item["ablations"].get(ablation)
            if entry is None:
                cells.append("—")
                continue
            cells.append(f"{_num_plain(entry['cv_mean'])} (val {_num_plain(entry['validation_product_like_email_ap'])})")
        lines.append(f"| {family} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _margin(block: dict) -> str:
    if not block.get("folds"):
        return "no common folds"
    per_fold = ", ".join(f"{item['margin']:+.3f}" for item in block["folds"])
    return f"{block['min_margin']:+.3f} ({per_fold})"


def _s11_section(selected: dict, runs: list[dict]) -> str:
    lines = [
        "### Mistaken first contacts (S11) against legitimate first contacts (S03, S06)",
        "",
        "Recipient-level risk scores, no cutoff applied. S11 rows are unintended recipients the sender had never emailed. Legitimate first-contact rows are intended S03 and S06 recipients who are novel to the sender. AUC is the chance that an S11 row outranks a legitimate first-contact row. No recall is reported here: recall needs the operating cutoff, which Phase 5 sets.",
        "",
        "| Run | Subset | S11 rows | S11 median [p25, p75] | Legitimate first-contact rows | Legitimate median [p25, p75] | AUC | AP | S11 above every legitimate first contact | AUC against all other legitimate rows |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    shown = [selected] + [
        run
        for run in runs
        if run["name"] != selected["name"]
        and run["kind"] in {"logistic", "tree"}
        and run["ablation"] in {"behavior_only", "all"}
        and run["name"].endswith(("unweighted", "only", "all"))
    ]
    for run in shown:
        diagnostics = run.get("first_contact_diagnostics") or {}
        for subset in ("validation_product_like", "validation_diagnostic"):
            block = diagnostics.get(subset)
            if not block:
                continue
            s11, legit = block["s11_unintended"], block["legitimate_first_contact"]
            pair = block.get("s11_vs_legitimate_first_contact") or {}
            other = block.get("s11_vs_all_other_legitimate") or {}
            lines.append(
                f"| `{run['name']}` | `{subset}` | {s11['n']} | {_dist(s11)} | {legit['n']} | {_dist(legit)} | "
                f"{_num_plain(pair.get('roc_auc'))} | {_num_plain(pair.get('average_precision'))} | "
                f"{pair.get('s11_above_max_legitimate_first_contact', '—')} of {s11['n']} | {_num_plain(other.get('roc_auc'))} |"
            )
    lines += [
        "",
        "Product-like validation has only a handful of S11 and S03/S06 drafts, so its row is anecdotal. Diagnostic rows share families and are not independent.",
    ]
    return "\n".join(lines)


def _dist(block: dict) -> str:
    if not block.get("n"):
        return "—"
    return f"{block['median']:.3g} [{block['p25']:.3g}, {block['p75']:.3g}]"


def _limitations(payload: dict, selected: dict, runs: list[dict]) -> str:
    items = []
    audit = (payload.get("eligibility") or {}).get("audit") or {}
    cosine = (audit.get("content_separation") or {}).get("content_cosine")
    if cosine is not None:
        items.append(
            f"Content cosine is a real but strong train signal (separation {cosine:.3f}). Off-topic mistakes (S02, S04) sit low on it by their scenario definitions, so a content model's gain on those scenarios partly restates how they were written."
        )
    shortcut = (payload.get("recency_shortcut") or {}).get("train") or {}
    if shortcut:
        items.append(
            f"Recency under five minutes: {_share(shortcut.get('legitimate_share_under_5_minutes'))} of legitimate and "
            f"{_share(shortcut.get('misdirected_share_under_5_minutes'))} of misdirected train rows."
        )
    product = selected["validation_product_like"]["email"]
    items.append(
        f"`validation_product_like` has {product['positives']} misdirected emails out of {product['n']}. Intervals are wide. A gap smaller than an interval is not a ranking."
    )
    items += [
        "The training mix is 10% misdirected. Precision at that mix is not an operating point. Product-like prevalence is a 0.5% simulation assumption.",
        "Scores are risk scores. Nothing was calibrated. No threshold was selected. The frozen test subsets were not scored.",
        "Coefficients on overlapping count features are not separate effects.",
        "AC01, AC02, and AC05 were not measured in this phase.",
    ]
    return "\n".join(f"- {item}" for item in items)


def _why(selected: dict, runs: list[dict]) -> str:
    eligible = [run for run in runs if run["eligible"]]
    best = max(eligible, key=_ap)
    behavior = [run for run in eligible if run["ablation"] == "behavior_only"]
    interval = best["validation_product_like"]["email"]["bootstrap"]["average_precision"]
    outside = []
    inside = []
    for run in eligible:
        point = _ap(run)
        if interval is not None and not (interval["low"] <= point <= interval["high"]):
            outside.append(run)
        else:
            inside.append(run)
    text = (
        f"The highest email average precision among eligible models on product-like validation is `{best['name']}` "
        f"at {_fmt_ap(best['validation_product_like']['email'])}."
    )
    if outside:
        listed = ", ".join(f"`{run['name']}` at {_ap(run):.3f}" for run in outside)
        text += f" Outside that interval: {listed}."
    if inside:
        listed = ", ".join(f"`{run['name']}`" for run in inside)
        text += f" Inside it: {listed}."
    peers = [run for run in inside if run["simplicity"] == selected["simplicity"] and run["name"] != selected["name"]]
    if peers:
        names = ", ".join(f"`{run['name']}`" for run in peers)
        text += (
            f" `{selected['name']}` and {names} are equally simple. "
            "The higher training-fold mean is kept, not the validation point estimate."
        )
    else:
        text += f" The simplest model inside the interval is `{selected['name']}`."
    if behavior:
        top = max(behavior, key=_ap)
        text += f" The best behavior-only model is `{top['name']}` at {_fmt_ap(top['validation_product_like']['email'])}."
    if selected["ablation"] == "behavior_only":
        text += " The selected model does not use the content cosine columns."
    return text


def _first_contact_paragraph(selected: dict) -> str:
    contrast = (selected.get("first_contact_contrast") or {}).get("validation_product_like")
    if not contrast:
        return "No paired first-contact check was stored for the selected model."
    before = contrast["positive_median_before"]
    after = contrast["positive_median_after"]
    text = (
        f"On product-like validation, the {contrast['n_positive']} unintended recipient rows have median risk "
        f"{before:.4f}. Rewriting each of those rows as a first contact for the same sender "
        f"(no pair counts, novelty on, recency unobserved, no pair text) moves the median to {after:.4f}."
    )
    fill = selected.get("recency_fill_days")
    if fill is not None:
        text += (
            f" Unobserved recency is replaced with the median observed recency on the fitting rows, "
            f"{float(fill) * 1440:.1f} minutes, and then log-transformed. The old 3650-day fallback is not a raw input."
        )
    if after is not None and after < 0.05:
        text += (
            " A familiar-recipient mistake stripped of its history therefore loses almost all of its risk. The rewrite is "
            "synthetic; the S11 comparison below scores real mistaken first contacts."
        )
    else:
        text += (
            " The rewrite is a synthetic check; the S11 comparison below scores real mistaken first contacts."
        )
    diagnostic = (selected.get("first_contact_contrast") or {}).get("validation_diagnostic")
    if diagnostic:
        text += (
            f" On the diagnostic subset the same rewrite moves the positive median from "
            f"{diagnostic['positive_median_before']:.4f} to {diagnostic['positive_median_after']:.4f} "
            f"({diagnostic['n_positive']} positive rows)."
        )
    return text


def _recency_paragraph(payload: dict, runs: list[dict]) -> str:
    shortcut = payload.get("recency_shortcut") or {}
    train = shortcut.get("train") or {}
    product = shortcut.get("validation_product_like") or {}
    text = (
        "Share of recipient rows whose last mail between the sender and that recipient was less than five minutes before the draft: "
        f"{_share(train.get('legitimate_share_under_5_minutes'))} of {train.get('n_legitimate', '—')} legitimate and "
        f"{_share(train.get('misdirected_share_under_5_minutes'))} of {train.get('n_misdirected', '—')} misdirected training rows; "
        f"{_share(product.get('legitimate_share_under_5_minutes'))} of {product.get('n_legitimate', '—')} legitimate and "
        f"{_share(product.get('misdirected_share_under_5_minutes'))} of {product.get('n_misdirected', '—')} misdirected product-like validation rows. "
        f"The shortest misdirected gap is {_days(train.get('misdirected_min_days'))} in train."
    )
    floor = _named(runs, "logistic_behavior_recency_floor_unweighted")
    if floor:
        text += (
            f" A diagnostic behavior-only logistic model floors recency at one day before the log. "
            f"Its product-like email average precision is {_fmt_ap(floor['validation_product_like']['email'])}. "
            "It is not a selection candidate."
        )
    return text


def _coefficient_paragraph(selected: dict, runs: list[dict], payload: dict) -> str:
    logistic = selected if selected.get("kind") == "logistic" else _named(runs, "logistic_behavior_only_unweighted")
    if logistic is None:
        return "No logistic model was recorded."
    config = logistic.get("config") or {}
    grid = payload.get("c_grid") or []
    subject = "The selected logistic" if logistic["name"] == selected["name"] else f"`{logistic['name']}`"
    text = f"{subject} `C` is {config.get('C'):g}. The train grid is {', '.join(f'{value:g}' for value in grid)}. "
    edge = logistic.get("grid_edge")
    if edge == "top":
        text += "Tuning stopped on the top edge of the grid, the least regularized point; the search may not have reached its best value. "
    elif edge == "bottom":
        text += "Tuning stopped on the bottom edge of the grid, the most regularized point. "
    else:
        text += "The chosen value is inside the grid, not on an edge. "
    edges = [f"`{run['name']}` ({run['grid_edge']})" for run in runs if run.get("grid_edge") and run["name"] != logistic["name"]]
    if edges:
        text += f"Other logistic runs whose `C` landed on a grid edge: {', '.join(edges)}. "
    largest = ((logistic.get("novelty") or {}).get("largest_coefficients")) or []
    if largest:
        listed = ", ".join(f"`{item['feature']}` {item['coefficient']:+.2f}" for item in largest[:6])
        text += f"The largest standardized coefficients are {listed}. "
    text += (
        "Extending the grid is a tuning change only; it does not remove collinearity, and a larger `C` can make correlated "
        "coefficients less stable. Weights on overlapping count features are not separate effects, and no single coefficient, "
        "including the novelty coefficient, is a behavioral finding."
    )
    dropped = _named(runs, "logistic_behavior_drop_rate_unweighted")
    if dropped:
        text += (
            f" Dropping `pair_outbound_rate_per_day` and refitting on train gives product-like email average "
            f"precision {_fmt_ap(dropped['validation_product_like']['email'])}. That run is a collinearity check, "
            "not a selection candidate."
        )
    return text


def _tree_paragraph(runs: list[dict]) -> str:
    tree = _named(runs, "tree_behavior_only")
    if tree is None:
        return "No behavior-only tree was recorded."
    support = (tree["validation_product_like"].get("score_support")) or {}
    buckets = support.get("buckets_with_positives") or []
    if not buckets:
        return (
            f"The behavior-only tree's product-like email average precision is "
            f"{_fmt_ap(tree['validation_product_like']['email'])}. Its rejection stands."
        )
    bucket = buckets[0]
    return (
        f"The behavior-only tree writes {support.get('n_distinct', '—')} distinct scores on product-like "
        f"validation. Its {bucket['n_positive']} positive recipient rows share the score {bucket['score']:.3f} "
        f"with {bucket['n'] - bucket['n_positive']} legitimate rows in that same score. Average precision "
        "counts those ties as a mixed leaf, so the low number is a tie penalty, not a separate story about "
        f"what the tree learned. Train-fold mean email average precision was {_num_plain((tree.get('cv') or {}).get('mean'))}. "
        "The rejection stands."
    )


def _positives(runs: list[dict]) -> str:
    for run in runs:
        return str(run["validation_product_like"]["email"]["positives"])
    return "—"


def _named(runs: list[dict], name: str) -> dict | None:
    for run in runs:
        if run["name"] == name:
            return run
    return None


def _share(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1%}"


def _days(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.3f} days"


def _content_paragraph(selected: dict, runs: list[dict]) -> str:
    if selected["ablation"] == "behavior_only" or selected["kind"] == "rules":
        uses = "The selected model does not use content cosine, the content-observed flag, or the pair-text count."
    else:
        uses = (
            "The selected model uses content features. It was a candidate only because its family passed the eligibility checks above; "
            "the behavior-only model of the same family is reported beside it."
        )
    return uses + " " + _gap_sentence(runs)


def _gap_sentence(runs: list[dict]) -> str:
    parts = []
    for kind in ("logistic", "tree"):
        behavior = _match(runs, kind, "behavior_only")
        full = _match(runs, kind, "all")
        if behavior is None or full is None:
            continue
        parts.append(
            f"`{kind}` email average precision on product-like validation is {_fmt_ap(behavior['validation_product_like']['email'])} "
            f"without those content columns and {_fmt_ap(full['validation_product_like']['email'])} with all features."
        )
    return " ".join(parts)


def _novelty_paragraph(selected: dict, runs: list[dict], novelty: dict) -> str:
    lines = [_format_novelty(selected["name"], novelty)]
    for run in runs:
        if run["name"] == selected["name"]:
            continue
        if run["ablation"] == "behavior_only" and run["kind"] in {"logistic", "tree"}:
            lines.append(_format_novelty(run["name"], run.get("novelty", {})))
    return " ".join(lines)


def _format_novelty(name: str, novelty: dict) -> str:
    if not novelty or not novelty.get("available"):
        return f"`{name}` does not expose a novelty coefficient."
    if novelty.get("kind") == "standardized_coefficient":
        return (
            f"`{name}` has a standardized coefficient of {novelty['coefficient']:.4f} on "
            f"`recipient_novel_to_sender` ({novelty['sign']}). That coefficient is not a behavioral finding. "
            "The paired first-contact scores are the check."
        )
    if novelty.get("kind") == "tree_splits":
        if novelty.get("uses_feature"):
            return (
                f"`{name}` splits on `recipient_novel_to_sender` "
                f"(importance {novelty['importance']:.4f}, {len(novelty['splits'])} node(s))."
            )
        return f"`{name}` does not split on `recipient_novel_to_sender` (importance {novelty['importance']:.4f})."
    if novelty.get("statement"):
        return f"`{name}`: {novelty['statement']}"
    return f"`{name}` novelty record: `{novelty}`."


def _rejected(selected: dict, runs: list[dict]) -> str:
    lines = []
    for run in runs:
        if not run["eligible"] or run["name"] == selected["name"]:
            continue
        lines.append(
            f"- `{run['name']}` email average precision {_fmt_ap(run['validation_product_like']['email'])} on product-like validation."
        )
    if not lines:
        return "No other behavior-only model was recorded."
    return "\n".join(lines)


def _run_table(runs: list[dict]) -> str:
    header = (
        "| Run | Ablation | Product-like email AP | Product-like recipient AP | "
        "Diagnostic email AP | CV email AP | Fit seconds | Score seconds / 1,000 rows |"
    )
    rule = "| --- | --- | --- | --- | --- | --- | --- | --- |"
    body = []
    for run in runs:
        product = run["validation_product_like"]
        diagnostic = run["validation_diagnostic"]
        cv_mean = run.get("cv", {}).get("mean")
        body.append(
            "| `{name}` | {ablation} | {email} ({ep} pos / {en}) | {recip} ({rp} pos / {rn}) | {demail} ({dp} pos / {dn}) | {cv} | {fit} | {score} |".format(
                name=run["name"],
                ablation=run["ablation"],
                email=_fmt_ap(product["email"]),
                ep=product["email"]["positives"],
                en=product["email"]["n"],
                recip=_fmt_ap(product["recipient"]),
                rp=product["recipient"]["positives"],
                rn=product["recipient"]["n"],
                demail=_fmt_ap(diagnostic["email"]),
                dp=diagnostic["email"]["positives"],
                dn=diagnostic["email"]["n"],
                cv=_num_plain(cv_mean),
                fit=f"{run['fit_seconds']:.3f}",
                score=f"{product['score_seconds_per_1000_rows']:.4f}",
            )
        )
    return "\n".join([header, rule, *body])


def _cv_table(runs: list[dict]) -> str:
    header = "| Run | Mean | Std | Folds scored |"
    rule = "| --- | --- | --- | --- |"
    body = []
    for run in runs:
        cv = run.get("cv") or {}
        body.append(
            f"| `{run['name']}` | {_num_plain(cv.get('mean'))} | {_num_plain(cv.get('std'))} | {cv.get('n_folds_scored', '')} |"
        )
    return "\n".join([header, rule, *body])


def _fold_table(folds: list[dict]) -> str:
    header = "| Fold | First week | Last week | Drafts | Positive emails | Families |"
    rule = "| --- | --- | --- | --- | --- | --- |"
    body = [
        f"| {item['fold']} | {item['week_start']} | {item['week_end']} | {item['n_drafts']} | {item['n_positive_emails']} | {item['n_families']} |"
        for item in folds
    ]
    return "\n".join([header, rule, *body])


def _gap_table(runs: list[dict]) -> str:
    header = "| Model | Behavior-only email AP | All-features email AP | Content-only email AP |"
    rule = "| --- | --- | --- | --- |"
    body = []
    for kind in ("logistic", "tree"):
        behavior = _match(runs, kind, "behavior_only")
        full = _match(runs, kind, "all")
        content = _match(runs, kind, "content_only")
        if behavior is None:
            continue
        body.append(
            "| {kind} | {behavior} | {full} | {content} |".format(
                kind=kind,
                behavior=_fmt_ap(behavior["validation_product_like"]["email"]),
                full=_fmt_ap(full["validation_product_like"]["email"]) if full else "",
                content=_fmt_ap(content["validation_product_like"]["email"]) if content else "",
            )
        )
    return "\n".join([header, rule, *body])


def _primary(run: dict) -> bool:
    if run["kind"] in {"always_allow", "rules", "fusion"}:
        return True
    if run["ablation"] not in {"all", "behavior_only"}:
        return False
    if run["kind"] == "tree":
        return True
    return run["config"].get("class_weight") in {"balanced", "unweighted"}


def _match(runs: list[dict], kind: str, ablation: str) -> dict | None:
    found = [run for run in runs if run["kind"] == kind and run["ablation"] == ablation]
    if not found:
        return None
    return max(found, key=_ap)


def _run(runs: list[dict], name: str) -> dict:
    for run in runs:
        if run["name"] == name:
            return run
    raise KeyError(name)


def _ap(run: dict) -> float:
    value = run["validation_product_like"]["email"]["average_precision"]
    return float(value) if value is not None else float("-inf")


def _fmt_ap(block: dict | None) -> str:
    if not block or block.get("average_precision") is None:
        return "—"
    interval = (block.get("bootstrap") or {}).get("average_precision")
    point = f"{block['average_precision']:.3f}"
    if not interval:
        return point
    return f"{point} [{interval['low']:.3f}, {interval['high']:.3f}]"


def _num(interval: dict | None, key: str) -> str:
    if not interval or interval.get(key) is None:
        return "—"
    return f"{interval[key]:.3f}"


def _num_plain(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):.3f}"
