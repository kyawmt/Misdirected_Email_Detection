"""Documentation-generator version, record locations, and what may be read from a frozen record.

This package writes the Phase 10 documents from stored records. It uses the
standard library only: it imports no scoring, fitting, feature, or
dataset-reading code and never opens a data table. Record locations are written
here, not imported, so that importing this package stays light; a test requires
them to equal the version modules of the packages that own the records
(`med_policy.version`, `med_api.version`, `med_monitor.version`,
`med_deploy.version`).

Change DOCS_VERSION when a rendering rule, a status rule, or a record location
changes.
"""

from __future__ import annotations

from pathlib import Path

DOCS_VERSION = "med-docs-v1"

DOCS_DIR = Path("docs")
README_PATH = Path("README.md")

DATASET_DIR = Path("data/med-synth-v4")
FEATURES_DIR = Path("artifacts/med-features-v2")
MODEL_DIR = Path("artifacts/med-model-v2")
POLICY_DIR = Path("artifacts/med-policy-v2")
API_LATENCY_PATH = Path("artifacts/med-api-latency/med-policy-v2/latency.json")
MONITOR_DIR = Path("artifacts/med-monitor-v1")
DEPLOY_DIR = Path("artifacts/med-deploy-v1")

SELECTION_SUBSET = "validation_product_like"
DIAGNOSTIC_SUBSET = "validation_diagnostic"
TEST_PRODUCT = "test_product_like"
TEST_DIAGNOSTIC = "test_diagnostic"
FROZEN_SUBSETS = (TEST_PRODUCT, TEST_DIAGNOSTIC)
VALIDATION_SUBSETS = (SELECTION_SUBSET, DIAGNOSTIC_SUBSET)

# ------------------------------------------------------------ frozen records

# `test_evaluation.json` stores the one recorded test pass and, under each
# subset, per-draft outcomes of frozen test drafts (ids, scenarios, scores,
# subjects). These members are discarded while the file is parsed, before any
# code can look at them, in this file and in the validation record.
SEALED_KEYS = frozenset({"outcomes", "examples", "examples_validation"})

# The only paths read from `test_evaluation.json`. Everything else is dropped as
# soon as the file is parsed. Paths below a subset are relative to
# `subsets/<name>/`.
TEST_TOP_PATHS = ("policy_version", "policy_sha256", "T_warn", "blocking_enabled", "evaluated_at")
TEST_SUBSET_PATHS = (
    "policy/cutoff",
    "policy/email",
    "policy/recipient",
    "policy/attribution",
    "policy/interventions",
    "policy/coverage",
    "slices/email_by_scenario",
)

# The same rule for the validation record. It is not frozen, but the generator
# treats both files alike and reads aggregates only.
VALIDATION_TOP_PATHS = ("policy_version", "T_warn")
VALIDATION_SUBSET_PATHS = (
    "policy/cutoff",
    "policy/email",
    "policy/recipient",
    "policy/attribution",
    "policy/interventions",
    "policy/coverage",
    "rules_same_budget/email",
    "rules_same_budget/interventions",
    "always_allow/email",
    "always_allow/interventions",
    "slices/email_by_scenario",
    "slices/email_by_recipient_count",
    "first_contact",
)

# ------------------------------------------------------------- status inputs

# AC01 would be "met" only with an argument that emails are independent, or with
# a more independent evaluation on a new frozen dataset version. Neither exists:
# most product-like test drafts come from one sender
# (docs/phase_5/UNCERTAINTY_AND_PREVALENCE.md#independence). The sender counts
# need the draft table, which this package never opens, so the fact is stated
# here once and linked from every document that relies on it.
INDEPENDENCE_ESTABLISHED = False

# Scenario labels, as in docs/phase_1/SCENARIOS.md. The records carry only the ids.
SCENARIO_TITLES = {
    "S01": "Lookalike replacement",
    "S02": "Added external recipient",
    "S03": "New legitimate collaborator",
    "S04": "Familiar recipient, unusual topic",
    "S05": "Routine legitimate mail",
    "S06": "Uncommon external domain, valid purpose",
    "S07": "Legitimate topic change",
    "S08": "Multiple recipients and roles",
    "S09": "Cold start or little text",
    "S11": "Mistaken first contact",
    "routine": "Background routine mail",
}
KNOWN_MISSES = ("S01", "S04", "S11")
LEGITIMATE_NOVELTY_SCENARIOS = ("S03", "S05", "S06", "S07")
