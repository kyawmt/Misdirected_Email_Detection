"""Schema, label, split, and leakage checks for a generated dataset."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from med_data.calendar import ASSESSMENT_SPLITS, FROZEN_SUBSETS, split_for
from med_data.history import visible_history
from med_data.roster import PLANS, RESTRICTED_TOPICS
from med_data.schema import MODEL_INPUT_DENYLIST, ROLES, TABLES
from med_data.templates import TOPIC_MARKERS
from med_data.version import DATASET_VERSION, GENERATOR_VERSION
from med_data.views import denied_keys, scoring_view

EMAIL_PATTERN = r"^[a-z0-9][a-z0-9._+-]*@[a-z0-9][a-z0-9.-]*\.example$"


@dataclass(frozen=True)
class Check:
    check_id: str
    name: str
    passed: bool
    detail: str


def validate_dataset(dataset) -> list[Check]:
    checks: list[Check] = []
    specs = [
        ("Q01", "Required columns are present", _columns),
        ("Q02", "Primary keys are unique", _primary_keys),
        ("Q03", "Foreign keys resolve", _foreign_keys),
        ("Q04", "Addresses use reserved example domains", _addresses),
        ("Q05", "Timestamps sit inside their split windows", _windows),
        ("Q06", "Splits are chronological", _chronology),
        ("Q07", "Labels are complete synthetic stipulations", _labels),
        ("Q08", "Recipient lists are within the product bounds", _recipients),
        ("Q09", "Product-like prevalence matches the simulation contract", _prevalence),
        ("Q10", "Each draft family stays in one split and subset", _families),
        ("Q11", "Non-empty message text does not cross splits", _body_hashes),
        ("Q12", "Threads do not cross splits", _threads),
        ("Q13", "Misdirected drafts are not sent mail", _counterfactuals),
        ("Q14", "Non-counterfactual drafts match a sent message", _sent_drafts),
        ("Q15", "Visible history excludes the future, the family, and copied text", _leakage),
        ("Q16", "Participants are already in the directory", _directory),
        ("Q17", "Sent mail keeps scenario relationships on their topics", _topics),
        ("Q18", "Scenario drafts match their stipulated structure", _scenarios),
        ("Q19", "The canonical walkthrough cast is in the frozen diagnostic set", _walkthrough),
        ("Q20", "Uncertain and unaccepted feedback does not change labels", _feedback),
        ("Q21", "A scoring view omits labels and generator metadata", _scoring_view),
        ("Q22", "The test subsets are frozen", _frozen),
        ("Q23", "Every row carries the dataset version", _version),
        ("Q24", "Empty subject or body occurs only on little-text drafts", _empty_text),
        ("Q25", "Invalid fixtures are outside the labeled tables", _invalid),
        ("Q26", "Hard negatives and diagnostic scenarios are present", _coverage),
        ("Q27", "Sent message timestamps are unique", _unique_times),
        ("Q28", "Topic markers appear in non-empty bodies of that topic", _markers),
    ]
    for check_id, name, function in specs:
        try:
            detail = function(dataset)
        except Exception as exc:
            checks.append(Check(check_id, name, False, str(exc)))
        else:
            checks.append(Check(check_id, name, True, detail))
    return checks


def assert_valid(dataset) -> list[Check]:
    checks = validate_dataset(dataset)
    failed = [check for check in checks if not check.passed]
    if failed:
        lines = [f"{check.check_id} {check.name}: {check.detail}" for check in failed]
        raise AssertionError("\n".join(lines))
    return checks


def report_payload(checks: list[Check]) -> dict:
    return {
        "dataset_version": DATASET_VERSION,
        "generator_version": GENERATOR_VERSION,
        "passed": all(check.passed for check in checks),
        "checks": [
            {
                "id": check.check_id,
                "name": check.name,
                "passed": check.passed,
                "detail": check.detail,
            }
            for check in checks
        ],
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _columns(dataset) -> str:
    frames = _frames(dataset)
    for name, columns in TABLES.items():
        frame = frames[name]
        _require(list(frame.columns) == columns, f"{name} columns are {list(frame.columns)}")
    return f"{len(TABLES)} tables"


def _primary_keys(dataset) -> str:
    _require(dataset.contacts["contact_id"].is_unique, "contact_id")
    _require(dataset.messages["message_id"].is_unique, "message_id")
    _require(dataset.drafts["draft_id"].is_unique, "draft_id")
    _require(dataset.labels.set_index(["draft_id", "contact_id"]).index.is_unique, "label key")
    _require(
        dataset.draft_recipients.set_index(["draft_id", "contact_id"]).index.is_unique,
        "draft recipient key",
    )
    _require(
        dataset.message_recipients.set_index(["message_id", "contact_id"]).index.is_unique,
        "message recipient key",
    )
    _require(dataset.reviewer_feedback["feedback_id"].is_unique, "feedback_id")
    _require(dataset.split_manifest["draft_id"].is_unique, "manifest draft_id")
    _require(dataset.invalid_fixtures["fixture_id"].is_unique, "fixture_id")
    return "primary keys unique"


def _foreign_keys(dataset) -> str:
    contacts = set(dataset.contacts["contact_id"])
    messages = set(dataset.messages["message_id"])
    drafts = set(dataset.drafts["draft_id"])
    _require(set(dataset.messages["sender_contact_id"]) <= contacts, "message sender")
    _require(set(dataset.message_recipients["contact_id"]) <= contacts, "message recipient")
    _require(set(dataset.message_recipients["message_id"]) <= messages, "message recipient parent")
    _require(set(dataset.drafts["sender_contact_id"]) <= contacts, "draft sender")
    _require(set(dataset.draft_recipients["draft_id"]) <= drafts, "draft recipient parent")
    _require(set(dataset.draft_recipients["contact_id"]) <= contacts, "draft recipient")
    _require(set(dataset.labels["draft_id"]) <= drafts, "label draft")
    _require(set(dataset.labels["contact_id"]) <= contacts, "label contact")
    sources = set(dataset.drafts.loc[dataset.drafts["source_message_id"] != "", "source_message_id"])
    _require(sources <= messages, "source_message_id")
    withheld = set(dataset.drafts.loc[dataset.drafts["withheld_contact_id"] != "", "withheld_contact_id"])
    _require(withheld <= contacts, "withheld contact")
    _require(set(dataset.reviewer_feedback["draft_id"]) <= drafts, "feedback draft")
    _require(set(dataset.reviewer_feedback["contact_id"]) <= contacts, "feedback contact")
    _require(set(dataset.reviewer_feedback["reviewer_id"]) <= contacts, "reviewer")
    return "foreign keys resolve"


def _addresses(dataset) -> str:
    emails = dataset.contacts["email_address"]
    _require(emails.str.match(EMAIL_PATTERN).all(), "contact email format")
    _require(emails.eq(emails.str.lower()).all(), "email lowercase")
    senders = dataset.drafts.merge(
        dataset.contacts[["contact_id", "is_internal", "domain"]],
        left_on="sender_contact_id",
        right_on="contact_id",
        how="left",
    )
    _require(senders["is_internal"].all(), "draft senders are internal")
    _require((senders["domain"] == "demo.example").all(), "draft sender domain")
    return f"{len(emails)} contacts"


def _windows(dataset) -> str:
    for _, row in dataset.messages.iterrows():
        _require(split_for(row["sent_at"]) == row["split"], f"message split {row['message_id']}")
    for _, row in dataset.drafts.iterrows():
        _require(split_for(row["sent_at"]) == row["split"], f"draft split {row['draft_id']}")
        _require(row["split"] in ASSESSMENT_SPLITS, "warmup draft")
    return "timestamps match split windows"


def _chronology(dataset) -> str:
    order = ("warmup", "train", "validation", "test")
    for frame, column in ((dataset.messages, "sent_at"), (dataset.drafts, "sent_at")):
        bounds = []
        for name in order:
            subset = frame.loc[frame["split"] == name, column]
            if subset.empty:
                bounds.append(None)
                continue
            bounds.append((subset.min(), subset.max()))
        previous_end = None
        for name, bound in zip(order, bounds):
            if bound is None:
                continue
            if previous_end is not None:
                _require(previous_end < bound[0], f"{name} overlaps the previous split")
            previous_end = bound[1]
    _require(dataset.drafts.loc[dataset.drafts["split"] == "warmup"].empty, "warmup drafts")
    return "warmup, then train, validation, and test"


def _labels(dataset) -> str:
    label_keys = dataset.labels[["draft_id", "contact_id"]].sort_values(["draft_id", "contact_id"])
    recipient_keys = dataset.draft_recipients[["draft_id", "contact_id"]].sort_values(
        ["draft_id", "contact_id"]
    )
    _require(label_keys.reset_index(drop=True).equals(recipient_keys.reset_index(drop=True)), "label coverage")
    _require(set(dataset.labels["label_source"]) == {"synthetic_stipulated"}, "label source")
    _require(set(dataset.labels["label_confidence"]) == {"certain"}, "label confidence")
    _require(dataset.labels["intended"].isin([True, False]).all(), "intended boolean")
    _require(dataset.labels["stipulation"].str.len().gt(0).all(), "stipulation text")
    manifest = dataset.split_manifest.set_index("draft_id")
    derived = dataset.labels.groupby("draft_id")["intended"].apply(lambda values: bool((~values).any()))
    _require(derived.sort_index().equals(manifest["is_misdirected_email"].sort_index()), "manifest flag")
    return f"{len(dataset.labels)} recipient labels"


def _recipients(dataset) -> str:
    _require(set(dataset.draft_recipients["role"]) <= ROLES, "draft roles")
    _require(set(dataset.message_recipients["role"]) <= ROLES, "message roles")
    counts = dataset.draft_recipients.groupby("draft_id")["contact_id"].nunique()
    _require(counts.ge(1).all() and counts.le(20).all(), "recipient counts")
    return "1 to 20 unique recipients"


def _prevalence(dataset) -> str:
    manifest = dataset.split_manifest
    expected = {
        "train": (PLANS["train"].product_misdirected_count, PLANS["train"].product_total),
        "validation_product_like": (
            PLANS["validation"].product_misdirected_count,
            PLANS["validation"].product_total,
        ),
        "test_product_like": (
            PLANS["test"].product_misdirected_count,
            PLANS["test"].product_total,
        ),
    }
    parts = []
    for subset, (misdirected, total) in expected.items():
        group = manifest.loc[manifest["subset"] == subset]
        observed_misdirected = int(group["is_misdirected_email"].sum())
        _require(len(group) == total, f"{subset} has {len(group)} drafts, expected {total}")
        _require(
            observed_misdirected == misdirected,
            f"{subset} has {observed_misdirected} misdirected drafts, expected {misdirected}",
        )
        parts.append(f"{subset} {observed_misdirected}/{total}")
    return "; ".join(parts)


def _families(dataset) -> str:
    groups = dataset.drafts.groupby("family_id")
    for family_id, group in groups:
        _require(group["split"].nunique() == 1, f"{family_id} split")
        _require(group["subset"].nunique() == 1, f"{family_id} subset")
        if group["subset"].iloc[0] in {
            "train",
            "validation_product_like",
            "test_product_like",
        }:
            _require(len(group) == 1, f"product family {family_id} has {len(group)} drafts")
    return f"{groups.ngroups} families"


def _body_hashes(dataset) -> str:
    message_part = dataset.messages[["body_hash", "split"]]
    draft_part = dataset.drafts[["body_hash", "split"]]
    combined = pd.concat([message_part, draft_part], ignore_index=True)
    combined = combined.loc[combined["body_hash"] != ""]
    counts = combined.groupby("body_hash")["split"].nunique()
    crossed = counts[counts > 1]
    _require(crossed.empty, f"body hashes cross splits: {len(crossed)}")
    return f"{combined['body_hash'].nunique()} non-empty hashes"


def _threads(dataset) -> str:
    counts = dataset.messages.groupby("thread_id")["split"].nunique()
    _require((counts == 1).all(), "thread crosses splits")
    return f"{len(counts)} threads"


def _counterfactuals(dataset) -> str:
    manifest = dataset.split_manifest.set_index("draft_id")
    misdirected = dataset.drafts["draft_id"].isin(manifest.index[manifest["is_misdirected_email"]])
    bad = dataset.drafts.loc[misdirected & ~dataset.drafts["is_counterfactual"]]
    _require(bad.empty, f"misdirected sent drafts: {bad['draft_id'].tolist()[:5]}")
    messages = _recipient_sets(dataset.message_recipients, "message_id")
    message_families = dataset.messages.set_index("message_id")["family_id"]
    sent_pairs = {(message_families.loc[message_id], recipients) for message_id, recipients in messages.items()}
    counterfactual = dataset.drafts.loc[dataset.drafts["is_counterfactual"]]
    draft_sets = _recipient_sets(dataset.draft_recipients, "draft_id")
    leaked = []
    for _, draft in counterfactual.iterrows():
        pair = (draft["family_id"], draft_sets[draft["draft_id"]])
        if pair in sent_pairs:
            leaked.append(draft["draft_id"])
    _require(not leaked, f"counterfactual also sent: {leaked[:5]}")
    return f"{len(counterfactual)} counterfactual drafts"


def _sent_drafts(dataset) -> str:
    sent = dataset.drafts.loc[~dataset.drafts["is_counterfactual"]]
    messages = dataset.messages.set_index("message_id")
    message_sets = _recipient_sets(dataset.message_recipients, "message_id")
    draft_sets = _recipient_sets(dataset.draft_recipients, "draft_id")
    for _, draft in sent.iterrows():
        source_id = draft["source_message_id"]
        _require(source_id in messages.index, f"missing source for {draft['draft_id']}")
        source = messages.loc[source_id]
        _require(source["family_id"] == draft["family_id"], "family mismatch")
        _require(pd.Timestamp(source["sent_at"]) == pd.Timestamp(draft["sent_at"]), "timestamp mismatch")
        _require(source["subject"] == draft["subject"], "subject mismatch")
        _require(source["body"] == draft["body"], "body mismatch")
        _require(source["sender_contact_id"] == draft["sender_contact_id"], "sender mismatch")
        _require(message_sets[source_id] == draft_sets[draft["draft_id"]], f"recipients mismatch {draft['draft_id']}")
    return f"{len(sent)} drafts correspond to sent mail"


def _leakage(dataset) -> str:
    messages = dataset.messages
    family_earliest = messages.groupby("family_id")["sent_at"].min()
    for _, draft in dataset.drafts.iterrows():
        if draft["family_id"] in family_earliest.index:
            _require(
                family_earliest.loc[draft["family_id"]] >= draft["sent_at"],
                f"earlier family mail for {draft['draft_id']}",
            )
    hashed = dataset.drafts.loc[dataset.drafts["body_hash"] != "", ["draft_id", "body_hash", "sent_at"]]
    hash_earliest = messages.loc[messages["body_hash"] != ""].groupby("body_hash")["sent_at"].min()
    for _, draft in hashed.iterrows():
        if draft["body_hash"] in hash_earliest.index:
            _require(
                hash_earliest.loc[draft["body_hash"]] >= draft["sent_at"],
                f"earlier copy of text for {draft['draft_id']}",
            )
    sample = dataset.drafts.loc[dataset.drafts["is_walkthrough"] & (dataset.drafts["scenario_id"] == "S01")]
    _require(len(sample) == 1, "walkthrough S01 missing for history sample")
    history = visible_history(dataset, sample.iloc[0]["draft_id"])
    _require((history["sent_at"] < sample.iloc[0]["sent_at"]).all(), "history cutoff")
    _require((history["family_id"] != sample.iloc[0]["family_id"]).all(), "history family")
    _require(not history.empty, "walkthrough history is empty")
    return "history cutoff holds for every draft"


def _directory(dataset) -> str:
    contacts = dataset.contacts.set_index("contact_id")
    for _, message in dataset.messages.iterrows():
        _require(
            contacts.loc[message["sender_contact_id"], "directory_visible_from"] <= message["sent_at"],
            message["message_id"],
        )
    pairs = dataset.message_recipients.merge(dataset.messages[["message_id", "sent_at"]], on="message_id")
    visible = pairs.merge(
        dataset.contacts[["contact_id", "directory_visible_from"]],
        on="contact_id",
    )
    _require((visible["directory_visible_from"] <= visible["sent_at"]).all(), "message recipient directory")
    draft_pairs = dataset.draft_recipients.merge(dataset.drafts[["draft_id", "sent_at", "sender_contact_id"]], on="draft_id")
    senders = dataset.drafts.merge(
        dataset.contacts[["contact_id", "directory_visible_from"]],
        left_on="sender_contact_id",
        right_on="contact_id",
    )
    _require((senders["directory_visible_from"] <= senders["sent_at"]).all(), "draft sender directory")
    recipients = draft_pairs.merge(
        dataset.contacts[["contact_id", "directory_visible_from"]],
        on="contact_id",
    )
    _require((recipients["directory_visible_from"] <= recipients["sent_at"]).all(), "draft recipient directory")
    return "directory dates respected"


def _topics(dataset) -> str:
    received = dataset.message_recipients.merge(
        dataset.messages[["message_id", "generator_topic"]],
        on="message_id",
    )
    for contact_id, allowed in RESTRICTED_TOPICS.items():
        topics = set(received.loc[received["contact_id"] == contact_id, "generator_topic"])
        _require(topics <= set(allowed), f"{contact_id} topics {sorted(topics - set(allowed))}")
        _require(topics, f"{contact_id} has no sent mail")
    facilities = set(dataset.contacts.loc[dataset.contacts["department"] == "Facilities", "contact_id"])
    s07 = _scenario_contacts(dataset, "S07")
    allowed_with_kickoff = s07 | {"c_sam"}
    for contact_id in facilities:
        topics = set(received.loc[received["contact_id"] == contact_id, "generator_topic"])
        allowed = {"facilities", "kickoff"} if contact_id in allowed_with_kickoff else {"facilities"}
        _require(topics <= allowed, f"facilities contact {contact_id} topics {sorted(topics)}")
    return "relationship topics held in sent mail"


def _scenarios(dataset) -> str:
    contacts = dataset.contacts.set_index("contact_id")
    labels = dataset.labels
    drafts = dataset.drafts
    _require(_scenario_contacts(dataset, "S01"), "S01 missing")
    for _, draft in drafts.loc[drafts["scenario_id"] == "S01"].iterrows():
        if draft["scenario_variant"] == "clean_twin":
            _require(_all_intended(labels, draft["draft_id"]), "S01 twin")
            continue
        bad = _unintended(labels, draft["draft_id"])
        _require(len(bad) == 1, f"S01 {draft['draft_id']} unintended count")
        _require(bool(draft["withheld_contact_id"]), "S01 withheld")
        _require(draft["withheld_contact_id"] not in set(_addressed(dataset, draft["draft_id"])), "withheld still addressed")
        _require("headcount" in draft["body"].casefold(), "S01 body")
    for _, draft in drafts.loc[drafts["scenario_variant"] == "added_external"].iterrows():
        bad = _unintended(labels, draft["draft_id"])
        _require(bad, "S02 unintended")
        for contact_id in bad:
            _require(not bool(contacts.loc[contact_id, "is_internal"]), "S02 external")
        _require(_intended(labels, draft["draft_id"]), "S02 keeps internal recipients")
    for _, draft in drafts.loc[drafts["scenario_id"] == "S03"].iterrows():
        addressed = _addressed(dataset, draft["draft_id"])
        _require(_all_intended(labels, draft["draft_id"]), "S03 intended")
        for contact_id in addressed:
            earlier = _involves_before(dataset, contact_id, draft["sent_at"])
            _require(earlier == 0, f"S03 prior mail for {contact_id}")
    for _, draft in drafts.loc[drafts["scenario_variant"] == "familiar_topic_mismatch"].iterrows():
        bad = _unintended(labels, draft["draft_id"])
        _require(len(bad) == 1, "S04 count")
        _require("salary band" in draft["body"].casefold(), "S04 compensation text")
        contact_id = bad[0]
        _require(contacts.loc[contact_id, "department"] == "Facilities", "S04 facilities")
        _require(_messages_before(dataset, contact_id, draft["sent_at"]) >= 3, "S04 history")
        topics = _topics_before(dataset, contact_id, draft["sent_at"])
        _require("compensation" not in topics, "S04 prior compensation")
    for _, draft in drafts.loc[drafts["scenario_id"] == "S05"].iterrows():
        _require(_all_intended(labels, draft["draft_id"]), "S05 intended")
    for _, draft in drafts.loc[drafts["scenario_id"] == "S06"].iterrows():
        _require(_all_intended(labels, draft["draft_id"]), "S06 intended")
        domains = {contacts.loc[contact_id, "domain"] for contact_id in _addressed(dataset, draft["draft_id"])}
        _require(len(domains) == 1, "S06 domain")
        domain = next(iter(domains))
        _require(domain != "demo.example", "S06 external domain")
        _require(_domain_before(dataset, domain, draft["sent_at"]) == 0, f"S06 domain already used {domain}")
    for _, draft in drafts.loc[drafts["scenario_id"] == "S07"].iterrows():
        _require(_all_intended(labels, draft["draft_id"]), "S07 intended")
        _require("kickoff" in draft["body"].casefold(), "S07 text")
        contact_id = _addressed(dataset, draft["draft_id"])[0]
        prior = _topics_before(dataset, contact_id, draft["sent_at"])
        _require("facilities" in prior, "S07 facilities history")
        _require("kickoff" not in prior, "S07 already had a kickoff")
    for variant, minimum_bad in (("unintended_cc", 1), ("unintended_bcc", 1), ("two_unintended", 2)):
        group = drafts.loc[drafts["scenario_variant"] == variant]
        _require(not group.empty, variant)
        for _, draft in group.iterrows():
            bad = _unintended(labels, draft["draft_id"])
            _require(len(bad) >= minimum_bad, f"{variant} count")
            roles = dataset.draft_recipients.loc[dataset.draft_recipients["draft_id"] == draft["draft_id"]]
            if variant == "two_unintended":
                _require(set(roles["role"]) >= {"to", "cc", "bcc"}, "two-unintended roles")
            else:
                expected_role = "cc" if variant == "unintended_cc" else "bcc"
                bad_roles = set(roles.loc[roles["contact_id"].isin(bad), "role"])
                _require(expected_role in bad_roles, f"{variant} role {sorted(bad_roles)}")
    all_intended = drafts.loc[drafts["scenario_variant"] == "all_intended"]
    _require(not all_intended.empty, "S08 all intended")
    for _, draft in all_intended.iterrows():
        _require(_all_intended(labels, draft["draft_id"]), "S08 clean")
        roles = set(dataset.draft_recipients.loc[dataset.draft_recipients["draft_id"] == draft["draft_id"], "role"])
        _require({"to", "cc"} <= roles, "S08 roles")
    for _, draft in drafts.loc[drafts["scenario_variant"] == "cold_start_legitimate"].iterrows():
        _require(_all_intended(labels, draft["draft_id"]), "S09 cold intended")
        sender = draft["sender_contact_id"]
        earlier = dataset.messages.loc[
            (dataset.messages["sender_contact_id"] == sender) & (dataset.messages["sent_at"] < draft["sent_at"])
        ]
        _require(earlier.empty, "S09 cold history")
        _require(draft["body"].strip() != "", "S09 cold text")
    for _, draft in drafts.loc[drafts["scenario_variant"].isin(["little_text_legitimate", "little_text_unintended"])].iterrows():
        empty = draft["subject"].strip() == "" or draft["body"].strip() == ""
        _require(empty, "S09 little text is not little")
        if draft["scenario_variant"] == "little_text_legitimate":
            _require(_all_intended(labels, draft["draft_id"]), "little text intended")
        else:
            _require(_unintended(labels, draft["draft_id"]), "little text unintended")
    return "S01 through S09 structures hold"


def _walkthrough(dataset) -> str:
    contacts = dataset.contacts.set_index("email_address")
    drafts = dataset.drafts
    walk = drafts.loc[drafts["is_walkthrough"]]
    _require((walk["subset"] == "test_diagnostic").all(), "walkthrough subset")
    _require((walk["split"] == "test").all(), "walkthrough split")

    def draft_for(scenario_id, variant):
        rows = walk.loc[(walk["scenario_id"] == scenario_id) & (walk["scenario_variant"] == variant)]
        _require(len(rows) == 1, f"walkthrough {scenario_id} {variant}")
        return rows.iloc[0]

    s01 = draft_for("S01", "lookalike_replacement")
    _require(_email(dataset, _unintended(dataset.labels, s01["draft_id"])[0]) == "alex.chen@demo.example", "S01 chen")
    _require(contacts.loc["alex.chan@demo.example", "contact_id"] == s01["withheld_contact_id"], "S01 chan")
    s02 = draft_for("S02", "added_external")
    _require(_email(dataset, _unintended(dataset.labels, s02["draft_id"])[0]) == "lee@vendor.example", "S02 lee")
    s03 = draft_for("S03", "legitimate_first_contact")
    _require(_email(dataset, _addressed(dataset, s03["draft_id"])[0]) == "jordan@demo.example", "S03 jordan")
    s04 = draft_for("S04", "familiar_topic_mismatch")
    _require(_email(dataset, _unintended(dataset.labels, s04["draft_id"])[0]) == "sam@demo.example", "S04 sam")
    s07 = draft_for("S07", "legitimate_topic_change")
    _require(_email(dataset, _addressed(dataset, s07["draft_id"])[0]) == "sam@demo.example", "S07 sam")
    _require(s04["sent_at"] == s07["sent_at"], "S04 and S07 share a cutoff")
    s06 = draft_for("S06", "legitimate_new_domain")
    _require(_email(dataset, _addressed(dataset, s06["draft_id"])[0]) == "rina@newpartner.example", "S06 rina")
    s05_external = draft_for("S05", "external_purchase")
    _require(_includes_lee(dataset, s05_external["draft_id"]), "S05 lee")
    _require((dataset.split_manifest.loc[dataset.split_manifest["draft_id"].isin(walk["draft_id"]), "frozen"]).all(), "frozen")
    return f"{len(walk)} walkthrough drafts"


def _feedback(dataset) -> str:
    feedback = dataset.reviewer_feedback
    _require(set(feedback["review_status"]) <= {"pending_review", "rejected"}, "accepted feedback present")
    _require((feedback["review_status"] == "pending_review").any(), "pending example")
    _require((feedback["confidence"] == "uncertain").any(), "uncertain example")
    _require((feedback["review_status"] == "rejected").any(), "rejected example")
    _require((feedback["asserted_intended"] == "").any(), "null assertion")
    return f"{len(feedback)} illustrative feedback rows, none accepted"


def _scoring_view(dataset) -> str:
    draft_id = dataset.drafts.loc[dataset.drafts["subset"] == "train"].sort_values("sent_at").iloc[0]["draft_id"]
    view = scoring_view(dataset, draft_id)
    leaked = denied_keys(view)
    _require(not leaked, f"denied keys in scoring view: {sorted(leaked)}")
    blob = repr(view["features"])
    for token in ("scenario_id", "lookalike_replacement", "synthetic_stipulated", "is_walkthrough"):
        _require(token not in blob, token)
    _require("history" in view["features"], "history")
    return f"scoring view for {draft_id}"


def _frozen(dataset) -> str:
    manifest = dataset.split_manifest
    frozen = manifest.loc[manifest["frozen"], "subset"]
    _require(set(frozen.unique()) == set(FROZEN_SUBSETS), f"frozen subsets {sorted(frozen.unique())}")
    _require((~manifest.loc[~manifest["subset"].isin(FROZEN_SUBSETS), "frozen"]).all(), "non-test frozen")
    _require(manifest.loc[manifest["subset"].isin(FROZEN_SUBSETS), "frozen"].all(), "test not frozen")
    return "test_product_like and test_diagnostic frozen"


def _version(dataset) -> str:
    for frame in (
        dataset.contacts,
        dataset.messages,
        dataset.drafts,
        dataset.labels,
        dataset.reviewer_feedback,
        dataset.split_manifest,
        dataset.invalid_fixtures,
    ):
        _require((frame["dataset_version"] == DATASET_VERSION).all(), "dataset_version")
    _require(dataset.seed == 20260926, f"seed {dataset.seed}")
    return DATASET_VERSION


def _empty_text(dataset) -> str:
    little = {"little_text_legitimate", "little_text_unintended"}
    empty = dataset.drafts["subject"].str.strip().eq("") | dataset.drafts["body"].str.strip().eq("")
    unexpected = dataset.drafts.loc[empty & ~dataset.drafts["scenario_variant"].isin(little)]
    _require(unexpected.empty, f"unexpected empty text {unexpected['draft_id'].tolist()[:5]}")
    required = dataset.drafts.loc[dataset.drafts["scenario_variant"].isin(little)]
    still_full = required.loc[~empty.loc[required.index]]
    _require(still_full.empty, "little-text draft has both subject and body")
    return f"{int(empty.sum())} drafts with empty subject or body"


def _invalid(dataset) -> str:
    fixtures = dataset.invalid_fixtures
    _require(set(fixtures["expected_status"]) == {"unable_to_assess"}, "status")
    _require(set(fixtures["category"]) == {"invalid_input", "unavailable"}, "categories")
    _require(set(fixtures["fixture_id"]).isdisjoint(set(dataset.drafts["draft_id"])), "fixtures mixed into drafts")
    return f"{len(fixtures)} invalid fixtures"


def _coverage(dataset) -> str:
    manifest = dataset.split_manifest
    for subset in ("train", "validation_product_like", "test_product_like"):
        group = manifest.loc[manifest["subset"] == subset]
        for scenario_id in ("S03", "S05", "S06", "S07", "S09"):
            _require((group["scenario_id"] == scenario_id).any(), f"{subset} missing {scenario_id}")
    for subset in ("validation_diagnostic", "test_diagnostic"):
        group = manifest.loc[manifest["subset"] == subset]
        for scenario_id in ("S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"):
            _require((group["scenario_id"] == scenario_id).any(), f"{subset} missing {scenario_id}")
        misdirected = int(group["is_misdirected_email"].sum())
        fraction = misdirected / len(group)
        _require(0.35 <= fraction <= 0.7, f"{subset} misdirected fraction {fraction:.3f}")
    variants = set(manifest.loc[manifest["subset"] == "test_diagnostic", "scenario_variant"])
    for variant in ("unintended_cc", "unintended_bcc", "two_unintended", "all_intended", "clean_twin"):
        _require(variant in variants, f"missing {variant}")
    return "scenario coverage holds"


def _unique_times(dataset) -> str:
    _require(dataset.messages["sent_at"].is_unique, "duplicate message timestamp")
    return f"{len(dataset.messages)} unique sent timestamps"


def _markers(dataset) -> str:
    for topic, marker in TOPIC_MARKERS.items():
        bodies = dataset.messages.loc[
            (dataset.messages["generator_topic"] == topic) & dataset.messages["body"].str.strip().ne(""),
            "body",
        ]
        if bodies.empty:
            continue
        _require(bodies.str.casefold().str.contains(marker, regex=False).all(), f"marker {topic}")
    return "topic markers present"


def _frames(dataset) -> dict[str, pd.DataFrame]:
    return {
        "contacts": dataset.contacts,
        "messages": dataset.messages,
        "message_recipients": dataset.message_recipients,
        "drafts": dataset.drafts,
        "draft_recipients": dataset.draft_recipients,
        "labels": dataset.labels,
        "reviewer_feedback": dataset.reviewer_feedback,
        "split_manifest": dataset.split_manifest,
        "invalid_fixtures": dataset.invalid_fixtures,
    }


def _recipient_sets(frame: pd.DataFrame, key: str) -> dict[str, frozenset]:
    grouped = {}
    for item_id, group in frame.groupby(key, sort=False):
        grouped[item_id] = frozenset(zip(group["contact_id"], group["role"], strict=True))
    return grouped


def _addressed(dataset, draft_id: str) -> list[str]:
    rows = dataset.draft_recipients.loc[dataset.draft_recipients["draft_id"] == draft_id]
    return rows.sort_values("recipient_order")["contact_id"].tolist()


def _unintended(labels, draft_id: str) -> list[str]:
    rows = labels.loc[(labels["draft_id"] == draft_id) & (~labels["intended"])]
    return sorted(rows["contact_id"].tolist())


def _intended(labels, draft_id: str) -> list[str]:
    rows = labels.loc[(labels["draft_id"] == draft_id) & labels["intended"]]
    return sorted(rows["contact_id"].tolist())


def _all_intended(labels, draft_id: str) -> bool:
    rows = labels.loc[labels["draft_id"] == draft_id, "intended"]
    return bool(len(rows) and rows.all())


def _scenario_contacts(dataset, scenario_id: str) -> set[str]:
    draft_ids = set(dataset.drafts.loc[dataset.drafts["scenario_id"] == scenario_id, "draft_id"])
    rows = dataset.draft_recipients.loc[dataset.draft_recipients["draft_id"].isin(draft_ids)]
    return set(rows["contact_id"])


def _involves_before(dataset, contact_id: str, cutoff) -> int:
    sent = dataset.messages
    sent_ids = set(sent.loc[sent["sent_at"] < cutoff, "message_id"])
    as_sender = sent.loc[(sent["sender_contact_id"] == contact_id) & (sent["sent_at"] < cutoff)]
    as_recipient = dataset.message_recipients.loc[
        (dataset.message_recipients["contact_id"] == contact_id)
        & dataset.message_recipients["message_id"].isin(sent_ids)
    ]
    return int(len(as_sender) + len(as_recipient))


def _messages_before(dataset, contact_id: str, cutoff) -> int:
    return _involves_before(dataset, contact_id, cutoff)


def _topics_before(dataset, contact_id: str, cutoff) -> set[str]:
    sent = dataset.messages
    early_ids = set(sent.loc[sent["sent_at"] < cutoff, "message_id"])
    received_ids = set(
        dataset.message_recipients.loc[
            (dataset.message_recipients["contact_id"] == contact_id)
            & dataset.message_recipients["message_id"].isin(early_ids),
            "message_id",
        ]
    )
    sent_ids = set(sent.loc[(sent["sender_contact_id"] == contact_id) & (sent["sent_at"] < cutoff), "message_id"])
    topics = sent.loc[sent["message_id"].isin(received_ids | sent_ids), "generator_topic"]
    return set(topics.tolist())


def _domain_before(dataset, domain: str, cutoff) -> int:
    contacts = dataset.contacts
    people = set(contacts.loc[contacts["domain"] == domain, "contact_id"])
    if not people:
        return 0
    total = 0
    for contact_id in people:
        total += _involves_before(dataset, contact_id, cutoff)
    return total


def _email(dataset, contact_id: str) -> str:
    contacts = dataset.contacts
    return contacts.loc[contacts["contact_id"] == contact_id, "email_address"].iloc[0]


def _includes_lee(dataset, draft_id: str) -> bool:
    return "lee@vendor.example" in {_email(dataset, contact_id) for contact_id in _addressed(dataset, draft_id)}
