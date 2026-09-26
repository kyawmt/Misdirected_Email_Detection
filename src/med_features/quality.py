"""Offline feature quality report.

Scenario and label fields are joined here only. They are not feature columns.
The report covers train and validation subsets. Frozen test subsets are refused.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from med_data.calendar import FROZEN_SUBSETS
from med_features.checks import validate_feature_frame
from med_features.schema import EXPORT_SUBSETS, FEATURE_COLUMNS, FEATURE_SPEC_VERSION, FeatureError

# Value to ignore when summarizing a feature that is undefined on some rows.
UNDEFINED_WHEN = {
    "sender_history_span_days": "sender_history_available",
    "pair_outbound_rate_per_day": "sender_history_available",
    "pair_recency_days": "pair_recency_observed",
    "co_partner_fraction": "co_support_applicable",
    "name_similarity_max": "contact_similarity_observed",
    "address_similarity_max": "contact_similarity_observed",
    "near_name_count": "contact_similarity_observed",
    "content_cosine": "content_similarity_observed",
    "co_focus_conditional_fraction": "co_focus_history_available",
}

# A6 shortcut checks, train only. A single feature whose train AUC for
# unintended recipient rows is above the high bound or below the low bound is
# flagged as a near-perfect separator. Flags are warnings to investigate.
SHORTCUT_AUC_LOW = 0.05
SHORTCUT_AUC_HIGH = 0.95
FIVE_MINUTES_DAYS = 5 / 1440
CONTENT_FEATURES = ("content_cosine", "content_similarity_observed", "pair_text_message_count")

SCENARIO_FEATURES = (
    "pair_outbound_count",
    "recipient_novel_to_sender",
    "domain_novel_to_sender",
    "domain_seen_in_history",
    "recipient_is_internal",
    "co_support_applicable",
    "co_partner_fraction",
    "name_similarity_max",
    "content_cosine",
    "content_similarity_observed",
    "draft_text_empty",
    "draft_text_short",
    "draft_text_oov",
    "pair_recency_observed",
)


def quality_report(dataset, frames_by_subset: dict[str, pd.DataFrame], *, fit_scope: dict) -> dict:
    if not frames_by_subset:
        raise FeatureError("Quality report needs at least one subset")
    subsets = {}
    for subset, frame in frames_by_subset.items():
        if subset not in EXPORT_SUBSETS or subset in FROZEN_SUBSETS:
            raise FeatureError(f"Quality report refuses subset {subset}")
        problems = validate_feature_frame(frame)
        if problems:
            raise FeatureError(f"{subset} feature frame failed checks: {problems[0]}")
        subsets[subset] = _subset_report(dataset, subset, frame)
    shortcut = None
    if "train" in frames_by_subset:
        shortcut = shortcut_checks(dataset, frames_by_subset["train"])
    report = {
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "dataset_version": str(dataset.summary.get("dataset_version", "")),
        "fit_scope": fit_scope,
        "populations": list(frames_by_subset),
        "frozen_subsets_excluded": list(FROZEN_SUBSETS),
        "subsets": subsets,
        "shortcut_checks": shortcut,
        "hypotheses": _hypotheses(),
    }
    report["table_notes"] = _table_notes(report)
    report["limitations"] = _limitations(report, dataset)
    return report


def shortcut_checks(dataset, frame: pd.DataFrame) -> dict:
    """A6: single-feature AUC and the five-minute recency share, on train rows only.

    The positive class is an unintended recipient row. AUC is computed on the
    raw feature value, fallbacks included, so a low value means low feature
    values go with mistakes. `separation` is max(AUC, 1 - AUC).
    """
    ids = set(frame["draft_id"])
    subsets = set(dataset.drafts.loc[dataset.drafts["draft_id"].isin(ids), "subset"])
    if subsets != {"train"}:
        raise FeatureError(f"Shortcut checks run on train only, got {sorted(subsets)}")
    labels = dataset.labels.loc[dataset.labels["draft_id"].isin(ids), ["draft_id", "contact_id", "intended"]]
    labeled = frame.merge(labels, on=["draft_id", "contact_id"], how="left")
    if labeled["intended"].isna().any():
        raise FeatureError("A train feature row has no label")
    positive = ~labeled["intended"].astype(bool).to_numpy()
    features = []
    for name in FEATURE_COLUMNS:
        values = labeled[name].to_numpy(dtype=np.float64)
        if positive.all() or not positive.any():
            auc = 0.5
        elif np.unique(values).size < 2:
            auc = 0.5
        else:
            auc = float(roc_auc_score(positive, values))
        features.append(
            {
                "feature": name,
                "auc": auc,
                "separation": max(auc, 1 - auc),
                "flagged": bool(auc > SHORTCUT_AUC_HIGH or auc < SHORTCUT_AUC_LOW),
                "content": name in CONTENT_FEATURES,
            }
        )
    features.sort(key=lambda item: -item["separation"])
    recency = labeled["pair_recency_days"].to_numpy(dtype=np.float64)
    observed = labeled["pair_recency_observed"].to_numpy() == 1
    recent = observed & (recency < FIVE_MINUTES_DAYS)
    return {
        "population": "train recipient rows",
        "rows": int(len(labeled)),
        "unintended_rows": int(positive.sum()),
        "auc_bounds": [SHORTCUT_AUC_LOW, SHORTCUT_AUC_HIGH],
        "features": features,
        "flagged": [item["feature"] for item in features if item["flagged"]],
        "flagged_content": [item["feature"] for item in features if item["flagged"] and item["content"]],
        "five_minute_recency": {
            "intended_rows": int((~positive).sum()),
            "intended_under_5_minutes": int((recent & ~positive).sum()),
            "intended_share": float((recent & ~positive).sum() / max((~positive).sum(), 1)),
            "unintended_rows": int(positive.sum()),
            "unintended_under_5_minutes": int((recent & positive).sum()),
            "unintended_share": float((recent & positive).sum() / max(positive.sum(), 1)),
        },
        "reading": "Warnings to investigate, not pass/fail on intent. A flag means one feature nearly separates the stipulated labels on train.",
    }


def render_quality_markdown(report: dict) -> str:
    lines = [
        "# Phase 3 — Feature quality report",
        "",
        f"Feature specification `{report['feature_spec_version']}`. "
        f"Dataset `{report['dataset_version']}`.",
        "",
        "This report describes feature matrices for train and validation only. "
        "It does not measure detection, precision, recall, or a warning rate. "
        "Scenario and label fields were joined after the matrix was built and are not model inputs. "
        "`test_product_like` and `test_diagnostic` are not included. "
        "Every exported value is finite; the build rejects a matrix that breaks the fallback checks.",
        "",
        "## Fit scope",
        "",
        _fit_lines(report["fit_scope"]),
        "",
        "## Populations",
        "",
    ]
    ordered = [name for name in EXPORT_SUBSETS if name in report["subsets"]]
    ordered.extend(name for name in report["subsets"] if name not in ordered)
    for subset in ordered:
        payload = report["subsets"][subset]
        lines.append(f"### `{subset}`")
        lines.append("")
        lines.append(
            f"{payload['drafts']} drafts, {payload['recipient_rows']} recipient rows, "
            f"{payload['senders']} senders."
        )
        lines.append("")
        lines.append(_feature_table(payload["features"]))
        lines.append("")
        lines.append("Scenario means are descriptive. A rate is the mean of a 0/1 feature on recipient rows.")
        lines.append("")
        lines.append(_scenario_table(payload["scenarios"]))
        lines.append("")
        if payload["constants"]:
            lines.append("Constant features in this subset: " + ", ".join(f"`{name}`" for name in payload["constants"]) + ".")
        else:
            lines.append("No feature is constant in this subset.")
        lines.append("")
        lines.append(
            "Intended and unintended means use the stipulated label after scoring. "
            "They are not a precision or recall result, and the training mix is enriched."
        )
        lines.append("")
        lines.append(_intended_table(payload["intended_means"]))
        lines.append("")
    if report.get("shortcut_checks"):
        lines.extend(_shortcut_lines(report["shortcut_checks"]))
    lines.extend(
        [
            "## Hypotheses",
            "",
            "These were fixed with the feature definitions. The tables are the place to compare them. "
            "Agreement is not evidence that a later model should warn.",
            "",
        ]
    )
    for item in report["hypotheses"]:
        lines.append(f"- {item}")
    lines.extend(["", "## What the tables show", ""])
    for item in report.get("table_notes", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Limitations", ""])
    for item in report["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _subset_report(dataset, subset: str, frame: pd.DataFrame) -> dict:
    drafts = dataset.drafts.loc[dataset.drafts["subset"] == subset, ["draft_id", "scenario_id", "sent_at"]]
    ids = set(frame["draft_id"])
    if ids - set(drafts["draft_id"]):
        raise FeatureError(f"{subset} matrix contains a draft from another subset")
    if set(drafts["draft_id"]) - ids:
        raise FeatureError(f"{subset} matrix is missing drafts")
    frozen = set(dataset.drafts.loc[dataset.drafts["draft_id"].isin(ids), "subset"]) & set(FROZEN_SUBSETS)
    if frozen:
        raise FeatureError("Frozen drafts cannot enter the quality report")
    labels = dataset.labels.loc[dataset.labels["draft_id"].isin(ids), ["draft_id", "contact_id", "intended"]]
    labeled = frame.merge(labels, on=["draft_id", "contact_id"], how="left")
    if labeled["intended"].isna().any():
        raise FeatureError("A feature row has no label for the offline report")
    scenarios = frame.merge(drafts[["draft_id", "scenario_id"]], on="draft_id", how="left")
    return {
        "drafts": int(frame["draft_id"].nunique()),
        "recipient_rows": int(len(frame)),
        "senders": int(
            dataset.drafts.loc[dataset.drafts["draft_id"].isin(ids), "sender_contact_id"].nunique()
        ),
        "features": {name: _feature_stats(frame, name) for name in FEATURE_COLUMNS},
        "constants": [name for name in FEATURE_COLUMNS if frame[name].nunique(dropna=False) <= 1],
        "scenarios": _scenarios(scenarios),
        "intended_means": _intended_means(labeled),
    }


def _feature_stats(frame: pd.DataFrame, name: str) -> dict:
    column = frame[name].to_numpy()
    defined = np.ones(len(frame), dtype=bool)
    flag = UNDEFINED_WHEN.get(name)
    if flag is not None:
        defined = frame[flag].to_numpy() == 1
        if name == "co_focus_conditional_fraction":
            defined = defined & (frame["co_support_applicable"].to_numpy() == 1)
    values = column[defined] if defined.any() else np.array([], dtype=float)
    undefined = int((~defined).sum())
    stats = {
        "count": int(len(frame)),
        "undefined": undefined,
        "undefined_fraction": undefined / len(frame) if len(frame) else 0.0,
        "nunique": int(pd.Series(column).nunique(dropna=False)),
        "constant": bool(pd.Series(column).nunique(dropna=False) <= 1),
        "min": _number(np.min(values)) if len(values) else None,
        "max": _number(np.max(values)) if len(values) else None,
        "mean": _number(np.mean(values)) if len(values) else None,
        "std": _number(np.std(values, ddof=0)) if len(values) else None,
    }
    return stats


def _scenarios(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for scenario, group in frame.groupby("scenario_id", sort=True):
        item = {
            "scenario_id": str(scenario),
            "drafts": int(group["draft_id"].nunique()),
            "recipient_rows": int(len(group)),
        }
        for name in SCENARIO_FEATURES:
            item[name] = _conditional_mean(group, name)
        rows.append(item)
    return rows


def _intended_means(frame: pd.DataFrame) -> dict:
    """Descriptive recipient-row means. Not an operating-point metric."""
    payload = {}
    for intended, group in frame.groupby("intended", sort=True):
        key = "intended" if bool(intended) else "unintended"
        payload[key] = {
            "recipient_rows": int(len(group)),
            "mean_pair_outbound_count": _conditional_mean(group, "pair_outbound_count"),
            "recipient_novel_rate": _conditional_mean(group, "recipient_novel_to_sender"),
            "mean_content_cosine": _conditional_mean(group, "content_cosine"),
            "mean_name_similarity": _conditional_mean(group, "name_similarity_max"),
        }
    return payload


def _conditional_mean(frame: pd.DataFrame, name: str) -> float | None:
    flag = UNDEFINED_WHEN.get(name)
    values = frame[name]
    if flag is not None:
        mask = frame[flag] == 1
        if name == "co_focus_conditional_fraction":
            mask = mask & (frame["co_support_applicable"] == 1)
        values = values.loc[mask]
    if values.empty:
        return None
    return _number(float(values.mean()))


def _number(value) -> float | int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _fit_lines(scope: dict) -> str:
    keys = (
        "corpus",
        "document_count",
        "vocabulary_size",
        "messages_in_window",
        "empty_documents_skipped",
        "first_sent_at",
        "last_sent_at",
        "fit_sent_at_end_exclusive",
        "warmup_included",
        "validation_and_test_excluded",
    )
    lines = []
    for key in keys:
        if key in scope:
            lines.append(f"- `{key}`: {scope[key]}")
    return "\n".join(lines)


def _feature_table(stats: dict) -> str:
    header = "| Feature | Min | Mean | Max | Unique | Undefined |"
    rule = "| --- | --- | --- | --- | --- | --- |"
    body = []
    for name, item in stats.items():
        body.append(
            "| `{name}` | {min} | {mean} | {max} | {nunique} | {undefined} |".format(
                name=name,
                min=_fmt(item["min"]),
                mean=_fmt(item["mean"]),
                max=_fmt(item["max"]),
                nunique=item["nunique"],
                undefined=_fmt(item["undefined_fraction"]),
            )
        )
    return "\n".join([header, rule, *body])


def _scenario_table(rows: list[dict]) -> str:
    columns = (
        "scenario_id",
        "drafts",
        "recipient_rows",
        "recipient_novel_to_sender",
        "domain_novel_to_sender",
        "pair_outbound_count",
        "content_similarity_observed",
        "content_cosine",
        "name_similarity_max",
        "draft_text_empty",
        "draft_text_oov",
        "co_support_applicable",
    )
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = []
    for row in rows:
        cells = []
        for column in columns:
            value = row[column]
            cells.append(str(value) if column in {"scenario_id", "drafts", "recipient_rows"} else _fmt(value))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, rule, *body])


def _intended_table(means: dict) -> str:
    header = "| Label | Recipient rows | Mean outbound count | Novel recipient rate | Mean cosine | Mean name similarity |"
    rule = "| --- | --- | --- | --- | --- | --- |"
    body = []
    for key in ("intended", "unintended"):
        item = means.get(key)
        if item is None:
            continue
        body.append(
            "| {key} | {rows} | {outbound} | {novel} | {cosine} | {name} |".format(
                key=key,
                rows=item["recipient_rows"],
                outbound=_fmt(item["mean_pair_outbound_count"]),
                novel=_fmt(item["recipient_novel_rate"]),
                cosine=_fmt(item["mean_content_cosine"]),
                name=_fmt(item["mean_name_similarity"]),
            )
        )
    if not body:
        return "No labeled rows."
    return "\n".join([header, rule, *body])


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _hypotheses() -> list[str]:
    return [
        "First-contact scenarios should show recipient_novel_to_sender near 1. Routine repeat mail should show it near 0. Novelty is not a label.",
        "A new external domain should show domain_seen_in_history of 0 and domain_novel_to_sender of 1. A new person on a known internal domain can be novel while the domain has already been seen.",
        "Lookalike names that are already in the directory should produce name_similarity_max well above the 0.8 near-name threshold. The nearest contact's identity is not a feature.",
        "Content cosine is summarized only where content_similarity_observed is 1. Empty drafts and out-of-vocabulary drafts stay at the cosine fallback 0, with their own indicators set.",
        "Single-recipient drafts keep co_support_applicable at 0. A multi-recipient draft with no shared history keeps a measured partner fraction of 0 where the flag is 1.",
        "Bcc does not appear in the matrix. Intended Bcc mail and unintended Bcc mail are not separated by a role indicator.",
        "Train contains about 10% misdirected emails and the product-like validation subset contains 0.5%. Means that pool those subsets are not an operating point. Intended and unintended means in this report are descriptive only.",
    ]


def _shortcut_lines(check: dict) -> list[str]:
    low, high = check["auc_bounds"]
    recency = check["five_minute_recency"]
    lines = [
        "## Train-only shortcut checks",
        "",
        f"On {check['rows']} train recipient rows ({check['unintended_rows']} unintended), each feature's AUC for an unintended row is computed on its raw value. "
        f"A feature is flagged when its AUC is above {high} or below {low}. Flags are warnings to investigate; they do not decide intent. "
        "Separation is the larger of AUC and 1 − AUC.",
        "",
        "| Feature | AUC | Separation | Flagged |",
        "| --- | --- | --- | --- |",
    ]
    for item in check["features"]:
        lines.append(f"| `{item['feature']}` | {item['auc']:.3f} | {item['separation']:.3f} | {'yes' if item['flagged'] else 'no'} |")
    flagged = ", ".join(f"`{name}`" for name in check["flagged"]) or "none"
    lines += [
        "",
        f"Flagged features: {flagged}.",
        "",
        f"Five-minute recency: {recency['intended_under_5_minutes']} of {recency['intended_rows']} intended train rows "
        f"({recency['intended_share']:.2%}) and {recency['unintended_under_5_minutes']} of {recency['unintended_rows']} unintended rows "
        f"({recency['unintended_share']:.2%}) had earlier mail between the sender and that recipient, in either direction, less than five minutes before the draft "
        "(the `pair_recency_days` feature). Dataset check Q31 counts mail to the recipient from any sender and reports its own shares.",
        "",
    ]
    return lines


def _scenario_value(report: dict, subset: str, scenario: str, name: str):
    for row in report["subsets"].get(subset, {}).get("scenarios", []):
        if row["scenario_id"] == scenario:
            return row.get(name), row["drafts"]
    return None, 0


def _table_notes(report: dict) -> list[str]:
    """Readings generated from the tables above. Not detection results."""
    notes = []
    if "train" in report["subsets"]:
        parts = []
        for scenario in ("S03", "S06", "S11"):
            novel, drafts = _scenario_value(report, "train", scenario, "recipient_novel_to_sender")
            if drafts:
                parts.append(f"{scenario} ({drafts} drafts) has recipient novelty {_fmt(novel)}")
        if parts:
            notes.append("Training " + "; ".join(parts) + ". S03 and S06 are legitimate first contacts and S11 is a mistaken one, so novelty alone does not set the label.")
        cosines = []
        for scenario in ("S01", "S02", "S04", "S05", "S07", "S08", "S11", "routine"):
            value, drafts = _scenario_value(report, "train", scenario, "content_cosine")
            if drafts and value is not None:
                cosines.append(f"{scenario} {value:.3f}")
        if cosines:
            notes.append("Mean observed content cosine on train by scenario: " + ", ".join(cosines) + ". Scenarios without pair text have no observed cosine.")
        name, drafts = _scenario_value(report, "train", "S01", "name_similarity_max")
        if drafts:
            notes.append(f"Training S01 name similarity averages {_fmt(name)} against the 0.8 near-name threshold.")
    for subset in ("validation_product_like", "validation_diagnostic"):
        means = report["subsets"].get(subset, {}).get("intended_means", {})
        if "unintended" in means:
            notes.append(f"`{subset}` has {means['unintended']['recipient_rows']} unintended recipient rows; its intended-versus-unintended means are descriptive only.")
    check = report.get("shortcut_checks")
    if check:
        top = check["features"][0]
        notes.append(
            f"The strongest single train separator is `{top['feature']}` (AUC {top['auc']:.3f}, separation {top['separation']:.3f}). "
            + ("It is flagged." if top["flagged"] else f"No feature is outside [{check['auc_bounds'][0]}, {check['auc_bounds'][1]}].")
        )
    return notes


def _limitations(report: dict, dataset) -> list[str]:
    items = [
        "No classifier was trained. No risk score, threshold, precision, recall, or false-warning rate is claimed.",
    ]
    check = report.get("shortcut_checks")
    if check:
        content = next(item for item in check["features"] if item["feature"] == "content_cosine")
        items.append(
            f"Content cosine is a real but imperfect train signal: AUC {content['auc']:.3f} (separation {content['separation']:.3f}). "
            "Off-topic mistakes (S02, S04) sit low by their scenario definitions, while on-topic S08 mistakes, S01 lookalikes, and S11 first contacts are not separable by text. "
            "A later model comparison must still report a behavior-only model beside any content model."
        )
        novel = _novel_counts(dataset, report)
        if novel:
            items.append(
                f"Novel recipients in train: {novel['intended']} intended and {novel['unintended']} unintended rows. Novelty is evidence, not a label."
            )
    items += [
        "IDF is frozen on sent mail before the validation window. It is not re-estimated at each earlier training draft. Historical counts and text centroids still stop at that draft's cutoff.",
        "Template sentences repeat across weeks. Stripping reference, ticket, and date slots removes unique generator tokens. It does not remove shared topic wording.",
        "Group-topic profiles are not implemented. A recipient with no direct pair history has no content centroid even if a broader group has discussed the topic.",
        "Diagnostic rows that share a family are dependent. Product-like families contain one draft. Scenario means pool variants, including clean twins, and are not one story. Do not read a diagnostic rate as the 0.5% prevalence result.",
        "The fictional history is dense weekly mail, so outbound counts and per-day rates are large. That scale is a property of the generator, not a real-world volume.",
        "Contact similarity is always observed on the exported subsets, because other directory entries are already visible. The unobserved-similarity and both-fields-empty fallbacks remain part of the contract and are covered by fixture tests.",
        "The frozen test subsets were not profiled here.",
        "Department is a directory field and is not a feature. Communication role is stored on the draft and is not a feature.",
    ]
    return items


def _novel_counts(dataset, report: dict) -> dict | None:
    means = report["subsets"].get("train", {}).get("intended_means", {})
    if not means:
        return None
    out = {}
    for key in ("intended", "unintended"):
        item = means.get(key)
        out[key] = int(round(item["recipient_rows"] * item["recipient_novel_rate"])) if item and item["recipient_novel_rate"] is not None else 0
    return out
